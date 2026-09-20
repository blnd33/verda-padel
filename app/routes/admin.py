import csv
import io
import secrets
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit
from PIL import Image, UnidentifiedImageError
from flask import Blueprint, request, render_template, redirect, abort, current_app, send_file, flash
from flask_login import current_user
from app import db
from app.models import *
from app.services import core
from app.security import require, permitted, PERMISSIONS, landing

admin=Blueprint('admin',__name__,url_prefix='/admin')

# Shared form descriptions keep validation and management screens consistent.
MODULES={
 'courts':(Stadium,'courts','Courts',[('name','Name','text',True),('description','Description','textarea',False),('location','Location','text',False),('price_per_hour','Hourly rate','number',False),('is_active','Active','checkbox',False),('show_in_booking','Public booking','checkbox',False),('show_in_pos','Cashier visibility','checkbox',False),('image_url','Image','image',False)]),
 'tables':(Table,'tables','Tables',[('name','Name','text',True),('capacity','Capacity','number',True),('is_active','Active','checkbox',False)]),
 'products':(Product,'products','Products',[(f'name_{lang}',f'Name ({lang})','text',lang=='en') for lang in ['en','ar']]+[(f'description_{lang}',f'Description ({lang})','textarea',False) for lang in ['en','ar']]+[('category_id','Category','category',False),('cost_price','Cost price','number',True),('price','Selling price','number',True),('stock','Opening stock','number',True),('track_stock','Track stock','checkbox',False),('low_stock_threshold','Low stock threshold','number',True),('is_active','Active','checkbox',False),('show_in_website','Website visibility','checkbox',False),('show_in_pos','Cashier visibility','checkbox',False),('featured','Featured product','checkbox',False),('barcode','Barcode','text',False),('image','Image','image',False)]),
 'categories':(Category,'products','Categories',[(f'name_{lang}',f'Name ({lang})','text',lang=='en') for lang in ['en','ar']]+[(f'description_{lang}',f'Description ({lang})','textarea',False) for lang in ['en','ar']]+[('is_active','Active','checkbox',False),('show_on_website','Website visibility','checkbox',False),('show_on_pos','Cashier visibility','checkbox',False)]),
 'expenses':(Expense,'expenses','Expenses',[('date','Date','date',True),('category','Category','expense_category',True),('amount','Amount','number',True),('description','Description','textarea',False),('payment_method','Method','method',True),('reference_number','Reference','text',False)]),
 'staff':(User,'staff','Staff & permissions',[('username','Username','text',True),('email','Email','email',True),('password','Password','password',False),('role','Role','role',True),('is_active','Active','checkbox',False)])
}

def authorize(permission):
    if not current_user.is_authenticated or not current_user.allowed(permission):
        abort(403)

def safe_admin_next(target):
    """Only ever return to a path inside the workspace, so a posted 'next' cannot
    be used to bounce a signed-in staff member somewhere else."""
    if not target or not target.startswith('/admin/') or target.startswith('//') or '\\' in target:
        return None
    return target

def safe_image(file):
    if not file or not file.filename:
        return None
    try:
        raw=file.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:
            raise core.RuleError('Image is too large.')
        with Image.open(io.BytesIO(raw)) as img:
            if img.format not in ['JPEG','PNG','WEBP'] or img.width*img.height>25000000:
                raise core.RuleError('Use a PNG, JPEG or WebP image under 25 megapixels.')
            img.verify()
        with Image.open(io.BytesIO(raw)) as img:
            img=img.convert('RGBA')
            img.thumbnail((1800,1800))
            folder=Path(current_app.static_folder)/'uploads'
            folder.mkdir(exist_ok=True)
            filename=secrets.token_hex(20)+'.webp'
            img.save(folder/filename,'WEBP',quality=88)
        return '/static/uploads/'+filename
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise core.RuleError('Choose a valid image file.')

VIDEO_LIMIT=40*1024*1024
MEDIA_PANELS={'hero':'Homepage hero','login':'Staff sign-in panel'}

def safe_video(file):
    if not file or not file.filename:
        return None
    raw=file.read(VIDEO_LIMIT+1)
    if len(raw)>VIDEO_LIMIT:
        raise core.RuleError('Video is too large. Keep it under 40MB.')
    if raw[4:8]==b'ftyp':
        extension='mp4'
    elif raw[:4]==b'\x1a\x45\xdf\xa3':
        extension='webm'
    else:
        raise core.RuleError('Use an MP4 or WebM video.')
    folder=Path(current_app.static_folder)/'uploads'
    folder.mkdir(exist_ok=True)
    filename=secrets.token_hex(20)+'.'+extension
    (folder/filename).write_bytes(raw)
    return '/static/uploads/'+filename

def date_range():
    today=core.business_date()
    period=request.args.get('period','today')
    starts={'today':today,'yesterday':today-timedelta(days=1),'week':today-timedelta(days=6),
            'month':today.replace(day=1),'all':date(2000,1,1)}
    try:
        start=date.fromisoformat(request.args['start']) if request.args.get('start') else starts.get(period,today)
        end=date.fromisoformat(request.args['end']) if request.args.get('end') else today-timedelta(days=1) if period=='yesterday' else today
    except ValueError:
        raise core.RuleError('Choose a valid date range.')
    if end<start:
        raise core.RuleError('Choose a valid date range.')
    return start,end

@admin.get('')
@admin.get('/')
@require('dashboard')
def dashboard():
    today=core.business_date()
    summary=core.reports(today,today)
    return render_template('admin/dashboard.html',title='Overview',summary=summary,
        recent_bookings=Booking.query.order_by(Booking.created_at.desc()).limit(6).all() if permitted('bookings') else [],
        recent_orders=Order.query.order_by(Order.created_at.desc()).limit(5).all() if permitted('orders') else [],
        pending=Booking.query.filter_by(status='pending').count(),
        cancellation_count=Booking.query.filter_by(status='pending_cancel').count(),
        low_stock=Product.query.filter(Product.track_stock.is_(True),Product.stock<=Product.low_stock_threshold,Product.is_active.is_(True)).count(),
        activity=ActivityLog.query.order_by(ActivityLog.id.desc()).limit(6).all())

@admin.route('/<module>',methods=['GET','POST'])
@admin.route('/<module>/<int:record_id>/edit',methods=['GET','POST'])
def manage(module,record_id=None):
    if module not in MODULES:
        abort(404)
    model,permission,title,fields=MODULES[module]
    authorize(permission)
    if module=='staff' and current_user.role!='super_admin':
        abort(403)
    record=db.get_or_404(model,record_id) if record_id else None
    if request.method=='POST':
        original = {f:getattr(record,f,None) for f,label,kind,req in fields if kind not in ['password','image']} if record else {}
        if record and request.form.get('action')=='archive':
            if module=='staff':
                guard_staff(record,False,record.role)
                record.session_version+=1
            if hasattr(record,'is_active'):
                record.is_active=False
            if hasattr(record,'archived'):
                record.archived=True
            if hasattr(record,'voided'):
                record.voided=True
            core.audit('Record archived',record,core.text_value(request.form.get('reason'),True))
            return redirect('/admin/'+module)
        data={}
        for field,label,kind,required in fields:
            if kind=='image':
                image=safe_image(request.files.get(field))
                if image:
                    data[field]=image
                continue
            value=request.form.get(field)
            if module=='products' and field=='stock' and record:
                continue
            if kind=='checkbox':
                data[field]=value=='on'
            elif kind=='number':
                data[field]=None if not value and not required else core.integer(value,1 if field in ['amount','capacity'] else 0)
            elif kind=='date':
                try:
                    data[field]=date.fromisoformat(value)
                except (ValueError,TypeError):
                    raise core.RuleError('Choose a valid date.')
            elif kind=='category':
                data[field]=core.integer(value,1) if value else None
                if data[field] and not db.session.get(Category,data[field]):
                    raise core.RuleError('Choose a valid category.')
            elif kind=='method':
                if value not in ['cash','card']:
                    raise core.RuleError('Choose a valid payment method.')
                data[field]=value
            elif kind=='role':
                if value not in ['admin','super_admin']:
                    raise core.RuleError('Choose a valid role.')
                data[field]=value
            elif kind=='expense_category':
                if value not in Expense.get_categories():
                    raise core.RuleError('Choose a valid category.')
                data[field]=value
            else:
                data[field]=core.text_value(value,required,1000 if kind=='textarea' else 100)
        if module=='staff':
            if current_user.role!='super_admin':
                abort(403)
            if record:
                guard_staff(record,data['is_active'],data['role'])
            data['username']=data['username'].lower()
            data['email']=data['email'].lower()
            if '@' not in data['email']:
                raise core.RuleError('Enter a valid email address.')
            password=data.pop('password')
            if (not record or password) and len(password)<12:
                raise core.RuleError('Use a password with at least 12 characters.')
        if module=='products':
            barcode=data.get('barcode','')
            if barcode and (len(barcode)>48 or not barcode.isascii() or not barcode.isprintable()):
                raise core.RuleError('Use a printable ASCII barcode up to 48 characters.')
            data['barcode']=barcode.upper() if barcode else ('VP'+secrets.token_hex(6).upper())
        creating=record is None
        record=record or model()
        for key,value in data.items():
            setattr(record,key,value)
        if module=='staff':
            if password:
                record.set_password(password)
            record.permissions=[p for p in request.form.getlist('permissions') if p in PERMISSIONS]
            record.sync_role_flags()
            record.session_version=(record.session_version or 0)+1
        if module=='expenses':
            record.created_by=record.created_by or core.actor()
        db.session.add(record)
        db.session.flush()
        if module=='products' and creating and record.stock:
            qty=record.stock
            record.stock=0
            core.stock_change(record,qty,'Opening stock',record)
        # Store dates as strings in JSON audit history; passwords are never logged.
        before={k:str(v) for k,v in original.items()}
        after={k:str(v) for k,v in data.items()}
        reason=core.text_value(request.form.get('reason'),True) if not creating else ''
        core.audit('Record created' if creating else 'Record updated',record,reason,before,after)
        return redirect('/admin/'+module)
    query=model.query
    q=request.args.get('q','').strip()
    if q:
        name='name_en' if module in ['products','categories'] else 'username' if module=='staff' else 'description' if module=='expenses' else 'name'
        query=query.filter(getattr(model,name).ilike('%'+q+'%'))
    if module=='expenses':
        if request.args.get('start') or request.args.get('end'):
            start,end=date_range()
            query=query.filter(Expense.date.between(start,end))
        if request.args.get('category'):
            query=query.filter_by(category=request.args['category'])
        if request.args.get('method'):
            query=query.filter_by(payment_method=request.args['method'])
        if request.args.get('status') in ['active','void']:
            query=query.filter_by(voided=request.args['status']=='void')
    rows=query.order_by(model.id.desc()).paginate(page=request.args.get('page',1,type=int),per_page=20)
    return render_template('admin/manage.html',title=title,module=module,fields=fields,record=record,rows=rows,
        categories=Category.query.all(),expense_categories=Expense.get_categories())

def guard_staff(record,active,role):
    if record.role=='super_admin' and record.is_active and (not active or role!='super_admin'):
        if User.query.filter_by(role='super_admin',is_active=True).count()<=1:
            raise core.RuleError('The last active super administrator must be preserved.')

@admin.get('/bookings')
def bookings():
    authorize('cancellations' if request.args.get('status')=='pending_cancel' else 'bookings')
    query=Booking.query
    for field in ['status','stadium_id']:
        if request.args.get(field):
            query=query.filter(getattr(Booking,field)==request.args[field])
    if request.args.get('date'):
        try:
            query=query.filter_by(business_day=date.fromisoformat(request.args['date']))
        except ValueError:
            raise core.RuleError('Choose a valid date.')
    q=request.args.get('q','').strip()
    if q:
        query=query.filter(db.or_(Booking.customer_name.ilike('%'+q+'%'),Booking.customer_phone.ilike('%'+q+'%'),Booking.reference.ilike('%'+q+'%')))
    return render_template('admin/bookings.html',title='Bookings',rows=query.order_by(Booking.starts_at.desc()).paginate(page=request.args.get('page',1,type=int),per_page=20),courts=Stadium.query.all())

@admin.route('/bookings/new',methods=['GET','POST'])
@require('bookings')
def new_booking():
    if request.method=='POST':
        b=core.create_booking(request.form,public=False)
        return redirect(f'/admin/bookings/{b.id}')
    return render_template('admin/booking_edit.html',title='New booking',record=None,courts=Stadium.query.filter_by(is_active=True).all())

@admin.route('/bookings/<int:record_id>',methods=['GET','POST'])
def booking_detail(record_id):
    record=db.get_or_404(Booking,record_id)
    if request.method=='POST':
        action=request.form.get('action')
        authorize('cancellations' if action in ['cancel','restore','request_cancel','reject'] else 'bookings')
        if action=='edit':
            core.create_booking(request.form,public=False,existing=record)
        else:
            core.decide_booking(record,action,request.form.get('reason',''))
        return redirect(safe_admin_next(request.form.get('next')) or f'/admin/bookings/{record.id}')
    if not (permitted('bookings') or (permitted('cancellations') and record.status=='pending_cancel')):
        abort(403)
    return render_template('admin/booking_edit.html',title='Booking details',record=record,courts=Stadium.query.all())

@admin.get('/orders')
@require('orders')
def orders():
    query=Order.query
    if request.args.get('status'):
        query=query.filter_by(status=request.args['status'])
    q=request.args.get('q','')
    if q:
        query=query.filter(db.or_(Order.customer_name.ilike('%'+q+'%'),Order.customer_phone.ilike('%'+q+'%'),Order.reference.ilike('%'+q+'%')))
    return render_template('admin/orders.html',title='Website orders',rows=query.order_by(Order.id.desc()).paginate(page=request.args.get('page',1,type=int),per_page=20))

@admin.route('/orders/<int:record_id>',methods=['GET','POST'])
@require('orders')
def order_detail(record_id):
    order=db.get_or_404(Order,record_id)
    if request.method=='POST':
        action=request.form.get('action')
        old=order.status
        if action=='cancel':
            authorize('cancellations')
            core.cancel_order(order,request.form.get('reason',''))
        elif action=='refund':
            authorize('cancellations')
            core.refund_bill(order,request.form.get('reason',''),request.form.get('restock')=='on')
        elif action=='payment':
            authorize('pos')
            method=request.form.get('method')
            amount=core.integer(request.form.get('amount'),1)
            if order.status=='cancelled' or order.voided or method not in ['cash','card'] or amount>core.balance(order):
                raise core.RuleError('The payment exceeds the remaining balance or is invalid.')
            db.session.add(Payment(order_id=order.id,amount=amount,method=method,user_id=core.actor(),business_day=core.business_date()))
            core.audit('Order payment',order,amount=amount,method=method)
        else:
            target={'confirm':'confirmed','prepare':'processing','deliver':'delivered','collect':'collected'}.get(action)
            transitions={'pending':['confirmed'],'confirmed':['processing'],'processing':['delivered','collected']}
            if order.voided or target not in transitions.get(old,[]) or (target=='collected' and order.delivery_method!='pickup') or (target=='delivered' and order.delivery_method!='delivery'):
                raise core.RuleError('This status change is not allowed.')
            order.status=target
            if target in ['delivered','collected']:
                order.finalized_at=core.now()
                order.business_day=core.business_date()
            core.audit('Order status changed',order,before={'status':old},after={'status':target})
        return redirect(f'/admin/orders/{order.id}')
    return render_template('admin/order.html',title='Order details',record=order)

@admin.route('/inventory',methods=['GET','POST'])
@require('inventory')
def inventory():
    if request.method=='POST':
        p=db.get_or_404(Product,core.integer(request.form.get('product_id'),1))
        qty=core.integer(request.form.get('quantity'),-1000000,1000000)
        reason=core.text_value(request.form.get('reason'),True)
        core.stock_change(p,qty,reason,p)
        core.audit('Stock adjusted',p,reason,after={'delta':qty})
        return redirect('/admin/inventory')
    return render_template('admin/inventory.html',title='Inventory',products=Product.query.order_by(Product.id.desc()).all(),
        rows=StockMovement.query.order_by(StockMovement.id.desc()).paginate(page=request.args.get('page',1,type=int),per_page=30))

@admin.route('/blocks',methods=['GET','POST'])
@require('courts')
def blocks():
    if request.method=='POST':
        if request.form.get('action')=='remove':
            block=db.get_or_404(CourtBlock,core.integer(request.form.get('id'),1))
            core.audit('Maintenance block removed',block,request.form.get('reason',''))
            db.session.delete(block)
        else:
            court=db.get_or_404(Stadium,core.integer(request.form.get('stadium_id'),1))
            try:
                a=core.utc(datetime.fromisoformat(request.form['start']).replace(tzinfo=ZoneInfo(core.settings().timezone)))
                b=core.utc(datetime.fromisoformat(request.form['end']).replace(tzinfo=ZoneInfo(core.settings().timezone)))
            except (KeyError,ValueError):
                raise core.RuleError('Choose a valid date and time.')
            if b<=a or a<core.now():
                raise core.RuleError('Choose a valid date and time.')
            if Booking.query.filter(Booking.stadium_id==court.id,Booking.starts_at<b,Booking.ends_at>a,Booking.status.in_(['pending','confirmed','pending_cancel'])).first() or POSSession.query.filter_by(stadium_id=court.id,status='active').first():
                raise core.RuleError('Resolve existing reservations or sessions before adding maintenance.')
            block=CourtBlock(stadium_id=court.id,starts_at=a,ends_at=b,reason=core.text_value(request.form.get('reason'),True),user_id=core.actor())
            db.session.add(block)
            db.session.flush()
            core.audit('Maintenance block added',block)
        return redirect('/admin/blocks')
    return render_template('admin/blocks.html',title='Court maintenance',courts=Stadium.query.all(),blocks=CourtBlock.query.order_by(CourtBlock.starts_at.desc()).all())

@admin.route('/debts',methods=['GET','POST'])
@require('debts')
def debts():
    if request.method=='POST':
        if request.form.get('action')=='collect':
            d=db.get_or_404(ManualDebt,core.integer(request.form.get('id'),1))
            core.collect_debt(d,request.form.get('amount'),request.form.get('method'))
        else:
            d=ManualDebt(name=core.text_value(request.form.get('name'),True,120),phone=core.text_value(request.form.get('phone'),limit=30),
                amount=core.integer(request.form.get('amount'),1),paid_amount=0,note=core.text_value(request.form.get('note')),
                date=core.business_date(),created_by=core.actor())
            db.session.add(d)
            db.session.flush()
            core.audit('Manual debt created',d)
        return redirect('/admin/debts')
    query=ManualDebt.query
    if request.args.get('status'):
        query=query.filter_by(status=request.args['status'])
    q=request.args.get('q','')
    if q:
        query=query.filter(db.or_(ManualDebt.name.ilike('%'+q+'%'),ManualDebt.phone.ilike('%'+q+'%')))
    if request.args.get('source')=='manual':
        query=query.filter(ManualDebt.session_id.is_(None))
    elif request.args.get('source')=='sale':
        query=query.filter(ManualDebt.session_id.isnot(None))
    if request.args.get('start'):
        a,b=date_range()
        query=query.filter(ManualDebt.date.between(a,b))
    filtered=query.all()
    return render_template('admin/debts.html',title='Debts',rows=query.order_by(ManualDebt.id.desc()).paginate(page=request.args.get('page',1,type=int),per_page=20),
        total=sum(d.amount for d in filtered if d.status!='void'),collected=sum(d.paid_amount for d in filtered if d.status!='void'),outstanding=sum(d.remaining for d in filtered if d.status=='open'))

@admin.get('/reports')
@require('reports')
def reports():
    start,end=date_range()
    summary=core.reports(start,end)
    usage=core.court_usage(start,end)
    if request.args.get('export')=='csv':
        data=[['Metric','IQD / count','Start business date','End business date']]
        for k in ['sales','court_time_sales','refunds','net_sales','collected','cash','card','expenses_total','cogs','gross_margin','operating_result','cash_movement','debt_created','debt_collections','outstanding','quoted','confirmed_value']:
            data.append([k,summary[k],start,end])
        data.append([])
        data.append(['Court','Occupied hours','Available hours estimate','Utilization percent'])
        data.extend([[r['name'],round(r['occupied_hours'],2),round(r['available_hours'],2),round(r['utilization'],2)] for r in usage])
        return csv_response(data,'verda-report.csv')
    return render_template('admin/reports.html',title='Reports',summary=summary,usage=usage,start=start,end=end)

def csv_response(rows,filename):
    output=io.StringIO(newline='')
    writer=csv.writer(output)
    for row in rows:
        writer.writerow([("'"+v) if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r')) else v for v in row])
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')),mimetype='text/csv',as_attachment=True,download_name=filename)

@admin.get('/archive')
@require('receipts')
def archive():
    start,end=date_range()
    records=[]
    for s in POSSession.query.filter(POSSession.business_day.between(start,end),POSSession.status.in_(['paid','debt','stopped'])).all():
        records.append(dict(kind=s.session_type,record=s,total=core.session_quote(s)['total'] if s.status=='stopped' else s.total_amount,method=s.payment_method or 'unpaid',url=f'/pos/receipt/{s.id}'))
    for o in Order.query.filter(Order.business_day.between(start,end)).all():
        methods={p.method for p in o.payments if p.amount>0}
        records.append(dict(kind='website',record=o,total=o.total_price,method=' / '.join(sorted(methods)) if methods else 'unpaid',url=f'/admin/receipt/order/{o.id}'))
    q=request.args.get('q','').lower()
    records=[r for r in records if (not q or q in (r['record'].customer_name or '').lower() or q in (r['record'].customer_phone or '').lower() or q in r['record'].reference.lower())
        and (not request.args.get('type') or r['kind']==request.args['type'])
        and (not request.args.get('method') or archive_method_matches(r,request.args['method']))]
    records.sort(key=lambda r:(r['record'].business_day,r['record'].created_at),reverse=True)
    total=sum(r['total'] for r in records if not r['record'].voided and r['record'].status!='cancelled')
    if request.args.get('export')=='csv':
        authorize('reports')
        return csv_response([['Reference','Type','Business date','Customer','Method','Status','Total IQD','Voided']]+[[r['record'].reference,r['kind'],r['record'].business_day,r['record'].customer_name,r['method'],r['record'].status,r['total'],r['record'].voided] for r in records],'verda-receipts.csv')
    page=max(1,request.args.get('page',1,type=int))
    return render_template('admin/archive.html',title='Receipt archive',records=records[(page-1)*30:page*30],total=total,start=start,end=end,page=page,has_next=len(records)>page*30)


def archive_method_matches(row,method):
    record=row['record']
    if method=='paid':
        return not record.voided and record.status!='cancelled' and core.balance(record)==0 and record.status!='stopped'
    if method=='unpaid':
        return not record.voided and record.status!='cancelled' and (record.status=='stopped' or core.balance(record)>0)
    if method in ['cash','card']:
        return any(p.method==method and p.amount>0 for p in record.payments)
    return row['method']==method

@admin.get('/receipt/order/<int:record_id>')
@require('receipts')
def receipt(record_id):
    return render_template('receipt.html',record=db.get_or_404(Order,record_id),kind='order')

@admin.route('/notifications',methods=['GET','POST'])
def notifications():
    if not current_user.is_authenticated:
        abort(403)
    query=Notification.query.filter(db.or_(Notification.user_id.is_(None),Notification.user_id==current_user.id))
    allowed=[p for p in PERMISSIONS if current_user.allowed(p)]
    query=query.filter(Notification.scope.in_(allowed))
    if request.method=='POST':
        n=query.filter_by(id=core.integer(request.form.get('id'),1)).first_or_404()
        if not db.session.get(NotificationRead,(n.id,current_user.id)):
            db.session.add(NotificationRead(notification_id=n.id,user_id=current_user.id))
        return redirect('/admin/notifications')
    return render_template('admin/notifications.html',title='Notifications',rows=query.order_by(Notification.id.desc()).paginate(page=request.args.get('page',1,type=int),per_page=20),
        read_ids={r.notification_id for r in NotificationRead.query.filter_by(user_id=current_user.id)})

@admin.get('/activity')
@require('dashboard')
def activity():
    return render_template('admin/activity.html',title='Activity',rows=ActivityLog.query.order_by(ActivityLog.id.desc()).paginate(page=request.args.get('page',1,type=int),per_page=30))

@admin.route('/barcodes',methods=['GET','POST'])
@require('products')
def barcodes():
    if request.method=='POST':
        p=db.get_or_404(Product,core.integer(request.form.get('product_id'),1))
        previous=p.barcode
        p.barcode='VP'+secrets.token_hex(6).upper()
        core.audit('Barcode regenerated',p,core.text_value(request.form.get('reason'),True),{'barcode':previous},{'barcode':p.barcode})
        return redirect('/admin/barcodes')
    query=Product.query
    if request.args.get('category'):
        query=query.filter_by(category_id=core.integer(request.args['category'],1))
    products=query.all()
    ids=request.args.getlist('ids')
    if request.args.get('preview'):
        products=[p for p in products if str(p.id) in ids]
    size=request.args.get('size',core.settings().label_size)
    if size not in ['38x25','50x30','60x40']:
        raise core.RuleError('Choose a valid label size.')
    return render_template('admin/barcodes.html',title='Barcode labels',products=products,categories=Category.query.all(),size=size,width=size.split('x')[0],height=size.split('x')[1],preview=bool(request.args.get('preview')))

@admin.get('/barcode/<int:product_id>.svg')
@require('products')
def barcode_image(product_id):
    from barcode import Code128
    p=db.get_or_404(Product,product_id)
    if not p.barcode:
        abort(404)
    out=io.BytesIO()
    Code128(p.barcode).write(out,options={'write_text':True,'quiet_zone':2})
    out.seek(0)
    return send_file(out,mimetype='image/svg+xml',as_attachment=bool(request.args.get('download')),download_name='verda-barcode.svg')

@admin.route('/settings',methods=['GET','POST'])
@require('settings')
def settings_page():
    s=core.settings()
    if request.method=='POST':
        for key in ['site_name','phone','email','address','directions_url','facebook_url','instagram_url','twitter_url']:
            value=core.text_value(request.form.get(key),key=='site_name',300)
            if key.endswith('_url') and value:
                parsed=urlsplit(value)
                if parsed.scheme not in ['http','https'] or not parsed.netloc:
                    raise core.RuleError('Use a complete http or https link.')
            setattr(s,key,value)
        for key,lo,hi in [('opening_hour',0,23),('closing_hour',0,23),('price_per_hour',0,10000000),('evening_rate',0,10000000),('evening_start_hour',0,23),('evening_end_hour',0,23),('discount_percentage',0,100),('discount_start_hour',0,23),('discount_end_hour',0,23),('minimum_minutes',0,1440),('rounding_minutes',1,120),('max_booking_hours',1,12),('booking_days_ahead',1,365),('delivery_fee',0,10000000)]:
            setattr(s,key,core.integer(request.form.get(key),lo,hi))
        for key in ['configured','delivery_enabled','auto_print','demo_mode']:
            setattr(s,key,request.form.get(key)=='on')
        language=request.form.get('default_language')
        if language not in ['ar','en']:
            raise core.RuleError('Choose a valid language.')
        s.default_language=language
        tz=request.form.get('timezone','')
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError,ValueError):
            raise core.RuleError('Choose a valid timezone.')
        s.timezone=tz
        s.receipt_width=core.integer(request.form.get('receipt_width'),58,80)
        label=request.form.get('label_size')
        if label not in ['38x25','50x30','60x40']:
            raise core.RuleError('Choose a valid label size.')
        s.label_size=label
        content=dict(s.content or {})
        for key in ['hero_title','hero_text','about','contact']:
            content[key]={lang:core.text_value(request.form.get(f'{key}_{lang}'),limit=3000) for lang in ['en','ar']}
        for key in ['show_courts','show_products','show_about']:
            content[key]=request.form.get(key)=='on'
        for prefix in MEDIA_PANELS:
            media=safe_image(request.files.get(f'{prefix}_image'))
            if media:
                content[f'{prefix}_image']=media
            video=safe_video(request.files.get(f'{prefix}_video'))
            if video:
                content[f'{prefix}_video']=video
            choice=request.form.get(f'{prefix}_media','illustration')
            if choice not in ['illustration','image','video']:
                raise core.RuleError('Choose a valid display option.')
            if choice!='illustration' and not content.get(f'{prefix}_{choice}'):
                raise core.RuleError('Upload the photo or video before selecting it for display.')
            content[f'{prefix}_media']=choice
        s.content=content
        core.audit('Settings updated',s,request.form.get('reason',''),after={'configured':s.configured,'default_language':s.default_language})
        return redirect('/admin/settings')
    return render_template('admin/settings.html',title='Website & settings',record=s)

@admin.get('/api/pending-counts')
def pending_counts():
    from flask import jsonify
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify(error='Unauthorized'), 401
    latest_booking = Booking.query.filter_by(status='pending').order_by(Booking.id.desc()).first()
    latest_order = Order.query.filter_by(status='pending').order_by(Order.id.desc()).first()
    return jsonify(
        latest_booking_id=latest_booking.id if latest_booking else 0,
        latest_order_id=latest_order.id if latest_order else 0
    )
