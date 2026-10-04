import re
import secrets
from datetime import datetime,timedelta,time
from concurrent.futures import ThreadPoolExecutor
import pytest
from app import db
from app.models import *
from app.services import core

def post(client,path,data=None,key=None):
    return client.post(path,data={**(data or {}),'_operation':key or secrets.token_urlsafe(24)})

def booking_data(app,**overrides):
    with app.app_context():
        day=core.business_date()+timedelta(days=2)
    return dict(stadium_id=1,date=str(day),hour=12,duration=1,customer_name='Fictional guest',customer_phone='+9647000000000',**overrides)

def start(staff,kind='stadium',location_id=1):
    response=post(staff,'/pos',dict(session_type=kind,location_id=location_id,customer_name='Fictional player'))
    assert response.status_code==302,response.get_data(as_text=True)
    return response.location

def test_public_and_staff_screens(app,staff):
    for url in ['/','/booking/','/store/','/store/product/1','/store/cart','/about','/contact','/auth/login','/admin',
        '/admin/bookings','/admin/bookings/new','/admin/orders','/admin/products','/admin/categories',
        '/admin/inventory','/admin/courts','/admin/tables','/admin/staff','/admin/expenses','/admin/debts',
        '/admin/reports','/admin/archive','/admin/activity','/admin/notifications','/admin/barcodes',
        '/admin/barcodes?preview=1&ids=1&price=1','/admin/blocks','/admin/settings','/admin/clients','/pos','/pos/quick']:
        result=staff.get(url)
        assert result.status_code in [200,302],(url,result.status_code,result.get_data(as_text=True))
        if result.status_code==200:
            assert b'Padel House' not in result.data
    for language in ['ar','en']:
        staff.get('/language/'+language)
        result=staff.get('/')
        assert ('dir="rtl"' if language!='en' else 'dir="ltr"') in result.get_data(as_text=True)

def test_booking_conflict_retry_and_private_reference(app,client):
    data=booking_data(app)
    key=secrets.token_urlsafe(24)
    first=post(client,'/booking/',data,key)
    assert first.status_code==302
    assert len(first.location.split('/')[-1])>=32
    assert post(client,'/booking/',data,key).location==first.location
    assert post(client,'/booking/',data).status_code==422
    assert client.get(first.location).status_code==200
    assert client.get('/booking/confirmation/1').status_code==404
    with app.app_context():
        assert Booking.query.count()==1
        assert Notification.query.filter_by(scope='bookings').count()==1

def test_booking_midnight_and_price_forgery(app,client):
    data=booking_data(app)
    data.update(hour=1,final_price=1,discount=99)
    result=post(client,'/booking/',data)
    assert result.status_code==302
    with app.app_context():
        b=Booking.query.one()
        assert b.date==b.business_day+timedelta(days=1)
        assert b.final_price==30000
        assert core.local(b.ends_at).hour==2
    data['duration']=2
    assert post(client,'/booking/',data).status_code==422

def test_invalid_duration_and_inactive(app,client):
    data=booking_data(app)
    for value in [0,-1,25,'1.5','garbage']:
        data['duration']=value
        assert post(client,'/booking/',data).status_code==422
    with app.app_context():
        db.session.get(Stadium,1).is_active=False
        db.session.commit()
    data['duration']=1
    assert post(client,'/booking/',data).status_code==422

def test_cancellation_restores_previous_state(app,staff):
    response=post(staff,'/booking/',booking_data(app))
    assert post(staff,'/admin/bookings/1',{'action':'confirm'}).status_code==302
    assert post(staff,response.location+'/cancel').status_code==302
    with app.app_context():
        assert Booking.query.one().status=='pending_cancel'
    assert post(staff,'/admin/bookings/1',{'action':'restore','reason':'Keep reservation'}).status_code==302
    with app.app_context():
        assert Booking.query.one().status=='confirmed'
    assert post(staff,'/admin/bookings/1',{'action':'cancel','reason':'Guest cancelled'}).status_code==302
    assert post(staff,'/booking/',booking_data(app)).status_code==302

def test_checkout_atomic_stock_fee_and_retry(app,client):
    post(client,'/store/cart',dict(action='add',product_id=1,quantity=2))
    details=dict(customer_name='Demo buyer',customer_phone='+9647000000000',delivery_method='pickup',address='stale address',area='stale area',total_price=1)
    key=secrets.token_urlsafe(24)
    response=post(client,'/store/checkout',details,key)
    assert response.status_code==302
    assert post(client,'/store/checkout',details,key).location==response.location
    assert client.get(response.location).status_code==200
    with app.app_context():
        order=Order.query.one()
        assert order.total_price==24000
        assert order.address is None and order.area is None
        assert db.session.get(Product,1).stock==8
        assert len(order.items)==1
        assert StockMovement.query.count()==1
        assert Payment.query.count()==0
    with client.session_transaction() as session:
        assert not session['cart']

def test_delivery_validation_and_hidden_category(app,client):
    with app.app_context():
        s=core.settings()
        s.delivery_enabled=True
        s.delivery_fee=3500
        db.session.commit()
    post(client,'/store/cart',dict(action='add',product_id=1,quantity=1))
    data=dict(customer_name='Demo',customer_phone='+9647000000000',delivery_method='delivery')
    assert post(client,'/store/checkout',data).status_code==422
    data.update(area='Demo area',address='Fictional address')
    assert post(client,'/store/checkout',data).status_code==302
    with app.app_context():
        assert Order.query.one().total_price==15500
        assert Order.query.one().delivery_fee==3500
        db.session.get(Category,1).show_on_website=False
        db.session.commit()
    assert client.get('/store/product/1').status_code==404
    assert post(client,'/store/cart',dict(action='add',product_id=1,quantity=1)).status_code==422

def test_stock_restore_once(app,staff):
    post(staff,'/store/cart',dict(action='add',product_id=1,quantity=2))
    post(staff,'/store/checkout',dict(customer_name='Demo',customer_phone='+9647000000000',delivery_method='pickup'))
    for _ in range(2):
        assert post(staff,'/admin/orders/1',dict(action='cancel',reason='Cancelled before fulfillment')).status_code==302
    with app.app_context():
        assert db.session.get(Product,1).stock==10
        assert StockMovement.query.filter(StockMovement.quantity>0).count()==1

@pytest.mark.parametrize('seconds,expected',[(3599,30000),(3600,30000),(3601,60000)])
def test_hour_rounding_boundaries(app,seconds,expected):
    with app.test_request_context():
        record=core.start_session(dict(session_type='stadium',location_id=1))
        at=record.start_time+timedelta(seconds=seconds)
        assert core.session_quote(record,at)['total']==expected

def test_duplicate_session_finish_freeze_and_payment_retry(app,staff):
    path=start(staff)
    assert post(staff,'/pos',dict(session_type='stadium',location_id=1)).status_code==422
    assert post(staff,path,dict(action='finish')).status_code==302
    with app.app_context():
        s=POSSession.query.one()
        frozen=core.session_quote(s)['total']
        assert core.session_quote(s,core.now()+timedelta(hours=5))['total']==frozen
        assert s.occupancy_key is None
    assert post(staff,path,dict(action='add',product_id=1,quantity=1)).status_code==302
    key=secrets.token_urlsafe(24)
    paid=post(staff,path,dict(action='settle',method='cash'),key)
    assert paid.status_code==302
    assert post(staff,path,dict(action='settle',method='cash'),key).location==paid.location
    assert post(staff,path,dict(action='settle',method='cash')).status_code==302
    assert staff.get(paid.location).status_code==200
    with app.app_context():
        assert Payment.query.count()==1
        assert Payment.query.one().amount==42000

def test_person_tab_has_no_court_charge_and_discounts_once(app,staff):
    path=start(staff,'person')
    post(staff,path,dict(action='add',product_id=1,quantity=2))
    assert post(staff,path,dict(action='discount',kind='percentage',value=25,reason='Demo discount')).status_code==302
    post(staff,path,dict(action='settle',method='card'))
    with app.app_context():
        s=POSSession.query.one()
        assert s.play_time_price==0
        assert s.manual_discount==6000
        assert s.total_amount==18000
        assert Payment.query.one().amount==18000

def test_quick_debt_partial_collection_and_reports(app,staff):
    result=post(staff,'/pos/quick',dict(product_id=[1],quantity=[2],discount=0,method='debt',customer_name='Demo debtor'))
    assert result.status_code==302
    with app.app_context():
        assert POSOrderItem.query.one().quantity==2
        assert Payment.query.count()==0
        assert ManualDebt.query.one().remaining==24000
        day=core.business_date()
        report=core.reports(day,day)['money']['IQD']
        assert report['sales']==24000 and report['collected']==0
    assert post(staff,'/admin/debts',dict(action='collect',id=1,amount=5000,method='cash')).status_code==302
    assert post(staff,'/admin/debts',dict(action='collect',id=1,amount=20000,method='cash')).status_code==422
    key=secrets.token_urlsafe(24)
    data=dict(action='collect',id=1,amount=19000,method='card')
    post(staff,'/admin/debts',data,key)
    post(staff,'/admin/debts',data,key)
    with app.app_context():
        assert ManualDebt.query.one().remaining==0
        assert Payment.query.count()==2
        report=core.reports(core.business_date(),core.business_date())['money']['IQD']
        assert report['sales']==24000 and report['collected']==24000 and report['outstanding']==0

def test_permissions_and_csrf(app,cashier):
    assert cashier.get('/admin/settings').status_code==403
    assert cashier.get('/admin/reports').status_code==403
    assert cashier.get('/admin/barcode/1.svg').status_code==403
    path=start(cashier,'person')
    assert post(cashier,path,dict(action='discount',kind='fixed',value=1,reason='No permission')).status_code==403
    assert post(cashier,'/admin/products',dict(name_en='forbidden')).status_code==403
    app.config['WTF_CSRF_ENABLED']=True
    assert post(cashier,path,dict(action='finish')).status_code==400

def test_valid_csrf_submission(app,client):
    app.config['WTF_CSRF_ENABLED']=True
    html=client.get('/booking/').get_data(as_text=True)
    csrf=re.search('name="csrf_token" value="([^"]+)"',html).group(1)
    result=post(client,'/booking/',{**booking_data(app),'csrf_token':csrf})
    assert result.status_code==302

def test_notifications_per_user(app,staff,cashier):
    # Two independent clients; Flask fixture clients would otherwise share auth state.
    with app.app_context():
        db.session.add(Notification(type='bookings',scope='bookings',title='Private booking'))
        db.session.commit()
    viewer=app.test_client()
    with viewer.session_transaction() as session:
        session['_user_id']='2';session['staff_version']=1
    assert b'Private booking' not in viewer.get('/admin/notifications').data
    assert post(viewer,'/admin/notifications',dict(id=1)).status_code==404

def test_historical_receipt_and_print_read_only(app,staff):
    response=post(staff,'/pos/quick',dict(product_id=[1],quantity=[1],discount=0,method='cash'))
    assert response.status_code==302
    with app.app_context():
        p=db.session.get(Product,1)
        p.name_en='Changed name';p.price=99999;p.cost_price=999
        core.settings().price_per_hour=99999
        db.session.commit()
    for _ in range(2):
        receipt=staff.get(response.location)
        assert b'Test racket' in receipt.data and b'Changed name' not in receipt.data
        assert b'12,000' in receipt.data
    with app.app_context():
        assert Payment.query.count()==1
        assert core.reports(core.business_date(),core.business_date())['money']['IQD']['cogs']==7000

def test_zero_and_overnight_discount(app):
    with app.app_context():
        s=core.settings()
        s.price_per_hour=0;s.discount_percentage=0
        c=db.session.get(Stadium,1);c.price_per_hour=0
        rule=core.rules(c)
        assert rule['rate']==0 and rule['discount_percentage']==0
        rule.update(rate=30000,discount_percentage=50,discount_start_hour=23,discount_end_hour=2)
        start=datetime(2026,10,1,19,0) # 22:00 Baghdad
        original,discount=core.price_interval(start,4*3600,rule)
        assert original==120000 and discount==45000

def test_linked_booking_not_double_billed(app,staff):
    with app.app_context():
        a=core.now()-timedelta(minutes=20)
        b=Booking(stadium_id=1,customer_name='Demo',customer_phone='+9647000000000',date=core.local(a).date(),
            start_time=core.local(a).time(),end_time=core.local(a+timedelta(hours=1)).time(),duration_hours=1,
            original_price=30000,discount_amount=0,final_price=30000,status='confirmed',reference=core.reference(),
            business_day=core.business_date(),starts_at=a,ends_at=a+timedelta(hours=1),pricing_snapshot=core.rules(db.session.get(Stadium,1)))
        db.session.add(b);db.session.commit()
    r=post(staff,'/pos',dict(session_type='stadium',location_id=1,booking_id=1))
    assert r.status_code==302
    post(staff,r.location,dict(action='settle',method='cash'))
    with app.app_context():
        report=core.reports(core.business_date(),core.business_date())['money']['IQD']
        assert report['sales']==30000 and report['confirmed_value']==30000

def test_concurrent_booking_and_last_stock(app):
    booking=booking_data(app)
    clients=[app.test_client(),app.test_client()]
    for c in clients:c.get('/')
    with ThreadPoolExecutor(2) as pool:
        responses=list(pool.map(lambda c:post(c,'/booking/',booking),clients))
    assert sorted(r.status_code for r in responses)==[302,422]
    with app.app_context():
        db.session.get(Product,1).stock=1
        db.session.commit()
    for c in clients:
        post(c,'/store/cart',dict(action='add',product_id=1,quantity=1))
    data=dict(customer_name='Demo',customer_phone='+9647000000000',delivery_method='pickup')
    with ThreadPoolExecutor(2) as pool:
        responses=list(pool.map(lambda c:post(c,'/store/checkout',data),clients))
    assert sorted(r.status_code for r in responses)==[302,422]
    with app.app_context():
        assert db.session.get(Product,1).stock==0
        assert Order.query.count()==1

def test_throttling_inactive_and_safe_redirect(app,client):
    with app.app_context():
        db.session.get(User,1).is_active=False;db.session.commit()
    result=post(client,'/auth/login?next=https://example.com',dict(username='test-admin',password='Test-only-password!234'))
    assert result.location=='/auth/login'
    for _ in range(7):
        post(client,'/auth/login',dict(username='missing',password='bad'))
    assert post(client,'/auth/login',dict(username='missing',password='bad')).status_code==422
    assert client.get('/language/en?next=//example.com').location=='/'

def test_barcode_exports_and_exclusions(app,staff):
    assert staff.get('/admin/barcode/1.svg').status_code==200
    assert staff.get('/pos/scan?barcode=TEST-001').json['id']==1
    assert 'cost_price' not in staff.get('/pos/scan?barcode=TEST-001').json
    assert staff.get('/admin/reports?export=csv').data.startswith(b'\xef\xbb\xbf')
    # /sw.js is served from the root on purpose: a service worker can only control
    # the paths at or below its own URL, so it cannot live under /static.
    assert staff.get('/sw.js').status_code==200
    for path in ['/training','/tapane/webhook','/manifest.json','/offline','/gaming']:
        assert staff.get(path).status_code==404


def test_person_tab_free_units_and_item_discounts(app,staff):
    assert post(staff,'/pos',dict(session_type='person',customer_name='')).status_code==422
    assert post(staff,'/pos',dict(session_type='table',location_id=1,customer_name='Blnd')).status_code==422
    path=start(staff,'person')
    post(staff,path,dict(action='add',product_id=1,quantity=5))
    with app.app_context():
        item=POSOrderItem.query.one().id
        assert db.session.get(Product,1).stock==5
    # A cashier without the discounts permission cannot give items away.
    cashier=app.test_client()
    with cashier.session_transaction() as session:
        session['_user_id']='2';session['staff_version']=1
    assert post(cashier,path,dict(action='free',item_id=item,free_quantity=1)).status_code==403
    assert post(staff,path,dict(action='free',item_id=item,free_quantity=6)).status_code==422
    assert post(staff,path,dict(action='free',item_id=item,free_quantity=1)).status_code==302
    assert post(staff,path,dict(action='line_discount',item_id=item,kind='percentage',value=10)).status_code==302
    assert post(staff,path,dict(action='discount',kind='fixed',value=3200,reason='Regular')).status_code==302
    with app.app_context():
        q=core.session_quote(POSSession.query.one())
        # 5 × 12,000; one free; 10% off the four paid; 3,200 off the invoice.
        assert (q['products_gross'],q['free_value'],q['line_discounts'],q['products'],q['total'])==(60000,12000,4800,43200,40000)
    assert staff.get(path).status_code==200
    post(staff,path,dict(action='settle',method='cash'))
    assert b'Free' in staff.get('/pos/receipt/1').data
    with app.app_context():
        s=POSSession.query.one()
        assert s.status=='paid' and s.total_amount==40000 and Payment.query.one().amount==40000
        assert db.session.get(Product,1).stock==5
        day=core.business_date()
        full=core.reports(day,day)
        r=full['money']['IQD']
        # The free unit is not revenue but its cost stays in cost of goods.
        assert r['sales']==40000 and r['cogs']==35000
        assert (r['free_units'],r['free_cost'],r['line_discounts'],r['discounts'])==(1,7000,4800,8000)
        assert r['by_type']['person']==40000
        assert full['product_summary'][0]['sales']==43200 and full['product_summary'][0]['free']==1

def test_reducing_quantity_keeps_free_units_within_it(app,staff):
    path=start(staff,'person')
    post(staff,path,dict(action='add',product_id=1,quantity=3))
    post(staff,path,dict(action='free',item_id=1,free_quantity=3))
    post(staff,path,dict(action='quantity',item_id=1,quantity=2))
    post(staff,path,dict(action='line_discount',item_id=1,kind='fixed',value=1))
    with app.app_context():
        item=db.session.get(POSOrderItem,1)
        assert item.free_quantity==2 and item.discount_value==0
        assert core.session_quote(POSSession.query.one())['total']==0

def test_venue_map_coordinates_and_directions(app,staff):
    assert b'find-us' not in staff.get('/').data
    with app.app_context():
        form={k:getattr(core.settings(),k) for k in ['site_name','opening_hour','closing_hour','price_per_hour','evening_rate',
            'evening_start_hour','evening_end_hour','discount_percentage','discount_start_hour','discount_end_hour','minimum_minutes',
            'rounding_minutes','max_booking_hours','booking_days_ahead','delivery_fee','receipt_width','timezone','default_language','label_size']}
    form={k:('' if v is None else v) for k,v in form.items()}
    bad=post(staff,'/admin/settings',{**form,'map_coordinates':'somewhere nice'})
    assert bad.status_code==422
    ok=post(staff,'/admin/settings',{**form,'map_coordinates':'36.8669, 42.9503'})
    assert ok.status_code==302,ok.get_data(as_text=True)[:400]
    with app.app_context():
        assert core.settings().map_coordinates=='36.866900,42.950300'
    page=staff.get('/')
    html=page.get_data(as_text=True)
    assert 'https://www.google.com/maps?q=36.866900,42.950300&amp;z=16&amp;output=embed' in html
    assert 'https://www.google.com/maps/dir/?api=1&amp;destination=36.866900,42.950300' in html
    assert "frame-src 'self' https://www.google.com" in page.headers['Content-Security-Policy']
    assert 'find-us' in staff.get('/contact').get_data(as_text=True)

def test_times_use_twelve_hour_clock(app,staff):
    from app.i18n import clock
    assert [clock(h) for h in [0,9,12,13,23]]==['12:00 AM','9:00 AM','12:00 PM','1:00 PM','11:00 PM']
    assert clock(16,short=True)=='4 PM' and clock(20,30,'ar')=='8:30 م'
    html=staff.get('/booking/').get_data(as_text=True)
    assert '9:00 AM' in html and '13:00' not in html
    assert 'AM' in staff.get('/').get_data(as_text=True)
    assert '9:00 AM' in staff.get('/admin/settings').get_data(as_text=True)

def add_dollar_product(staff,price='45.50',cost='30'):
    result=post(staff,'/admin/products',dict(name_en='Dollar racket',currency='USD',cost_price=cost,price=price,stock=5,
        track_stock='on',is_active='on',show_in_pos='on',show_in_website='on',low_stock_threshold=1))
    assert result.status_code==302,result.get_data(as_text=True)[:300]

def test_money_parsing_keeps_currencies_exact(app):
    from app import money
    with app.app_context():
        assert money.parse('45.5','USD')==4550 and money.parse('45','USD')==4500 and money.parse('3,000','IQD')==3000
        for bad,code in [('45.555','USD'),('3000.5','IQD'),('-1','IQD'),('abc','USD')]:
            with pytest.raises(core.RuleError):
                money.parse(bad,code)
    assert money.fmt(4550,'USD')=='$45.50' and money.fmt(3000,'IQD')=='3,000 IQD'

def test_dollar_and_dinar_bill_settle_report_and_refund_apart(app,staff):
    add_dollar_product(staff)
    with app.app_context():
        usd=Product.query.filter_by(name_en='Dollar racket').one()
        assert (usd.currency,usd.price,usd.cost_price)==('USD',4550,3000)
        usd_id=usd.id
    path=start(staff,'person')
    post(staff,path,dict(action='add',product_id=1,quantity=2))
    post(staff,path,dict(action='add',product_id=usd_id,quantity=1))
    # A fixed invoice discount comes off the dollar total only.
    assert post(staff,path,dict(action='discount',kind='fixed',currency='USD',value='5.50',reason='Loyal')).status_code==302
    with app.app_context():
        q=core.session_quote(POSSession.query.one())
        assert q['totals']=={'IQD':24000,'USD':4000} and q['currencies']==['IQD','USD']
    html=staff.get(path).get_data(as_text=True)
    assert '$40.00' in html and '24,000 IQD' in html
    post(staff,path,dict(action='settle',method='cash'))
    with app.app_context():
        pays={p.currency:p.amount for p in Payment.query.all()}
        assert pays=={'IQD':24000,'USD':4000}
        s=POSSession.query.one()
        assert (s.total_amount,s.total_usd)==(24000,4000)
        day=core.business_date()
        m=core.reports(day,day)['money']
        assert (m['IQD']['sales'],m['USD']['sales'])==(24000,4000)
        assert (m['IQD']['cogs'],m['USD']['cogs'])==(14000,3000)
        assert (m['IQD']['collected'],m['USD']['collected'])==(24000,4000)
        assert m['USD']['discounts']==550
    receipt=staff.get('/pos/receipt/1').get_data(as_text=True)
    assert '$40.00' in receipt and '24,000 IQD' in receipt
    assert b'$40.00' in staff.get('/admin').data and b'$40.00' in staff.get('/admin/reports').data
    assert post(staff,path,dict(action='refund',reason='Returned',restock='on')).status_code==302
    with app.app_context():
        adj={a.currency:(a.amount,a.cogs_reversal) for a in Adjustment.query.all()}
        assert adj=={'IQD':(24000,14000),'USD':(4000,3000)}
        refunds={p.currency:p.amount for p in Payment.query.filter(Payment.amount<0)}
        assert refunds=={'IQD':-24000,'USD':-4000}

def test_mixed_bill_on_debt_owes_each_currency(app,staff):
    add_dollar_product(staff,price='20')
    with app.app_context():
        usd_id=Product.query.filter_by(name_en='Dollar racket').one().id
    path=start(staff,'person')
    post(staff,path,dict(action='add',product_id=1,quantity=1))
    post(staff,path,dict(action='add',product_id=usd_id,quantity=1))
    post(staff,path,dict(action='settle',method='debt'))
    with app.app_context():
        debts={d.currency:(d.id,d.amount) for d in ManualDebt.query.all()}
        assert {k:v[1] for k,v in debts.items()}=={'IQD':12000,'USD':2000}
        usd_debt=debts['USD'][0]
    assert post(staff,'/admin/debts',dict(action='collect',id=usd_debt,amount='25',method='cash')).status_code==422
    assert post(staff,'/admin/debts',dict(action='collect',id=usd_debt,amount='7.25',method='cash')).status_code==302
    with app.app_context():
        assert db.session.get(ManualDebt,usd_debt).remaining==1275
        m=core.reports(core.business_date(),core.business_date())['money']
        assert m['USD']['outstanding']==1275 and m['IQD']['outstanding']==12000
        assert m['USD']['collected']==725 and m['IQD']['collected']==0
    assert post(staff,'/admin/debts',dict(name='Supplier note',currency='USD',amount='10.5',note='')).status_code==302
    with app.app_context():
        assert ManualDebt.query.filter_by(name='Supplier note').one().amount==1050

def test_website_order_with_dollar_items(app,staff,client):
    add_dollar_product(staff,price='12')
    with app.app_context():
        usd_id=Product.query.filter_by(name_en='Dollar racket').one().id
    shopper=app.test_client()
    post(shopper,'/store/cart',dict(product_id=usd_id,quantity=2))
    post(shopper,'/store/cart',dict(product_id=1,quantity=1))
    assert b'$24.00' in shopper.get('/store/cart').data
    result=post(shopper,'/store/checkout',dict(customer_name='Web buyer',customer_phone='+9647000000001',delivery_method='pickup'))
    assert result.status_code==302,result.get_data(as_text=True)[:300]
    with app.app_context():
        order=Order.query.one()
        assert (order.total_price,order.total_usd)==(12000,2400)
    assert post(staff,f'/admin/orders/{order.id}',dict(action='payment',currency='USD',amount='24',method='card')).status_code==302
    with app.app_context():
        o=db.session.get(Order,order.id)
        assert core.balance(o,'USD')==0 and core.balance(o,'IQD')==12000

def test_quick_sale_with_both_currencies(app,staff):
    add_dollar_product(staff,price='10')
    with app.app_context():
        usd_id=Product.query.filter_by(name_en='Dollar racket').one().id
    result=post(staff,'/pos/quick',dict(product_id=[1,usd_id],quantity=[1,3],discount='2.5',discount_kind='fixed',
        discount_currency='USD',reason='Promo',method='card'))
    assert result.status_code==302,result.get_data(as_text=True)[:300]
    with app.app_context():
        s=POSSession.query.one()
        assert (s.total_amount,s.total_usd)==(12000,2750)
        assert {p.currency:p.amount for p in Payment.query.all()}=={'IQD':12000,'USD':2750}

def test_activity_reads_as_sentences(app,staff):
    path=start(staff,'person')
    post(staff,path,dict(action='add',product_id=1,quantity=2))
    post(staff,path,dict(action='free',item_id=1,free_quantity=1))
    post(staff,path,dict(action='discount',kind='percentage',value=10,reason='Regular'))
    html=staff.get('/admin/activity').get_data(as_text=True)
    for sentence in ['test-admin opened a tab for Fictional player',"test-admin added 2 × Test racket to Fictional player&#39;s tab",
                     "test-admin gave 1 × Test racket free on Fictional player&#39;s tab","applied a discount of 10% to"]:
        assert sentence in html,sentence
    assert '<pre>' not in html and '{&#34;' not in html
    staff.get('/language/ar')
    assert 'فتح حساباً لـ Fictional player' in staff.get('/admin/activity').get_data(as_text=True)

def make_booking(app,starts_in_minutes,hours=1,name='Timed guest'):
    with app.app_context():
        a=core.now()+timedelta(minutes=starts_in_minutes)
        b=Booking(stadium_id=1,customer_name=name,customer_phone='+9647000000009',date=core.local(a).date(),
            start_time=core.local(a).time(),end_time=core.local(a+timedelta(hours=hours)).time(),duration_hours=hours,
            original_price=30000*hours,discount_amount=0,final_price=30000*hours,status='confirmed',reference=core.reference(),
            business_day=core.business_date(),starts_at=a,ends_at=a+timedelta(hours=hours),pricing_snapshot=core.rules(db.session.get(Stadium,1)))
        db.session.add(b);db.session.commit()
        return b.id

def json_post(client,path):
    return client.post(path,json={},headers={'Idempotency-Key':secrets.token_urlsafe(24)})

def test_booking_prompt_appears_only_at_its_time(app,staff):
    make_booking(app,30,name='Later guest')
    assert staff.get('/pos/api/due').json['due']==[]
    bid=make_booking(app,-2,hours=3,name='Blnd')
    due=staff.get('/pos/api/due').json['due']
    assert [d['id'] for d in due]==[bid] and due[0]['name']=='Blnd' and due[0]['hours']==3
    assert "It's Blnd's time" in due[0]['title'] and 'Blnd' in staff.get('/pos').get_data(as_text=True)

def test_accept_starts_at_booked_time_and_auto_stops_at_booked_end(app,staff):
    bid=make_booking(app,-5,hours=3,name='Blnd')
    r=json_post(staff,f'/pos/bookings/{bid}/start')
    assert r.status_code==200,r.get_data(as_text=True)[:300]
    url=r.json['url']
    with app.app_context():
        s=POSSession.query.one();b=db.session.get(Booking,bid)
        assert s.status=='active' and s.booking_id==bid and s.start_time==b.starts_at
    assert staff.get('/pos/api/due').json['due']==[]
    assert 'data-remaining' in staff.get(url).get_data(as_text=True)
    # Nothing stops before the booked end.
    assert staff.get('/pos/api/due').json['stopped']==[]
    with app.app_context():
        b=db.session.get(Booking,bid);b.ends_at=core.now()-timedelta(seconds=5);db.session.commit();end=b.ends_at
    stopped=staff.get('/pos/api/due').json['stopped']
    assert len(stopped)==1 and 'timer stopped' in stopped[0]['text']
    assert staff.get('/pos/api/due').json['stopped']==[]
    with app.app_context():
        s=POSSession.query.one()
        assert s.status=='stopped' and s.end_time==end and s.occupancy_key is None
        assert s.total_amount==90000
        assert ActivityLog.query.filter_by(action='Booked time ended').count()==1
    assert 'the booked time ended and the timer stopped automatically' in staff.get('/admin/activity').get_data(as_text=True)

def test_decline_dismisses_the_prompt(app,staff):
    bid=make_booking(app,-1)
    assert json_post(staff,f'/pos/bookings/{bid}/decline').status_code==200
    assert staff.get('/pos/api/due').json['due']==[]
    with app.app_context():
        b=db.session.get(Booking,bid)
        assert b.status=='confirmed' and b.start_prompt_declined_at is not None
    # A cashier can still start it by hand from the court card.
    r=post(staff,'/pos',dict(session_type='stadium',location_id=1,booking_id=bid))
    assert r.status_code==302

def test_accept_is_refused_when_court_is_busy(app,staff):
    start(staff,'stadium')
    bid=make_booking(app,-1)
    r=json_post(staff,f'/pos/bookings/{bid}/start')
    assert r.status_code==422 and r.json['error']

def test_bookings_filter_today(app,staff,client):
    make_booking(app,60,name='Tonight guest')
    assert post(client,'/booking/',{**booking_data(app),'customer_name':'Later week guest'}).status_code==302
    today=staff.get('/admin/bookings?when=today').get_data(as_text=True)
    assert 'Tonight guest' in today and 'Later week guest' not in today
    upcoming=staff.get('/admin/bookings?when=upcoming').get_data(as_text=True)
    assert upcoming.index('Tonight guest')<upcoming.index('Later week guest')
    assert 'Later week guest' in staff.get('/admin/bookings').get_data(as_text=True)

def test_cashier_role_without_email(app,staff):
    r=post(staff,'/admin/staff',dict(username='Till-One',password='Long-enough-pass-1',role='cashier',is_active='on'))
    assert r.status_code==302,r.get_data(as_text=True)[:300]
    with app.app_context():
        u=User.query.filter_by(username='till-one').one()
        assert u.email is None and u.role=='cashier' and not u.is_admin
        assert sorted(u.permissions)==['clients','pos','receipts'] and u.allowed('pos') and not u.allowed('reports')
        from app.security import landing
        assert landing(u)=='/pos'
    assert post(staff,'/admin/staff',dict(username='x',password='Long-enough-pass-1',role='manager',is_active='on')).status_code==422
    page=staff.get('/admin/staff').get_data(as_text=True)
    assert 'name="email"' not in page and 'value="cashier"' in page

def test_staff_password_any_length(app,staff):
    assert post(staff,'/admin/staff',dict(username='short-pass',password='1234',role='cashier',is_active='on')).status_code==302
    assert post(staff,'/admin/staff',dict(username='no-pass',password='',role='cashier',is_active='on')).status_code==422
    with app.app_context():
        u=User.query.filter_by(username='short-pass').one()
        assert u.check_password('1234')
        uid=u.id
    # Editing with a blank password keeps the current one.
    assert post(staff,f'/admin/staff/{uid}/edit',dict(username='short-pass',password='',role='cashier',is_active='on',
        permissions=['pos'],reason='Rename')).status_code==302
    with app.app_context():
        assert db.session.get(User,uid).check_password('1234')

def test_settings_keeps_daytime_rate_when_saved(app,staff):
    import re as _re
    html=staff.get('/admin/settings').get_data(as_text=True)
    assert _re.search(r'<input name="price_per_hour" type="number" value="30000"',html)
    assert not _re.search(r'<select name="price_per_hour"',html) and '<select name="opening_hour"' in html
    with app.app_context():
        form={k:getattr(core.settings(),k) for k in ['site_name','opening_hour','closing_hour','price_per_hour','evening_rate',
            'evening_start_hour','evening_end_hour','discount_percentage','discount_start_hour','discount_end_hour','minimum_minutes',
            'rounding_minutes','max_booking_hours','booking_days_ahead','delivery_fee','receipt_width','timezone','default_language','label_size']}
    assert post(staff,'/admin/settings',{k:('' if v is None else v) for k,v in form.items()}).status_code==302
    with app.app_context():
        assert core.settings().price_per_hour==30000

def regular_form(app,days_ahead=2,hour=20,**extra):
    with app.app_context():
        day=core.business_date()+timedelta(days=days_ahead)
    return day,dict(action='create',customer_name='Weekly Blnd',customer_phone='+9647000000011',stadium_id=1,
        hour=hour,duration=2,starts_on=str(core.business_date() if False else day),weekday=[day.weekday()],**extra)

def test_regular_reserves_next_game_and_blocks_the_slot(app,staff,client):
    day,form=regular_form(app)
    assert post(staff,'/admin/regulars',form).status_code==302
    with app.app_context():
        s=RegularBooking.query.one();b=Booking.query.filter_by(regular_id=s.id).one()
        assert (b.status,b.source,b.business_day,b.duration_hours)==('confirmed','regular',day,2)
    # Nobody else can book that slot online.
    assert post(client,'/booking/',{**booking_data(app),'date':str(day),'hour':20,'duration':1}).status_code==422
    page=staff.get('/admin/regulars').get_data(as_text=True)
    assert 'Weekly Blnd' in page and 'Next game' in page

def test_regular_twice_a_week_makes_two_slots(app,staff):
    day,form=regular_form(app)
    form['weekday']=[day.weekday(),(day.weekday()+3)%7]
    assert post(staff,'/admin/regulars',form).status_code==302
    with app.app_context():
        assert RegularBooking.query.count()==2 and Booking.query.filter(Booking.regular_id.isnot(None)).count()==2

def test_after_playing_next_week_is_reserved(app,staff):
    day,form=regular_form(app)
    post(staff,'/admin/regulars',form)
    with app.app_context():
        b=Booking.query.one();b.status='completed';db.session.commit()
    staff.get('/admin/regulars')
    with app.app_context():
        days=sorted(x.business_day for x in Booking.query.all())
        assert days==[day,day+timedelta(days=7)]
        assert core.regular_state(RegularBooking.query.one())['result']=='played'

def test_cancel_one_week_then_stop(app,staff):
    day,form=regular_form(app)
    post(staff,'/admin/regulars',form)
    with app.app_context():
        sid=RegularBooking.query.one().id
    assert post(staff,'/admin/regulars',dict(action='cancel_week',id=sid,reason='Travelling')).status_code==302
    with app.app_context():
        rows={b.business_day:b.status for b in Booking.query.all()}
        assert rows=={day:'cancelled',day+timedelta(days=7):'confirmed'}
    assert post(staff,'/admin/regulars',dict(action='stop',id=sid,reason='Did not come')).status_code==302
    staff.get('/admin/regulars')
    with app.app_context():
        s=db.session.get(RegularBooking,sid)
        assert not s.active and s.end_reason=='Did not come'
        assert Booking.query.filter_by(status='confirmed').count()==0 and Booking.query.count()==2
    assert 'stopped the weekly regular booking' in staff.get('/admin/activity').get_data(as_text=True)

def test_repeat_every_week_from_a_booking_and_settle_reserves_next(app,staff):
    # Open around the clock so the slot is valid whatever time the test runs.
    with app.app_context():
        core.settings().opening_hour=core.settings().closing_hour=0;db.session.commit()
    bid=make_booking(app,-5,hours=2,name='Sara')
    assert post(staff,f'/admin/bookings/{bid}',dict(action='repeat_weekly')).status_code==302
    with app.app_context():
        b=db.session.get(Booking,bid);s=RegularBooking.query.one()
        assert b.regular_id==s.id and s.weekday==b.business_day.weekday() and s.duration_hours==2
        first_day=b.business_day
    r=json_post(staff,f'/pos/bookings/{bid}/start')
    assert r.status_code==200
    post(staff,r.json['url'],dict(action='settle',method='cash'))
    with app.app_context():
        nxt=Booking.query.filter(Booking.regular_id.isnot(None),Booking.status=='confirmed').one()
        assert nxt.business_day==first_day+timedelta(days=7) and nxt.customer_name=='Sara'

def test_regular_week_already_taken_is_flagged_and_skipped(app,staff,client):
    day,form=regular_form(app)
    assert post(client,'/booking/',{**booking_data(app),'date':str(day),'hour':20,'duration':1}).status_code==302
    assert post(staff,'/admin/regulars',form).status_code==302
    with app.app_context():
        s=RegularBooking.query.one()
        assert s.conflict_on==day
        assert Booking.query.filter_by(regular_id=s.id).one().business_day==day+timedelta(days=7)

def test_walk_in_refusal_names_the_booking(app,staff):
    make_booking(app,-10,name='Blnd Now')
    r=post(staff,'/pos',dict(session_type='stadium',location_id=1))
    html=r.get_data(as_text=True)
    assert r.status_code==422 and 'booked right now for Blnd Now' in html and 'Bookings starting now' in html
    with app.app_context():
        Booking.query.delete();db.session.commit()
    make_booking(app,15,name='Soon Guest')
    html=post(staff,'/pos',dict(session_type='stadium',location_id=1)).get_data(as_text=True)
    assert 'booked for Soon Guest at' in html and 'minimum session' in html

def test_delete_unsold_product_removes_it(app,staff):
    post(staff,'/admin/products',dict(name_en='Never sold',currency='IQD',cost_price='100',price='500',stock=3,track_stock='on',is_active='on',show_in_pos='on',low_stock_threshold=1))
    with app.app_context():
        pid=Product.query.filter_by(name_en='Never sold').one().id
    r=post(staff,f'/admin/products/{pid}/edit',dict(action='delete'))
    assert r.status_code==302
    with app.app_context():
        assert db.session.get(Product,pid) is None and StockMovement.query.filter_by(product_id=pid).count()==0
    assert 'deleted the product “Never sold”' in staff.get('/admin/activity').get_data(as_text=True)

def test_delete_sold_product_keeps_history(app,staff):
    assert post(staff,'/pos/quick',dict(product_id=[1],quantity=[1],discount=0,method='cash')).status_code==302
    assert post(staff,'/admin/products/1/edit',dict(action='delete')).status_code==302
    with app.app_context():
        p=db.session.get(Product,1)
        assert p.deleted_at and not p.is_active and p.barcode is None
    assert 'Test racket' not in staff.get('/admin/products').get_data(as_text=True)
    assert 'Test racket' not in staff.get('/pos/quick').get_data(as_text=True)
    assert 'Test racket' in staff.get('/pos/receipt/1').get_data(as_text=True)
    with app.app_context():
        assert core.reports(core.business_date(),core.business_date())['money']['IQD']['sales']==12000

def test_delete_category_keeps_its_products(app,staff):
    assert post(staff,'/admin/categories/1/edit',dict(action='delete')).status_code==302
    with app.app_context():
        assert db.session.get(Category,1) is None and db.session.get(Product,1).category_id is None
    assert 'Test racket' in staff.get('/admin/products').get_data(as_text=True)

def open_client(app,staff,name='Daily Ahmed',phone='0750 111 2222'):
    r=post(staff,'/admin/clients',dict(name=name,phone=phone,notes='Plays every evening'))
    assert r.status_code==302,r.get_data(as_text=True)[:300]
    with app.app_context():
        return Client.query.filter_by(name=name).one().id

def test_client_account_saves_bills_and_pays_later(app,staff):
    cid=open_client(app,staff)
    assert post(staff,'/admin/clients',dict(name='daily ahmed',phone='0750 111 2222')).status_code==422
    for visit in range(2):
        tab=post(staff,'/pos',dict(session_type='person',client_id=cid)).location
        # Picking their name again reopens the same tab instead of a second one.
        assert post(staff,'/pos',dict(session_type='person',client_id=cid)).location==tab
        post(staff,tab,dict(action='add',product_id=1,quantity=1))
        assert 'Save to Daily Ahmed’s account' in staff.get(tab).get_data(as_text=True)
        assert post(staff,tab,dict(action='settle',method='account')).status_code==302
    with app.app_context():
        c=db.session.get(Client,cid)
        assert core.client_owes(c)=={'IQD':24000,'USD':0}
        assert all(d.client_id==cid for d in ManualDebt.query.all())
        bill=POSSession.query.filter_by(client_id=cid).first()
        assert bill.status=='debt' and bill.payment_method=='account' and bill.customer_name=='Daily Ahmed'
        bill_id=bill.id
    assert 'Saved to account' in staff.get(f'/pos/receipt/{bill_id}').get_data(as_text=True)
    page=staff.get('/admin/clients').get_data(as_text=True)
    assert 'Daily Ahmed' in page and '24,000' in page
    # Paying part clears the oldest bill first; paying more than owed is refused.
    assert post(staff,f'/admin/clients/{cid}',dict(action='pay',currency='IQD',amount='15000',method='cash')).status_code==302
    assert post(staff,f'/admin/clients/{cid}',dict(action='pay',currency='IQD',amount='10000',method='cash')).status_code==422
    with app.app_context():
        first,second=ManualDebt.query.order_by(ManualDebt.id).all()
        assert first.status=='paid' and second.remaining==9000
        assert core.client_owes(db.session.get(Client,cid))['IQD']==9000
        assert core.reports(core.business_date(),core.business_date())['money']['IQD']['collected']==15000
    # The name stays until deleted, and cannot be deleted while money is owed.
    assert post(staff,f'/admin/clients/{cid}',dict(action='delete')).status_code==422
    post(staff,f'/admin/clients/{cid}',dict(action='pay',currency='IQD',amount='9000',method='card'))
    assert 'Nothing owed' in staff.get('/admin/clients').get_data(as_text=True)
    assert post(staff,f'/admin/clients/{cid}',dict(action='delete')).location.endswith('/admin/clients')
    with app.app_context():
        assert db.session.get(Client,cid) is None
        assert ManualDebt.query.filter(ManualDebt.client_id.isnot(None)).count()==0
        assert ManualDebt.query.first().name=='Daily Ahmed'
    assert staff.get(f'/pos/receipt/{bill_id}').status_code==200
    feed=staff.get('/admin/activity').get_data(as_text=True)
    assert 'opened a client account for Daily Ahmed' in feed and 'account' in feed

def test_one_time_customer_pays_now_and_others_go_on_an_account(app,staff):
    cid=open_client(app,staff,'Sara regular','')
    # A client can still pay on the spot: nothing goes on the account.
    tab=post(staff,'/pos',dict(session_type='person',client_id=cid)).location
    post(staff,tab,dict(action='add',product_id=1,quantity=1))
    post(staff,tab,dict(action='settle',method='cash'))
    with app.app_context():
        assert ManualDebt.query.count()==0
    # A walk-in tab or a quick sale can be saved to an account chosen at the end.
    walk_in=start(staff,'person')
    post(staff,walk_in,dict(action='add',product_id=1,quantity=1))
    assert post(staff,walk_in,dict(action='settle',method='account')).status_code==422
    assert post(staff,walk_in,dict(action='settle',method='account',client_id=cid)).status_code==302
    assert post(staff,'/pos/quick',dict(product_id=[1],quantity=[2],discount=0,method='account',client_id=cid)).status_code==302
    with app.app_context():
        assert core.client_owes(db.session.get(Client,cid))['IQD']==36000
    page=staff.get(f'/admin/clients/{cid}').get_data(as_text=True)
    assert 'Sara regular' in page and '36,000' in page
    assert post(staff,f'/admin/clients/{cid}',dict(action='charge',currency='USD',amount='5',note='Old balance')).status_code==302
    with app.app_context():
        assert core.client_owes(db.session.get(Client,cid))=={'IQD':36000,'USD':500}

