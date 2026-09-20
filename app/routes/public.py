from datetime import timedelta
from flask import Blueprint, render_template, request, session, redirect, abort, jsonify
from app import db
from app.models import Stadium, Product, Category, Booking, Order
from app.services import core

main = Blueprint('main', __name__)
booking = Blueprint('booking', __name__, url_prefix='/booking')
store = Blueprint('store', __name__, url_prefix='/store')

@main.get('/')
def home():
    return render_template('home.html', courts=Stadium.query.filter_by(is_active=True,show_in_booking=True).all(),
        products=core.product_query('website').filter(Product.featured.is_(True)).limit(4).all())

@main.get('/language/<lang>')
def language(lang):
    if lang in ['en','ar']:
        session['lang']=lang
    target=request.args.get('next','/')
    if not target.startswith('/') or target.startswith('//') or '\\' in target:
        target='/'
    return redirect(target)

@main.get('/about')
@main.get('/contact')
def information():
    return render_template('information.html', contact=request.path=='/contact')

@main.get('/robots.txt')
def robots():
    return 'User-agent: *\nDisallow: /admin\nDisallow: /pos\nDisallow: /auth\nDisallow: /booking/confirmation\nDisallow: /store/confirmation\n', 200, {'Content-Type':'text/plain'}

@main.get('/sw.js')
def service_worker():
    from flask import current_app, send_from_directory
    response = send_from_directory(current_app.static_folder, 'sw.js')
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response

@booking.route('/',methods=['GET','POST'])
def book():
    s=core.settings()
    if request.method=='POST':
        if not s.configured and not s.demo_mode:
            raise core.RuleError('Booking will open when venue details are confirmed.')
        b=core.create_booking(request.form)
        return redirect('/booking/confirmation/'+b.reference)
    courts=Stadium.query.filter_by(is_active=True,show_in_booking=True).all()
    court_id=request.args.get('court',courts[0].id if courts else None)
    day=request.args.get('date',str(core.business_date()))
    duration=request.args.get('duration','1')
    slots=[]
    hours=list(range(s.opening_hour,24))+list(range(s.closing_hour)) if s.closing_hour<=s.opening_hour else list(range(s.opening_hour,s.closing_hour))
    for hour in hours:
        try:
            court,business_day,a,b,d=core.interval(court_id,day,hour,duration)
            original,discount=core.price_interval(a,d*3600,core.rules(court))
            slots.append(dict(hour=hour,available=True,price=original-discount,original=original,discount=discount,end=core.local(b).strftime('%H:%M'),actual_date=core.local(a).date()))
        except core.RuleError:
            slots.append(dict(hour=hour,available=False))
    return render_template('booking.html',courts=courts,court_id=str(court_id),day=day,duration=str(duration),slots=slots)

@booking.get('/api/availability')
def availability():
    try:
        c,d,a,b,h=core.interval(request.args.get('court'),request.args.get('date'),request.args.get('hour'),request.args.get('duration'))
        original,discount=core.price_interval(a,h*3600,core.rules(c))
        return jsonify(available=True,original=original,discount=discount,total=original-discount,start=a.isoformat()+'Z',end=b.isoformat()+'Z')
    except core.RuleError as e:
        return jsonify(available=False,error=str(e)),422

@booking.get('/confirmation/<reference>')
def confirmation(reference):
    record=Booking.query.filter_by(reference=reference).first_or_404()
    return render_template('confirmation.html',record=record,kind='booking')

@booking.post('/confirmation/<reference>/cancel')
def cancel(reference):
    record=Booking.query.filter_by(reference=reference).first_or_404()
    core.decide_booking(record,'request_cancel',request.form.get('reason',''))
    return redirect('/booking/confirmation/'+reference)

@store.get('/')
def products():
    query=core.product_query('website')
    search=request.args.get('q','').strip()
    if search:
        query=query.filter(db.or_(Product.name_en.ilike('%'+search+'%'),Product.name_ar.ilike('%'+search+'%')))
    if request.args.get('category'):
        query=query.filter(Product.category_id==core.integer(request.args['category'],1))
    return render_template('store.html',products=query.order_by(Product.id.desc()).paginate(page=request.args.get('page',1,type=int),per_page=16),
        categories=Category.query.filter_by(is_active=True,show_on_website=True).all())

@store.get('/product/<int:product_id>')
def product(product_id):
    p=db.session.get(Product,product_id)
    if not core.visible_product(p,'website'):
        abort(404)
    return render_template('product.html',product=p)

@store.route('/cart',methods=['GET','POST'])
def cart():
    cart=session.get('cart',{})
    if request.method=='POST':
        action=request.form.get('action')
        if action=='clear':
            cart={}
        else:
            pid=core.integer(request.form.get('product_id'),1)
            qty=0 if action=='remove' else core.integer(request.form.get('quantity',1),0,999)
            if action=='add':
                qty+=cart.get(str(pid),0)
            if qty:
                core.basket_lines([dict(product_id=pid,quantity=qty)],'website')
                cart[str(pid)]=qty
            else:
                cart.pop(str(pid),None)
        session['cart']=cart
        return redirect('/store/cart')
    lines=[]
    invalid=False
    for pid,qty in cart.items():
        p=db.session.get(Product,int(pid))
        valid=core.visible_product(p,'website') and (not p.track_stock or p.stock>=qty)
        invalid=invalid or not valid
        lines.append(dict(product=p,product_id=pid,quantity=qty,valid=valid,total=p.price*qty if p else 0))
    return render_template('cart.html',lines=lines,total=sum(l['total'] for l in lines),invalid=invalid)

@store.route('/checkout',methods=['GET','POST'])
def checkout():
    cart=session.get('cart',{})
    items=[dict(product_id=k,quantity=v) for k,v in cart.items()]
    if request.method=='POST':
        s=core.settings()
        if not s.configured and not s.demo_mode:
            raise core.RuleError('Checkout will open when venue details are confirmed.')
        order=core.create_order(request.form,items)
        session['cart']={}
        return redirect('/store/confirmation/'+order.reference)
    lines=core.basket_lines(items,'website')
    return render_template('checkout.html',total=sum(p.price*q for p,q in lines))

@store.get('/confirmation/<reference>')
def order_confirmation(reference):
    record=Order.query.filter_by(reference=reference).first_or_404()
    return render_template('confirmation.html',record=record,kind='order')
