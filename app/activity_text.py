"""Activity log entries as plain sentences.

The log stores an action name, the record it touched and optional before/after
values. This turns each entry into a sentence a manager can read ("blnd applied
a 10% discount to Sara's tab") plus a short list of what changed, in English or
Arabic. Sentence templates are English locale keys with {placeholders}, so the
Arabic wording lives in locales.tsv next to every other translation.
"""
from app import db
from app.i18n import translate, clock_of
from app.money import fmt as money_fmt, CURRENCIES

MONEY_FIELDS = {'price', 'cost_price', 'amount'}
IQD_FIELDS = {'price_per_hour', 'evening_rate', 'delivery_fee'}
HIDDEN_FIELDS = {'password', 'image', 'image_url'}
THINGS = {'product': 'the product', 'category': 'the category', 'stadium': 'the court', 'expense': 'an expense',
          'user': 'the staff member', 'table': 'the table', 'client': 'the client account'}


def load_records(rows):
    """Fetch every record the page mentions in one query per type."""
    from app.models import (POSSession, Booking, Order, Product, Category, Stadium, Expense, ManualDebt,
                            User, CourtBlock, POSOrder, POSOrderItem, Table, RegularBooking, Client)
    models = {'pos_session': POSSession, 'booking': Booking, 'order': Order, 'product': Product,
              'category': Category, 'stadium': Stadium, 'expense': Expense, 'manual_debts': ManualDebt,
              'user': User, 'court_block': CourtBlock, 'pos_order': POSOrder, 'table': Table,
              'regular_booking': RegularBooking, 'client': Client}
    wanted = {}
    for r in rows:
        if r.entity_type in models and r.entity_id:
            wanted.setdefault(r.entity_type, set()).add(r.entity_id)
    found = {}
    for kind, ids in wanted.items():
        model = models[kind]
        for obj in model.query.filter(model.id.in_(ids)).all():
            found[(kind, obj.id)] = obj
    item_ids = {(r.after_values or {}).get('item') for r in rows if isinstance(r.after_values, dict)} - {None}
    items = {i.id: i for i in POSOrderItem.query.filter(POSOrderItem.id.in_(item_ids)).all()} if item_ids else {}
    return found, items


def describe_all(rows, lang):
    found, items = load_records(rows)
    return {r.id: describe(r, lang, found, items) for r in rows}


def describe(log, lang, found, items):
    t = lambda text: translate(text, lang)
    obj = found.get((log.entity_type, log.entity_id))
    after = log.after_values if isinstance(log.after_values, dict) else {}
    before = log.before_values if isinstance(log.before_values, dict) else {}
    values = dict(actor=log.user.username if log.user else t('A guest'), record=record_name(log, obj, lang))
    action = log.action or ''

    def say(template, **extra):
        return t(template).format(**values, **extra)

    details = []
    if action == 'Staff signed in':
        text = say('{actor} signed in')
    elif action == 'Settings updated':
        text = say('{actor} updated the website settings')
    elif action == 'Session started':
        kind = getattr(obj, 'session_type', None)
        if kind == 'person':
            text = say('{actor} opened a tab for {name}', name=obj.customer_name)
        elif kind == 'stadium' and obj.booking_id:
            text = say("{actor} started {name}'s booked session on {court}", name=obj.customer_name or '', court=obj.location_snapshot)
        elif kind == 'stadium':
            text = say('{actor} started a court session on {court}', court=obj.location_snapshot)
        else:
            text = say('{actor} started a quick sale')
    elif action == 'Item added':
        if after.get('product'):
            text = say('{actor} added {quantity} × {product} to {record}', quantity=after.get('quantity', 1), product=after['product'])
        else:
            text = say('{actor} added an item to {record}')
    elif action == 'Item quantity changed':
        if after.get('product'):
            text = say('{actor} changed {product} on {record} from {old} to {new}', product=after['product'],
                       old=before.get('quantity', '?'), new=after.get('quantity', '?'))
        else:
            text = say('{actor} changed an item quantity on {record}')
    elif action == 'Items given free':
        product = after.get('product') or item_name(items.get(after.get('item')), lang)
        free = after.get('free', 0)
        text = say('{actor} gave {quantity} × {product} free on {record}', quantity=free, product=product) if free \
            else say('{actor} removed the free units of {product} on {record}', product=product)
    elif action == 'Item discount applied':
        item = items.get(after.get('item'))
        product = after.get('product') or item_name(item, lang)
        currency = after.get('currency') or getattr(item, 'currency', None) or 'IQD'
        if after.get('kind'):
            text = say('{actor} gave {product} a discount of {discount} on {record}', product=product,
                       discount=discount_text(after['kind'], after.get('value', 0), currency))
        else:
            text = say('{actor} removed the discount on {product} on {record}', product=product)
    elif action in ('Discount applied', 'Quick sale discount'):
        if after.get('kind'):
            text = say('{actor} applied a discount of {discount} to {record}',
                       discount=discount_text(after['kind'], after.get('value', 0), after.get('currency', 'IQD')))
        else:
            text = say('{actor} applied a discount to {record}')
    elif action == 'Play finished':
        text = say('{actor} stopped the timer on {record}')
    elif action == 'Regular booking created':
        text = say('{actor} set up a weekly regular booking: {record}')
    elif action == 'Regular booking stopped':
        text = say('{actor} stopped the weekly regular booking: {record}')
    elif action == 'Weekly booking reserved':
        text = say('Next week was reserved automatically: {record}')
    elif action == 'Booked time ended':
        text = say('{record}: the booked time ended and the timer stopped automatically')
    elif action == 'Booking start declined':
        text = say('{actor} dismissed the start reminder for {record}')
    elif action == 'Bill finalized':
        amounts = amounts_text(after, log.amount)
        if log.payment_method == 'debt':
            text = say('{actor} closed {record} and put {amounts} on debt', amounts=amounts)
        elif log.payment_method == 'account':
            text = say("{actor} saved {record} to {name}'s account ({amounts})", amounts=amounts,
                       name=getattr(obj, 'customer_name', '') or '')
        else:
            text = say('{actor} closed {record}: {amounts} paid by {method}', amounts=amounts, method=t(log.payment_method or 'cash'))
    elif action == 'Bill customer updated':
        text = say('{actor} updated the customer details on {record}')
    elif action == 'Preparation status changed':
        status = getattr(obj, 'status', None)
        text = say('{actor} moved an order on {record} to “{status}”', status=t(status)) if status \
            else say('{actor} moved an order on {record} to the next stage')
    elif action == 'Open bill voided':
        text = say('{actor} voided {record}')
    elif action == 'Bill refunded':
        text = say('{actor} refunded {record} ({amounts})', amounts=amounts_text(after, log.amount))
    elif action == 'Booking requested':
        text = say('{actor} requested {record}')
    elif action == 'Booking updated':
        text = say('{actor} edited {record}')
    elif action.startswith('Booking '):
        verb = {'confirm': '{actor} approved {record}', 'reject': '{actor} declined {record}',
                'cancel': '{actor} cancelled {record}', 'request_cancel': '{actor} asked to cancel {record}',
                'restore': '{actor} restored {record}', 'complete': '{actor} marked {record} as completed',
                'archive': '{actor} archived {record}'}.get(action.split(' ', 1)[1])
        text = say(verb) if verb else say('{actor} changed {record}')
    elif action == 'Order requested':
        text = say('{actor} placed {record}')
    elif action == 'Order status changed':
        text = say('{actor} moved {record} from “{old}” to “{new}”', old=t(before.get('status', '')), new=t(after.get('status', '')))
    elif action == 'Order payment':
        text = say('{actor} recorded a {method} payment of {amount} on {record}', method=t(log.payment_method or 'cash'),
                   amount=money_fmt(log.amount or 0, after.get('currency', 'IQD')))
    elif action == 'Order cancelled':
        text = say('{actor} cancelled {record}')
    elif action == 'Client account opened':
        text = say('{actor} opened a client account for {name}', name=after.get('name', ''))
    elif action == 'Client account updated':
        text = say('{actor} edited the client account {record}')
        details = field_changes('client', before, after, False, obj, lang)
    elif action == 'Client account paid':
        code = after.get('currency', 'IQD')
        text = say('{actor} received {amount} ({method}) from {record}', method=t(log.payment_method or 'cash'),
                   amount=money_fmt(log.amount or 0, code))
        if 'still_owed' in after:
            details = [dict(label=t('Still owes'), old=None, new=money_fmt(after['still_owed'], code))]
    elif action == 'Manual debt created':
        text = say('{actor} recorded {record}')
    elif action == 'Debt collected':
        text = say('{actor} collected {amount} ({method}) from {record}', method=t(log.payment_method or 'cash'),
                   amount=money_fmt(log.amount or 0, after.get('currency') or getattr(obj, 'currency', 'IQD')))
    elif action == 'Stock adjusted':
        delta = int(after.get('delta', 0) or 0)
        text = say('{actor} added {quantity} units to the stock of {record}', quantity=delta) if delta >= 0 \
            else say('{actor} removed {quantity} units from the stock of {record}', quantity=-delta)
    elif action == 'Maintenance block added':
        text = say('{actor} blocked {record} for maintenance')
    elif action == 'Maintenance block removed':
        text = say('{actor} removed the maintenance block on {record}')
    elif action == 'Barcode regenerated':
        text = say('{actor} made a new barcode for {record}')
    elif action == 'Record deleted':
        values['thing'] = t(THINGS.get(log.entity_type, 'a record'))
        text = say('{actor} deleted {thing} “{name}”', name=after.get('name', ''))
    elif action in ('Record created', 'Record updated', 'Record archived'):
        values['thing'] = t(THINGS.get(log.entity_type, 'a record'))
        template = {'Record created': '{actor} added {thing} {record}', 'Record updated': '{actor} updated {thing} {record}',
                    'Record archived': '{actor} archived {thing} {record}'}[action]
        text = say(template)
        if action != 'Record archived':
            details = field_changes(log.entity_type, before, after, action == 'Record created', obj, lang)
    else:
        text = say('{actor}: {action} — {record}', action=t(action))
    return dict(text=text, details=details, reason=log.note or '')


def record_name(log, obj, lang):
    t = lambda text: translate(text, lang)
    kind = log.entity_type
    if obj is None:
        return t('a deleted record') if log.entity_id else ''
    if kind == 'pos_session':
        return bill_name(obj, lang)
    if kind == 'pos_order':
        return bill_name(obj.session, lang) if obj.session else t('a deleted record')
    if kind == 'booking':
        when = clock_of(_local(obj.starts_at), lang, True) if obj.starts_at else ''
        court = obj.stadium.name if obj.stadium else ''
        return t('the booking for {name} on {court}, {when}').format(name=obj.customer_name, court=court, when=when)
    if kind == 'order':
        return t('website order VP-{ref} from {name}').format(ref=(obj.reference or '')[:10].upper(), name=obj.customer_name)
    if kind == 'client':
        return obj.name
    if kind == 'manual_debts':
        return t('a debt of {amount} for {name}').format(amount=money_fmt(obj.amount, obj.currency or 'IQD'), name=obj.name or '—')
    if kind == 'product':
        return obj.get_name(lang) if hasattr(obj, 'get_name') else obj.name_en
    if kind == 'category':
        return obj.get_name(lang) if hasattr(obj, 'get_name') else obj.name_en
    if kind == 'expense':
        return f'“{t(obj.category)}” ({money_fmt(obj.amount, obj.currency or "IQD")})'
    if kind == 'user':
        return obj.username
    if kind == 'regular_booking':
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        from app.i18n import clock
        return t('{name}, every {day} at {time} on {court}').format(name=obj.customer_name, day=t(days[obj.weekday]),
            time=clock(obj.hour, 0, lang), court=obj.stadium.name if obj.stadium else '')
    if kind == 'court_block':
        return obj.court.name if getattr(obj, 'court', None) else t('a court')
    return getattr(obj, 'name', None) or f'#{obj.id}'


def bill_name(bill, lang):
    t = lambda text: translate(text, lang)
    if bill.session_type == 'person':
        return t("{name}'s tab").format(name=bill.customer_name)
    if bill.session_type == 'stadium':
        who = f' ({bill.customer_name})' if bill.customer_name else ''
        return t('the {court} session').format(court=bill.location_snapshot) + who
    return t('quick sale VP-{ref}').format(ref=(bill.reference or '')[:10].upper())


def item_name(item, lang):
    if not item:
        return translate('an item', lang)
    snap = item.snapshot or {}
    return snap.get('name_' + lang) or snap.get('name_en') or translate('an item', lang)


def discount_text(kind, value, currency):
    return f'{value}%' if kind == 'percentage' else money_fmt(int(value or 0), currency or 'IQD')


def amounts_text(after, fallback):
    parts = [money_fmt(after[c], c) for c in CURRENCIES if isinstance(after.get(c), int) and after[c]]
    return ' + '.join(parts) if parts else money_fmt(fallback or 0, 'IQD')


def field_changes(kind, before, after, created, obj, lang):
    """Readable 'Field: old → new' lines, only for fields that actually changed."""
    t = lambda text: translate(text, lang)
    labels = field_labels()
    currency = after.get('currency') or getattr(obj, 'currency', None) or 'IQD'
    lines = []
    for key, new in after.items():
        if key in HIDDEN_FIELDS:
            continue
        old = before.get(key)
        blank = lambda v: v in (None, '', 'None')
        if not created and (str(old) == str(new) or (blank(old) and blank(new))):
            continue
        if created and new in ('', 'None', None, 'False'):
            continue
        show = lambda v: pretty(key, v, currency if key in MONEY_FIELDS else 'IQD', lang)
        lines.append(dict(label=t(labels.get(key, key.replace('_', ' ').capitalize())),
                          old=None if created else show(old), new=show(new)))
    return lines


def pretty(key, value, currency, lang):
    t = lambda text: translate(text, lang)
    if value in (None, 'None', ''):
        return '—'
    if value in ('True', True):
        return t('Yes')
    if value in ('False', False):
        return t('No')
    if key in MONEY_FIELDS | IQD_FIELDS:
        try:
            return money_fmt(int(value), currency)
        except (TypeError, ValueError):
            return str(value)
    if key == 'currency':
        return t({'IQD': 'Dinar (IQD)', 'USD': 'Dollar ($)'}.get(value, value))
    if key in ('category', 'payment_method', 'role'):
        return t(value)
    return str(value)


_labels = None


def field_labels():
    global _labels
    if _labels is None:
        from app.routes.admin import MODULES
        _labels = {name: label for model, permission, title, fields in MODULES.values() for name, label, kind, req in fields}
    return _labels


def _local(value):
    from app.services.core import local
    return local(value)
