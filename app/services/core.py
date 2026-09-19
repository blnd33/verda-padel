"""Authoritative rules. Amounts are integer IQD; stored timestamps are naive UTC.

Mutation callers must hold the database write lock for their complete transaction.
"""
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
import math
import re
import secrets
from flask_login import current_user
from sqlalchemy import or_
from app import db
from app.models import *


class RuleError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def settings():
    return db.session.get(Settings, 1)


def local(value, tz=None):
    return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz or settings().timezone))


def utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def business_date(value=None):
    s = settings()
    v = local(value or now())
    return v.date() - timedelta(days=int(s.closing_hour <= s.opening_hour and v.hour < s.closing_hour))


def integer(value, minimum=0, maximum=1000000000):
    if isinstance(value, bool) or not re.fullmatch(r'-?\d+', str(value).strip()):
        raise RuleError('Enter a valid whole number.')
    n = int(value)
    if not minimum <= n <= maximum:
        raise RuleError('The number is outside the allowed range.')
    return n


def money(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def text_value(value, required=False, limit=500):
    v = str(value or '').strip()
    if (required and not v) or len(v) > limit:
        raise RuleError('Complete the required fields and keep text within the allowed length.')
    return v


def customer(data):
    name = text_value(data.get('customer_name'), True, 100)
    phone = text_value(data.get('customer_phone'), True, 20)
    if not re.fullmatch(r'[+\d() -]{7,20}', phone):
        raise RuleError('Enter a valid phone number.')
    email = text_value(data.get('customer_email'), False, 100)
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise RuleError('Enter a valid email address.')
    return dict(customer_name=name, customer_phone=phone, customer_email=email or None,
                notes=text_value(data.get('notes'), limit=1000))


def actor():
    return current_user.id if current_user and current_user.is_authenticated else None


def audit(action, obj, reason='', before=None, after=None, amount=None, method=None):
    db.session.add(ActivityLog(user_id=actor(), action=action, entity_type=obj.__tablename__,
        entity_id=obj.id, title=action, note=reason, before_values=before, after_values=after,
        amount=amount, payment_method=method))


def notify(scope, title, url):
    db.session.add(Notification(type=scope, title=title, url=url, message='', scope=scope))


def reference():
    return secrets.token_urlsafe(24)


def rules(court=None):
    s = settings()
    return dict(rate=money(court.price_per_hour if court and court.price_per_hour is not None else s.price_per_hour),
        minimum_minutes=s.minimum_minutes, rounding_minutes=s.rounding_minutes,
        discount_percentage=s.discount_percentage, discount_start_hour=s.discount_start_hour,
        discount_end_hour=s.discount_end_hour, evening_rate=money(s.evening_rate),
        evening_start_hour=s.evening_start_hour, evening_end_hour=s.evening_end_hour, timezone=s.timezone)


def within_window(hour, a, b):
    return (a <= hour < b) if a < b else (hour >= a or hour < b) if a > b else False


def discounted_hour(hour, rule):
    return within_window(hour, rule['discount_start_hour'], rule['discount_end_hour'])


def hour_rate(hour, rule):
    """Snapshots taken before evening pricing existed carry no evening keys and stay on the base rate."""
    if rule.get('evening_rate') and within_window(hour, rule.get('evening_start_hour', 0), rule.get('evening_end_hour', 0)):
        return rule['evening_rate']
    return rule['rate']


def price_interval(start, seconds, rule):
    """Prorate the billed interval across rate and discount windows, round each total once."""
    original, discount = Decimal(0), Decimal(0)
    cursor, end = start, start + timedelta(seconds=seconds)
    while cursor < end:
        venue = local(cursor, rule['timezone'])
        boundary = cursor + timedelta(seconds=3600 - venue.minute * 60 - venue.second - venue.microsecond / 1e6)
        step = min(boundary, end)
        billed = Decimal(str((step - cursor).total_seconds())) * Decimal(hour_rate(venue.hour, rule)) / Decimal(3600)
        original += billed
        if discounted_hour(venue.hour, rule):
            discount += billed * Decimal(rule['discount_percentage']) / 100
        cursor = step
    return money(original), money(discount)


def interval(court_id, day, hour, duration, public=True, exclude=None, past=True):
    s = settings()
    court = db.session.get(Stadium, integer(court_id, 1))
    if not court or not court.is_active or (public and not court.show_in_booking):
        raise RuleError('This court is not available.')
    try:
        day = date.fromisoformat(str(day))
    except ValueError:
        raise RuleError('Choose a valid business date.')
    hour = integer(hour, 0, 23)
    duration = integer(duration, 1, s.max_booking_hours)
    opening = datetime.combine(day, time(s.opening_hour), ZoneInfo(s.timezone))
    closing = datetime.combine(day, time(s.closing_hour), ZoneInfo(s.timezone))
    if closing <= opening:
        closing += timedelta(days=1)
    start = datetime.combine(day, time(hour), ZoneInfo(s.timezone))
    if start < opening:
        start += timedelta(days=1)
    end = start + timedelta(hours=duration)
    a, b = utc(start), utc(end)
    if start < opening or end > closing:
        raise RuleError('The duration extends beyond opening hours.')
    if past and (a < now() or day > business_date() + timedelta(days=s.booking_days_ahead)):
        raise RuleError('Choose an upcoming time within the booking window.')
    query = Booking.query.filter(Booking.stadium_id == court.id,
        Booking.status.in_(['pending', 'confirmed', 'pending_cancel']), Booking.starts_at < b, Booking.ends_at > a)
    if exclude:
        query = query.filter(Booking.id != exclude)
    blocked = CourtBlock.query.filter(CourtBlock.stadium_id == court.id, CourtBlock.starts_at < b,
                                     CourtBlock.ends_at > a).first()
    occupied = POSSession.query.filter_by(stadium_id=court.id, status='active').first()
    occupied_overlap = False
    if occupied and (not exclude or occupied.booking_id != exclude):
        policy=occupied.pricing_snapshot
        rounding=max(1,policy['rounding_minutes'])*60
        elapsed=max(0,(now()-occupied.start_time).total_seconds())
        projected_end=occupied.start_time+timedelta(seconds=max(policy['minimum_minutes']*60,(math.floor(elapsed/rounding)+1)*rounding))
        if occupied.booking:
            projected_end=max(projected_end,occupied.booking.ends_at)
        occupied_overlap=a<projected_end and b>occupied.start_time
    if query.first() or blocked or occupied_overlap:
        raise RuleError('This time is no longer available. Choose another slot.')
    return court, day, a, b, duration


def create_booking(data, public=True, existing=None):
    court, day, a, b, duration = interval(data.get('stadium_id'), data.get('date'), data.get('hour'),
        data.get('duration'), public=public, exclude=existing.id if existing else None)
    if existing and (existing.status not in ['pending', 'confirmed'] or existing.pos_sessions):
        raise RuleError('This reservation can no longer be edited.')
    details = customer(data)
    rule = rules(court)
    original, discount = price_interval(a, duration * 3600, rule)
    record = existing or Booking(reference=reference())
    for k, v in details.items():
        setattr(record, k, v)
    record.stadium_id, record.business_day, record.starts_at, record.ends_at = court.id, day, a, b
    record.date, record.start_time, record.end_time = local(a).date(), local(a).time().replace(tzinfo=None), local(b).time().replace(tzinfo=None)
    record.duration_hours, record.original_price, record.discount_amount = duration, original, discount
    record.final_price, record.discount_percentage, record.pricing_snapshot = original - discount, rule['discount_percentage'], rule
    if not existing:
        record.status = 'pending'
        db.session.add(record)
    db.session.flush()
    audit('Booking updated' if existing else 'Booking requested', record)
    if not existing:
        notify('bookings', 'New booking request', f'/admin/bookings/{record.id}')
    return record


def decide_booking(record, action, reason=''):
    old = record.status
    if action == 'confirm' and old == 'pending':
        interval(record.stadium_id, record.business_day, local(record.starts_at, record.pricing_snapshot['timezone']).hour,
                 record.duration_hours, public=False, exclude=record.id)
        record.status, record.confirmed_at, record.confirmed_by = 'confirmed', now(), actor()
    elif action == 'request_cancel' and old in ['pending', 'confirmed']:
        if record.pos_sessions:
            raise RuleError('A linked bill must be resolved before cancellation.')
        record.previous_status, record.status = old, 'pending_cancel'
        notify('cancellations', 'Cancellation request', f'/admin/bookings/{record.id}')
    elif action in ['cancel', 'reject'] and old in ['pending', 'confirmed', 'pending_cancel']:
        if record.pos_sessions:
            raise RuleError('A linked bill must be resolved before cancellation.')
        record.rejection_reason = text_value(reason, True, 255)
        record.status = 'cancelled'
    elif action == 'restore' and old == 'pending_cancel':
        record.status = record.previous_status or 'confirmed'
    elif action == 'complete' and old == 'confirmed':
        record.status = 'completed'
    elif action == 'archive' and old in ['completed', 'cancelled']:
        record.archived = True
    else:
        raise RuleError('This status change is not allowed.')
    audit('Booking ' + action, record, reason, {'status': old}, {'status': record.status})


def visible_product(product, channel):
    if not product or not product.is_active or not getattr(product, 'show_in_' + channel):
        return False
    category = product.category
    return not category or (category.is_active and getattr(category, 'show_on_' + channel))


def product_query(channel):
    return Product.query.outerjoin(Category).filter(Product.is_active.is_(True),
        getattr(Product, 'show_in_' + channel).is_(True), or_(Category.id.is_(None),
        (Category.is_active.is_(True) & getattr(Category, 'show_on_' + channel).is_(True))))


def stock_change(product, delta, reason, source):
    if product.track_stock:
        if product.stock + delta < 0:
            raise RuleError('There is not enough stock for this item.')
        product.stock += delta
    db.session.add(StockMovement(product_id=product.id, quantity=delta, reason=reason,
        source_type=source.__tablename__, source_id=source.id, user_id=actor()))
    if product.track_stock and delta < 0 and product.stock <= product.low_stock_threshold:
        notify('inventory', 'Low stock', '/admin/inventory')


def basket_lines(items, channel):
    if not isinstance(items, list) or not items or len(items) > 100:
        raise RuleError('Your basket is empty or invalid.')
    merged = {}
    for entry in items:
        pid, qty = integer(entry.get('product_id'), 1), integer(entry.get('quantity'), 1, 999)
        merged[pid] = integer(merged.get(pid, 0) + qty, 1, 999)
    result = []
    for pid, qty in merged.items():
        p = db.session.get(Product, pid)
        if not visible_product(p, channel):
            raise RuleError('An item in your basket is no longer available.')
        if p.track_stock and qty > p.stock:
            raise RuleError('There is not enough stock for this item.')
        result.append((p, qty))
    return result


def snapshot_product(p):
    return dict(name_en=p.name_en, name_ar=p.name_ar, cost=p.cost_price, barcode=p.barcode)


def create_order(data, items):
    s = settings()
    details = customer(data)
    method = data.get('delivery_method', 'pickup')
    if method not in ['pickup', 'delivery'] or (method == 'delivery' and not s.delivery_enabled):
        raise RuleError('Choose an available collection method.')
    area = text_value(data.get('area'), method == 'delivery', 100) if method == 'delivery' else None
    address = text_value(data.get('address'), method == 'delivery', 500) if method == 'delivery' else None
    lines = basket_lines(items, 'website')
    fee = s.delivery_fee if method == 'delivery' else 0
    order = Order(**details, delivery_method=method, area=area, address=address, delivery_fee=fee,
        reference=reference(), total_price=sum(p.price*q for p,q in lines)+fee, business_day=business_date(),
        venue_snapshot=venue_snapshot())
    db.session.add(order)
    db.session.flush()
    for p, q in lines:
        db.session.add(OrderItem(order_id=order.id, product_id=p.id, quantity=q, price=p.price, snapshot=snapshot_product(p)))
        stock_change(p, -q, 'Website order', order)
    audit('Order requested', order)
    notify('orders', 'New website order', f'/admin/orders/{order.id}')
    return order


def cancel_order(order, reason):
    if order.status == 'cancelled':
        return
    if order.status in ['delivered', 'collected'] or order.payments:
        raise RuleError('Use a controlled refund/return for fulfilled or paid goods.')
    for line in order.items:
        stock_change(line.product, line.quantity, 'Unfulfilled order cancellation', order)
    order.status = 'cancelled'
    order.stock_restored = True
    audit('Order cancelled', order, text_value(reason, True))


def venue_snapshot():
    s = settings()
    return dict(name=s.site_name, phone=s.phone, address=s.address, timezone=s.timezone,
                receipt_width=s.receipt_width, email=s.email,
                cashier=current_user.username if current_user and current_user.is_authenticated else None)


def start_session(data):
    kind = data.get('session_type')
    if kind not in ['stadium', 'table', 'quick']:
        raise RuleError('Choose a court or table.')
    location = None
    if kind != 'quick':
        model = Stadium if kind == 'stadium' else Table
        location = db.session.get(model, integer(data.get('location_id'), 1))
        if not location or not location.is_active or (kind == 'stadium' and not location.show_in_pos):
            raise RuleError('This location is not available.')
        key = f'{kind}:{location.id}'
        if POSSession.query.filter_by(occupancy_key=key).first():
            raise RuleError('This location is already occupied.')
    else:
        key = None
    booking = None
    if data.get('booking_id'):
        booking = db.session.get(Booking, integer(data['booking_id'], 1))
        if (not booking or kind != 'stadium' or booking.stadium_id != location.id or
                booking.status != 'confirmed' or booking.pos_sessions):
            raise RuleError('Choose an eligible confirmed reservation.')
        if not booking.starts_at <= now() < booking.ends_at:
            raise RuleError('Start a reserved session during its reserved interval.')
    if kind == 'stadium':
        next_end = now() + timedelta(minutes=settings().minimum_minutes)
        conflicts = Booking.query.filter(Booking.stadium_id == location.id,
            Booking.status.in_(['pending','confirmed','pending_cancel']), Booking.starts_at < next_end,
            Booking.ends_at > now())
        if booking:
            conflicts = conflicts.filter(Booking.id != booking.id)
        if conflicts.first() or CourtBlock.query.filter(CourtBlock.stadium_id==location.id,
                CourtBlock.starts_at < next_end, CourtBlock.ends_at > now()).first():
            raise RuleError('A reservation or maintenance block occupies this time.')
    record = POSSession(session_type=kind, stadium_id=location.id if kind=='stadium' else None,
        table_id=location.id if kind=='table' else None, occupancy_key=key,
        customer_name=text_value(data.get('customer_name'), limit=100),
        customer_phone=text_value(data.get('customer_phone'), limit=20), start_time=now(), created_at=now(),
        reference=reference(), booking_id=booking.id if booking else None,
        pricing_snapshot=booking.pricing_snapshot if booking else rules(location if kind=='stadium' else None),
        venue_snapshot=venue_snapshot(), location_snapshot=location.name if location else 'Quick sale',
        cashier_id=actor(), business_day=business_date())
    db.session.add(record)
    db.session.flush()
    audit('Session started', record)
    return record


def session_quote(record, at=None):
    finish = record.end_time or at or now()
    seconds = max(0, (finish-record.start_time).total_seconds())
    original, auto, billed = 0, 0, 0
    if record.session_type == 'stadium':
        r = record.pricing_snapshot
        rounding = max(1, r['rounding_minutes']) * 60
        if record.booking:
            extra = max(0, (finish - record.booking.ends_at).total_seconds())
            billed = math.ceil(extra / rounding) * rounding
            ext, disc = price_interval(record.booking.ends_at, billed, r)
            original, auto = money(record.booking.original_price)+ext, money(record.booking.discount_amount)+disc
            billed += record.booking.duration_hours*3600
        else:
            billed = max(r['minimum_minutes']*60, math.ceil(seconds/rounding)*rounding)
            original, auto = price_interval(record.start_time, billed, r)
    products = sum(money(i.price)*i.quantity for o in record.orders for i in o.items)
    discount = money(record.manual_discount or 0)
    subtotal = original + products - auto
    if record.discount_kind == 'percentage':
        discount = money(Decimal(subtotal)*record.discount_value/100)
    elif record.discount_kind == 'fixed':
        discount = min(subtotal, record.discount_value)
    return dict(seconds=seconds, billed_seconds=billed, original=original, auto_discount=auto,
        products=products, manual_discount=discount, total=max(0, subtotal-discount))


def finish_play(record):
    if record.status != 'active':
        if record.end_time:
            return
        raise RuleError('This session cannot be stopped.')
    record.end_time, record.status, record.occupancy_key = now(), 'stopped', None
    quote = session_quote(record)
    record.play_time_minutes = math.ceil(quote['seconds']/60)
    record.play_time_price, record.auto_discount, record.total_amount = quote['original'], quote['auto_discount'], quote['total']
    record.actual_seconds, record.billed_seconds = math.ceil(quote['seconds']), quote['billed_seconds']
    audit('Play finished', record)


def add_item(record, product_id, quantity):
    if record.status not in ['active', 'stopped']:
        raise RuleError('This bill is finalized.')
    p, q = basket_lines([{'product_id':product_id, 'quantity':quantity}], 'pos')[0]
    order = next((o for o in record.orders if o.status == 'pending'), None)
    if not order:
        order = POSOrder(session_id=record.id, total_price=0)
        db.session.add(order)
        db.session.flush()
        db.session.expire(record, ['orders'])
    line = POSOrderItem(order_id=order.id, product_id=p.id, quantity=q, price=p.price, snapshot=snapshot_product(p))
    db.session.add(line)
    stock_change(p, -q, 'POS item', record)
    db.session.flush()
    db.session.expire(order, ['items'])
    order.calculate_total()
    audit('Item added', record)


def update_item(record, item, quantity):
    if record.status not in ['active','stopped'] or item.order.session_id != record.id:
        raise RuleError('This bill is finalized.')
    quantity = integer(quantity, 0, 999)
    delta = quantity - item.quantity
    if delta < 0 and item.order.status in ['preparing','ready','delivered']:
        raise RuleError('Prepared goods require an explicit return after settlement.')
    if delta > 0 and not visible_product(item.product, 'pos'):
        raise RuleError('This item is no longer available.')
    stock_change(item.product, -delta, 'POS quantity correction', record)
    item.quantity = quantity
    item.order.calculate_total()
    audit('Item quantity changed', record)


def balance(obj):
    total = money(obj.total_amount if isinstance(obj, POSSession) else obj.total_price)
    return max(0, total - sum(p.amount for p in obj.payments))


def settle_session(record, method):
    if record.status in ['paid','debt']:
        return
    if record.status not in ['active','stopped'] or method not in ['cash','card','debt']:
        raise RuleError('Choose a valid payment method.')
    if method == 'debt' and not record.customer_name:
        raise RuleError('A customer name is required for debt.')
    finish_play(record)
    q = session_quote(record)
    record.play_time_price, record.auto_discount = q['original'], q['auto_discount']
    record.manual_discount, record.total_amount = q['manual_discount'], q['total']
    record.status, record.payment_method, record.finalized_at = ('debt' if method=='debt' else 'paid'), method, now()
    if record.booking:
        record.booking.status = 'completed'
    if method == 'debt' and q['total']:
        db.session.add(ManualDebt(name=record.customer_name, phone=record.customer_phone, amount=q['total'],
            paid_amount=0, date=business_date(), session_id=record.id, created_by=actor()))
    elif q['total']:
        db.session.add(Payment(session_id=record.id, amount=q['total'], method=method, user_id=actor(), business_day=business_date()))
    audit('Bill finalized', record, amount=q['total'], method=method)


def collect_debt(debt, amount, method):
    amount = integer(amount, 1)
    if method not in ['cash','card'] or amount > debt.remaining or debt.status != 'open':
        raise RuleError('The collection exceeds the remaining balance or is invalid.')
    db.session.add(Payment(debt_id=debt.id, session_id=debt.session_id, amount=amount, method=method,
                           user_id=actor(), business_day=business_date()))
    debt.paid_amount += amount
    debt.status = 'paid' if debt.remaining == 0 else 'open'
    audit('Debt collected', debt, amount=amount, method=method)


def refund_bill(obj, reason, restock=False):
    if obj.voided:
        return
    is_session = isinstance(obj, POSSession)
    if is_session and obj.status not in ['paid','debt']:
        raise RuleError('Only finalized bills can be refunded here.')
    if not is_session and obj.status == 'cancelled':
        raise RuleError('This order is already cancelled.')
    reason = text_value(reason, True)
    total = money(obj.total_amount if is_session else obj.total_price)
    paid = sum(p.amount for p in obj.payments)
    source = dict(session_id=obj.id) if is_session else dict(order_id=obj.id)
    adjustment = Adjustment(**source, amount=total, reason=reason, user_id=actor(), business_day=business_date())
    db.session.add(adjustment)
    # Refund actual collections by their recorded methods; never refund receivables as cash.
    for payment in list(obj.payments):
        if payment.amount>0:
            db.session.add(Payment(**source, debt_id=payment.debt_id, amount=-payment.amount,
                method=payment.method, user_id=actor(), business_day=business_date()))
    if is_session:
        for debt in ManualDebt.query.filter_by(session_id=obj.id).all():
            debt.status = 'void'
    if restock:
        lines = [i for o in obj.orders for i in o.items] if is_session else obj.items
        for i in lines:
            stock_change(i.product, i.quantity, 'Explicit goods return', obj)
        obj.stock_restored = True
        adjustment.cogs_reversal=sum((i.snapshot or {}).get('cost',0)*i.quantity for i in lines)
    else:
        adjustment.cogs_reversal=0
    if not is_session and not obj.finalized_at:
        # A pre-fulfillment refund reverses a collection, not a recognized sale.
        adjustment.amount=0
        adjustment.cogs_reversal=0
    obj.voided = True
    audit('Bill refunded', obj, reason, amount=total)


def court_usage(start, end):
    """Actual occupied time within current scheduled hours; denominator is an estimate.

    Historical opening-hour and court-activation schedules were not recorded.
    Union intervals prevent double counting maintenance or adjacent sessions.
    """
    config=settings()
    zone=ZoneInfo(config.timezone)
    first=utc(datetime.combine(start,time(config.opening_hour),zone))
    last=utc(datetime.combine(end+timedelta(days=1),time(config.opening_hour),zone))
    until=min(last,now())
    sessions=POSSession.query.filter(POSSession.session_type=='stadium',
        POSSession.status!='cancelled',POSSession.start_time<until,
        or_(POSSession.end_time.is_(None),POSSession.end_time>first)).all()
    blocks=CourtBlock.query.filter(CourtBlock.starts_at<until,CourtBlock.ends_at>first).all()
    def merged_seconds(intervals):
        total=0
        finish=None
        for a,b in sorted(intervals):
            if finish is None or a>finish:
                total+=(b-a).total_seconds()
            elif b>finish:
                total+=(b-finish).total_seconds()
            finish=max(finish or b,b)
        return total
    output=[]
    for court in Stadium.query.all():
        uses=[s for s in sessions if s.stadium_id==court.id]
        if not court.is_active and not uses:
            continue
        unavailable=[b for b in blocks if b.stadium_id==court.id]
        occupied=available=0
        day=start
        while day<=end:
            a=utc(datetime.combine(day,time(config.opening_hour),zone))
            close_day=day+timedelta(days=int(config.closing_hour<=config.opening_hour))
            b=min(utc(datetime.combine(close_day,time(config.closing_hour),zone)),until)
            if b>a:
                blocked=[(max(a,x.starts_at),min(b,x.ends_at)) for x in unavailable if x.starts_at<b and x.ends_at>a]
                available+=max(0,(b-a).total_seconds()-merged_seconds(blocked))
                used=[(max(a,s.start_time),min(b,s.end_time or until)) for s in uses if s.start_time<b and (s.end_time or until)>a]
                occupied+=merged_seconds(used)
            day+=timedelta(days=1)
        output.append(dict(name=court.name,occupied_hours=occupied/3600,available_hours=available/3600,
            utilization=100*occupied/available if available else 0))
    return output


def reports(start, end):
    """Business-date sales and actual-date collections are deliberately separate."""
    sessions = POSSession.query.filter(POSSession.business_day.between(start,end), POSSession.finalized_at.isnot(None)).all()
    orders = Order.query.filter(Order.business_day.between(start,end), Order.finalized_at.isnot(None)).all()
    payments = Payment.query.filter(Payment.business_day.between(start,end)).all()
    expenses = Expense.query.filter(Expense.date.between(start,end), Expense.voided.is_(False)).all()
    adjustments = Adjustment.query.filter(Adjustment.business_day.between(start,end)).all()
    bookings = Booking.query.filter(Booking.business_day.between(start,end)).all()
    debts = ManualDebt.query.filter(ManualDebt.date.between(start,end)).all()
    lines = [i for s in sessions for o in s.orders for i in o.items] + [i for o in orders for i in o.items]
    costs = sum((i.snapshot or {}).get('cost',0)*i.quantity for i in lines)
    returned_costs=sum(a.cogs_reversal or 0 for a in adjustments)
    net_costs=costs-returned_costs
    by_type = {k:sum(money(s.total_amount) for s in sessions if s.session_type==k) for k in ['stadium','table','quick']}
    sales = sum(by_type.values())+sum(money(o.total_price) for o in orders)
    collected = sum(p.amount for p in payments)
    expenditure = sum(e.amount for e in expenses)
    operating_expenses = sum(e.amount for e in expenses if e.category != 'purchases')
    refunds = sum(a.amount for a in adjustments)
    product_summary={}
    for item in lines:
        # Historical prices and names come from the sale, never the live catalog.
        snap=item.snapshot or {}
        key=(item.product_id,snap.get('name_en'),item.price,snap.get('cost',0))
        entry=product_summary.setdefault(key,dict(snapshot=snap,quantity=0,sales=0,cost=0))
        entry['quantity']+=item.quantity
        entry['sales']+=item.quantity*item.price
        entry['cost']+=item.quantity*snap.get('cost',0)
    return dict(sessions=sessions, orders=orders, payments=payments, expenses=expenses, adjustments=adjustments,
        bookings=bookings, product_summary=list(product_summary.values()), sales=sales, refunds=refunds, net_sales=sales-refunds,
        court_time_sales=sum(s.play_time_price-s.auto_discount for s in sessions if s.session_type=='stadium'),
        collected=collected, cash=sum(p.amount for p in payments if p.method=='cash'),
        card=sum(p.amount for p in payments if p.method=='card'), expenses_total=expenditure,
        cash_movement=collected-expenditure, cogs=net_costs, original_cogs=costs, returned_costs=returned_costs,
        gross_margin=sales-refunds-net_costs,
        operating_result=sales-refunds-net_costs-operating_expenses, by_type=by_type,
        website_sales=sum(money(o.total_price) for o in orders),
        debt_created=sum(d.amount for d in debts if d.status!='void'),
        debt_collections=sum(p.amount for p in payments if p.debt_id),
        outstanding=sum(d.remaining for d in ManualDebt.query.filter_by(status='open')),
        discounts=sum(money(s.auto_discount)+money(s.manual_discount) for s in sessions),
        product_quantity=sum(i.quantity for i in lines),
        quoted=sum(money(b.final_price) for b in bookings if b.status!='cancelled'),
        confirmed_value=sum(money(b.final_price) for b in bookings if b.status in ['confirmed','completed']),
        booked_hours=sum(b.duration_hours for b in bookings if b.status in ['confirmed','completed']),
        active=POSSession.query.filter_by(status='active').count(),
        unpaid=sum(session_quote(s)['total'] for s in POSSession.query.filter_by(status='stopped')))
