from flask import Blueprint, request, render_template, redirect, abort, jsonify
from app import db
from app.models import Stadium,Table,Product,Category,POSSession,POSOrderItem,POSOrder,Booking
from app.security import require, permitted
from app.services import core

pos=Blueprint('pos',__name__,url_prefix='/pos')

@pos.route('',methods=['GET','POST'])
@pos.route('/',methods=['GET','POST'])
@require('pos')
def index():
    if request.method=='POST':
        record=core.start_session(request.form)
        return redirect(f'/pos/session/{record.id}')
    sessions=POSSession.query.filter(POSSession.status.in_(['active','stopped'])).all()
    courts=Stadium.query.filter_by(is_active=True,show_in_pos=True).all()
    return render_template('pos/index.html',title='Cashier',courts=courts,
        tables=Table.query.filter_by(is_active=True).all(),sessions=sessions,occupied={s.occupancy_key:s for s in sessions if s.occupancy_key},
        rate_bands={c.id:court_rate_bands(c) for c in courts},venue_clock=core.local(core.now()),
        bookings=Booking.query.filter_by(status='confirmed').order_by(Booking.starts_at).limit(50).all())

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
            value=core.integer(request.form.get('value'),0,100 if kind=='percentage' else core.session_quote(record)['original']+core.session_quote(record)['products']-core.session_quote(record)['auto_discount'])
            record.discount_kind,record.discount_value=kind,value
            record.discount_note=core.text_value(request.form.get('reason'),True,200)
            core.audit('Discount applied',record,record.discount_note,after={'kind':kind,'value':value})
        elif action=='settle':
            method=request.form.get('method')
            if method=='debt' and not permitted('debts'):
                abort(403)
            core.settle_session(record,method)
            return redirect(f'/pos/receipt/{record.id}') if permitted('receipts') else redirect('/pos')
        elif action=='customer':
            if record.status not in ['active','stopped']:
                raise core.RuleError('This bill is finalized.')
            record.customer_name=core.text_value(request.form.get('customer_name'),limit=100)
            record.customer_phone=core.text_value(request.form.get('customer_phone'),limit=20)
            core.audit('Bill customer updated',record)
        elif action=='preparation':
            order=db.get_or_404(POSOrder,core.integer(request.form.get('order_id'),1))
            status=request.form.get('status')
            transitions={'pending':'preparing','preparing':'ready','ready':'delivered'}
            if order.session_id!=record.id or transitions.get(order.status)!=status or record.status not in ['active','stopped']:
                raise core.RuleError('This status change is not allowed.')
            order.status=status
            core.audit('Preparation status changed',order)
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
    return render_template('pos/session.html',title='Current bill',record=record,quote=core.session_quote(record),
        products=core.product_query('pos').all(),categories=Category.query.filter_by(is_active=True,show_on_pos=True).all())

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
        if method=='debt' and not permitted('debts'):
            abort(403)
        value=core.integer(request.form.get('discount',0),0)
        if value:
            if not permitted('discounts'):
                abort(403)
            kind=request.form.get('discount_kind')
            if kind not in ['percentage','fixed']:
                raise core.RuleError('Choose a valid discount.')
            core.integer(value,0,100 if kind=='percentage' else core.session_quote(record)['products'])
            record.discount_kind,record.discount_value=kind,value
            record.discount_note=core.text_value(request.form.get('reason'),True,200)
            core.audit('Quick sale discount',record,record.discount_note)
        core.settle_session(record,method)
        return redirect(f'/pos/receipt/{record.id}') if permitted('receipts') else redirect('/pos')
    return render_template('pos/quick.html',title='Quick sale',products=core.product_query('pos').all(),categories=Category.query.filter_by(is_active=True,show_on_pos=True).all())

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
    return jsonify(id=p.id,name=p.name_en,price=p.price,stock=p.stock if p.track_stock else None)
