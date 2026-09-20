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
        '/admin/barcodes?preview=1&ids=1&price=1','/admin/blocks','/admin/settings','/pos','/pos/quick']:
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

def test_table_has_no_court_charge_and_discounts_once(app,staff):
    path=start(staff,'table')
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
        report=core.reports(day,day)
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
        report=core.reports(core.business_date(),core.business_date())
        assert report['sales']==24000 and report['collected']==24000 and report['outstanding']==0

def test_permissions_and_csrf(app,cashier):
    assert cashier.get('/admin/settings').status_code==403
    assert cashier.get('/admin/reports').status_code==403
    assert cashier.get('/admin/barcode/1.svg').status_code==403
    path=start(cashier,'table')
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
        assert core.reports(core.business_date(),core.business_date())['cogs']==7000

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
        report=core.reports(core.business_date(),core.business_date())
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
