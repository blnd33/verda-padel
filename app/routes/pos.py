from flask import Blueprint, request, render_template, redirect, abort, jsonify
from app import db
from app.models import Stadium,Table,Product,Category,POSSession,POSOrderItem,POSOrder,Booking,Client
from app.security import require, permitted
from app.services import core
from app import money as currency

pos=Blueprint('pos',__name__,url_prefix='/pos')

@pos.route('',methods=['GET','POST'])
@pos.route('/',methods=['GET','POST'])
@require('pos')
def index():
    if request.method=='POST':
        record=core.start_session(request.form)
        return redirect(f'/pos/session/{record.id}')
    sweep()
    clients=client_choices()
    sessions=POSSession.query.filter(POSSession.status.in_(['active','stopped'])).all()
    courts=Stadium.query.filter_by(is_active=True,show_in_pos=True).all()
    return render_template('pos/index.html',title='Cashier',courts=courts,due=core.due_bookings(),
        tabs=sorted((s for s in sessions if s.session_type=='person' and s.status=='active'),key=lambda s:s.start_time,reverse=True),
        closed_tabs=POSSession.query.filter(POSSession.session_type=='person',POSSession.business_day==core.business_date(),
            POSSession.finalized_at.isnot(None)).order_by(POSSession.finalized_at.desc()).limit(30).all(),
        sessions=sessions,occupied={s.occupancy_key:s for s in sessions if s.occupancy_key},
        rate_bands={c.id:court_rate_bands(c) for c in courts},venue_clock=core.local(core.now()),clients=clients,
        bookings=Booking.query.filter_by(status='confirmed').order_by(Booking.starts_at).limit(50).all())

def client_choices():
    """Client accounts the cashier can put a bill on, by name."""
    return Client.query.order_by(Client.name).all() if permitted('clients') else []

def check_settle(method):
    if method=='debt' and not permitted('debts'):
        abort(403)
    if method=='account' and not permitted('clients'):
        abort(403)

def sweep():
    """Stop booked sessions whose time is over. Runs on cashier page loads and on
    the staff screens' regular check, since there is no background worker."""
    stopped=core.stop_finished_bookings()
    reserved=core.keep_regulars_reserved()
    if stopped or reserved:
        db.session.commit()
    return stopped

@pos.get('/api/due')
@require('pos')
def due_api():
    from flask import session
    from app.i18n import translate,clock_of
    stopped=sweep()
    lang=session.get('lang',core.settings().default_language)
    t=lambda text:translate(text,lang)
    return jsonify(
        due=[dict(id=b.id,name=b.customer_name,phone=b.customer_phone,court=b.stadium.name if b.stadium else '',
            starts=clock_of(core.local(b.starts_at),lang),ends=clock_of(core.local(b.ends_at),lang),hours=b.duration_hours,
            regular=bool(b.regular_id),
            title=(t("It's {name}'s time · weekly regular") if b.regular_id else t("It's {name}'s time")).format(name=b.customer_name),
            when=t('{court} · {starts} – {ends} ({hours} h)').format(court=b.stadium.name if b.stadium else '',
                starts=clock_of(core.local(b.starts_at),lang),ends=clock_of(core.local(b.ends_at),lang),hours=b.duration_hours))
            for b in core.due_bookings()],
        stopped=[dict(id=s.id,url=f'/pos/session/{s.id}',
            text=t("{name}'s booked time on {court} has ended. The timer stopped.").format(name=s.customer_name or t('Walk-in'),court=s.location_snapshot))
            for s in stopped],
        labels=dict(accept=t('Accept & start'),decline=t('Decline'),open=t('Open bill'),error=t('Could not start. Check the cashier page.')))

@pos.post('/bookings/<int:booking_id>/start')
@require('pos')
def start_booking(booking_id):
    record=core.start_booking_session(db.get_or_404(Booking,booking_id))
    url=f'/pos/session/{record.id}'
    return jsonify(url=url) if request.is_json else redirect(url)

@pos.post('/bookings/<int:booking_id>/decline')
@require('pos')
def decline_booking(booking_id):
    core.decline_booking_start(db.get_or_404(Booking,booking_id),(request.get_json(silent=True) or request.form).get('reason',''))
    return jsonify(ok=True) if request.is_json else redirect('/pos')

def court_rate_bands(court):
    """The rate windows a cashier is about to bill against, straight from the same
    rules() the pricing engine uses, so the card can never drift from the charge."""
    rule=core.rules(court)
    hour=core.local(core.now()).hour
    day=dict(kind='Daytime',rate=int(rule['rate']),
        start=core.settings().opening_hour,end=rule['evening_start_hour'])
    if not rule['evening_rate'] or rule['evening_rate']==rule['rate']:
        return [dict(day,start=core.settings().opening_hour,end=core.settings().closing_hour,current=True)]
    evening=dict(kind='Evening',rate=int(rule['evening_rate']),
        start=rule['evening_start_hour'],end=rule['evening_end_hour'])
    in_evening=core.within_window(hour,evening['start'],evening['end'])
    return [dict(day,current=not in_evening),dict(evening,current=in_evening)]

@pos.route('/session/<int:session_id>',methods=['GET','POST'])
@require('pos')
def session_detail(session_id):
    record=db.get_or_404(POSSession,session_id)
    if request.method=='POST':
        action=request.form.get('action')
        if action=='add':
            product_id=request.form.get('product_id')
            if request.form.get('barcode'):
                p=Product.query.filter_by(barcode=request.form['barcode'].strip()).first()
                if not p:
                    raise core.RuleError('Barcode not found.')
                product_id=p.id
            core.add_item(record,product_id,request.form.get('quantity',1))
        elif action=='quantity':
            item=db.get_or_404(POSOrderItem,core.integer(request.form.get('item_id'),1))
            core.update_item(record,item,request.form.get('quantity'))
        elif action in ['free','line_discount']:
            if not permitted('discounts'):
                abort(403)
            item=db.get_or_404(POSOrderItem,core.integer(request.form.get('item_id'),1))
            if action=='free':
                core.set_free_units(record,item,request.form.get('free_quantity'),request.form.get('reason'))
            else:
                core.set_line_discount(record,item,request.form.get('kind'),request.form.get('value',0),request.form.get('reason'))
        elif action=='finish':
            core.finish_play(record)
        elif action=='discount':
            if not permitted('discounts'):
                abort(403)
            if record.status not in ['active','stopped']:
                raise core.RuleError('This bill is finalized.')
            kind=request.form.get('kind')
            if kind not in ['percentage','fixed']:
                raise core.RuleError('Choose a valid discount.')
            # A fixed discount comes off one currency's total, entered in that currency.
            code=currency.check(request.form.get('currency','IQD')) if kind=='fixed' else 'IQD'
            if kind=='percentage':
                value=core.integer(request.form.get('value'),0,100)
            else:
                record.discount_kind=None
                quote=core.session_quote(record)
                subtotal=quote['original']-quote['auto_discount']+quote['products'] if code=='IQD' else quote['usd']['products']
                value=currency.parse(request.form.get('value'),code,0,subtotal)
            record.discount_kind,record.discount_value,record.discount_currency=kind,value,code
            record.discount_note=core.text_value(request.form.get('reason'),True,200)
            core.audit('Discount applied',record,record.discount_note,after={'kind':kind,'value':value,'currency':code})
        elif action=='settle':
            method=request.form.get('method')
            check_settle(method)
            core.settle_session(record,method,request.form.get('client_id'))
            return redirect(f'/pos/receipt/{record.id}') if permitted('receipts') else redirect('/pos')
        elif action=='customer':
            if record.status not in ['active','stopped']:
                raise core.RuleError('This bill is finalized.')
            record.customer_name=core.text_value(request.form.get('customer_name'),record.session_type=='person',100)
            record.customer_phone=core.text_value(request.form.get('customer_phone'),limit=20)
            core.audit('Bill customer updated',record)
        elif action=='preparation':
            order=db.get_or_404(POSOrder,core.integer(request.form.get('order_id'),1))
            status=request.form.get('status')
            transitions={'pending':'preparing','preparing':'ready','ready':'delivered'}
            if order.session_id!=record.id or transitions.get(order.status)!=status or record.status not in ['active','stopped']:
                raise core.RuleError('This status change is not allowed.')
            order.status=status
            core.audit('Preparation status changed',order,after={'status':status})
        elif action=='void':
            if not permitted('cancellations'):
                abort(403)
            if record.status not in ['active','stopped']:
                raise core.RuleError('This bill is finalized.')
            reason=core.text_value(request.form.get('reason'),True)
            if any(o.status!='pending' for o in record.orders):
                raise core.RuleError('Prepared goods require settlement and an explicit return.')
            for order in record.orders:
                for item in order.items:
                    core.stock_change(item.product,item.quantity,'Unconsumed bill cancellation',record)
            record.stock_restored=True
            record.status='cancelled'
            record.occupancy_key=None
            record.end_time=core.now()
            core.audit('Open bill voided',record,reason)
            return redirect('/pos')
        elif action=='refund':
            if not permitted('cancellations'):
                abort(403)
            core.refund_bill(record,request.form.get('reason',''),request.form.get('restock')=='on')
        else:
            raise core.RuleError('Choose a valid action.')
        return redirect(f'/pos/session/{record.id}')
    sweep()
    return render_template('pos/session.html',title='Current bill',record=record,quote=core.session_quote(record),
        products=core.product_query('pos').all(),categories=Category.query.filter_by(is_active=True,show_on_pos=True).all(),
        clients=client_choices(),owes=core.client_owes(record.client) if record.client else None)

@pos.route('/quick',methods=['GET','POST'])
@require('pos')
def quick():
    if request.method=='POST':
        product_ids=request.form.getlist('product_id')
        quantities=request.form.getlist('quantity')
        items=[dict(product_id=p,quantity=q) for p,q in zip(product_ids,quantities) if str(q)!='0']
        lines=core.basket_lines(items,'pos')
        record=core.start_session(dict(session_type='quick',customer_name=request.form.get('customer_name'),customer_phone=request.form.get('customer_phone')))
        for p,q in lines:
            core.add_item(record,p.id,q)
        method=request.form.get('method')
        check_settle(method)
        kind=request.form.get('discount_kind')
        code=currency.check(request.form.get('discount_currency','IQD')) if kind=='fixed' else 'IQD'
        raw=str(request.form.get('discount','') or '0').strip()
        if raw not in ['0','0.0','0.00','']:
            if not permitted('discounts'):
                abort(403)
            if kind not in ['percentage','fixed']:
                raise core.RuleError('Choose a valid discount.')
            quote=core.session_quote(record)
            value=core.integer(raw,0,100) if kind=='percentage' else currency.parse(raw,code,0,quote['totals'][code])
            record.discount_kind,record.discount_value,record.discount_currency=kind,value,code
            record.discount_note=core.text_value(request.form.get('reason'),True,200)
            core.audit('Quick sale discount',record,record.discount_note)
        core.settle_session(record,method,request.form.get('client_id'))
        return redirect(f'/pos/receipt/{record.id}') if permitted('receipts') else redirect('/pos')
    return render_template('pos/quick.html',title='Quick sale',products=core.product_query('pos').all(),categories=Category.query.filter_by(is_active=True,show_on_pos=True).all(),
        clients=client_choices())

@pos.get('/receipt/<int:session_id>')
@require('receipts')
def receipt(session_id):
    return render_template('receipt.html',record=db.get_or_404(POSSession,session_id),kind='session')

@pos.get('/scan')
@require('pos')
def scan():
    p=Product.query.filter_by(barcode=request.args.get('barcode')).first()
    if not core.visible_product(p,'pos'):
        abort(404)
    return jsonify(id=p.id,name=p.name_en,price=p.price,currency=p.currency or 'IQD',stock=p.stock if p.track_stock else None)
