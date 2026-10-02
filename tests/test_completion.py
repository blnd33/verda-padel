import io
import sqlite3
from datetime import timedelta,datetime
from flask_migrate import upgrade,downgrade
from app import create_app,db
from app.models import *
from app.services import core
from tests.test_workflows import post


def test_website_archive_payments_and_prefullfillment_refund(app,staff):
    post(staff,'/store/cart',dict(action='add',product_id=1,quantity=1))
    r=post(staff,'/store/checkout',dict(customer_name='Archive buyer',customer_phone='+9647000000000',delivery_method='pickup'))
    assert r.status_code==302
    assert post(staff,'/admin/orders/1',dict(action='payment',amount=4000,method='cash')).status_code==302
    assert post(staff,'/admin/orders/1',dict(action='payment',amount=8000,method='card')).status_code==302
    for method in ['cash','card','paid']:
        result=staff.get('/admin/archive?period=all&method='+method+'&export=csv')
        assert result.status_code==200 and b'Archive buyer' in result.data
    assert b'Archive buyer' not in staff.get('/admin/archive?period=all&method=unpaid&export=csv').data
    assert post(staff,'/admin/orders/1',dict(action='refund',reason='Fictional return',restock='on')).status_code==302
    with app.app_context():
        report=core.reports(core.business_date(),core.business_date())['money']['IQD']
        assert report['sales']==report['refunds']==report['collected']==report['cogs']==0
        assert db.session.get(Product,1).stock==10


def test_debt_refund_reconciles_stock_cost_and_collections(app,staff):
    result=post(staff,'/pos/quick',dict(product_id=[1],quantity=[2],discount=0,method='debt',customer_name='Demo debt'))
    assert result.status_code==302
    post(staff,'/admin/debts',dict(action='collect',id=1,amount=5000,method='cash'))
    post(staff,'/pos/session/1',dict(action='refund',reason='Returned goods',restock='on'))
    post(staff,'/pos/session/1',dict(action='refund',reason='Repeated return',restock='on'))
    with app.app_context():
        report=core.reports(core.business_date(),core.business_date())['money']['IQD']
        assert report['sales']==report['refunds']==24000
        assert report['net_sales']==report['cogs']==report['collected']==report['debt_collections']==report['outstanding']==0
        assert Payment.query.count()==2 and Adjustment.query.count()==1
        assert db.session.get(Product,1).stock==10
    assert staff.get('/admin/reports').status_code==200


def test_shared_notification_read_isolation(app,staff):
    with app.app_context():
        db.session.add(Notification(type='pos',scope='pos',title='Shared demo',url='/pos'))
        db.session.commit()
    other=app.test_client()
    with other.session_transaction() as s:
        s['_user_id']='2';s['staff_version']=1;s['lang']='en'
    assert post(staff,'/admin/notifications',dict(id=1)).status_code==302
    assert b'Mark read' not in staff.get('/admin/notifications').data
    assert b'Mark read' in other.get('/admin/notifications').data
    assert post(other,'/admin/notifications',dict(id=1)).status_code==302
    with app.app_context():
        assert NotificationRead.query.count()==2


def test_staff_guard_and_invalid_upload(app,staff):
    assert post(staff,'/admin/staff/1/edit',dict(action='archive',reason='Test last admin')).status_code==422
    assert post(staff,'/admin/courts',dict(name='Bad image',price_per_hour=0,image_url=(io.BytesIO(b'<svg>bad</svg>'),'court.png'))).status_code==422
    with app.app_context():
        assert db.session.get(User,1).is_active
        assert Stadium.query.count()==1
    assert staff.get('/store/?category=1').status_code==200


def test_court_utilization_uses_time_not_payments(app,monkeypatch):
    fixed=datetime(2026,9,17,12,0) # 15:00 Baghdad
    monkeypatch.setattr(core,'now',lambda:fixed)
    with app.app_context():
        db.session.add(POSSession(session_type='stadium',stadium_id=1,status='stopped',
            start_time=fixed-timedelta(hours=2),end_time=fixed-timedelta(hours=1)))
        db.session.add(CourtBlock(stadium_id=1,starts_at=fixed-timedelta(hours=4),ends_at=fixed-timedelta(hours=3),reason='Test'))
        db.session.commit()
        rows=core.court_usage(fixed.date(),fixed.date())
        assert rows[0]['occupied_hours']==1
        assert rows[0]['available_hours']==5
        assert rows[0]['utilization']==20


def test_setup_admin_backup_and_upgrade_preserve_data(tmp_path):
    path=tmp_path/'fresh.db'
    app=create_app(dict(TESTING=True,SECRET_KEY='test-only-secret',SQLALCHEMY_DATABASE_URI='sqlite:///'+str(path)))
    runner=app.test_cli_runner()
    assert runner.invoke(args=['setup']).exit_code==0
    assert runner.invoke(args=['setup']).exit_code==0
    created=runner.invoke(args=['create-admin','--username','new-admin','--email','admin@example.invalid'],input='Test-only-secret!123\nTest-only-secret!123\n')
    assert created.exit_code==0,created.output
    with app.app_context():
        assert User.query.one().check_password('Test-only-secret!123')
        assert Settings.query.count()==1
        # Exercise an upgrade with existing Verda rows and stable identifiers.
        downgrade(revision='0002')
        upgrade()
        assert User.query.one().id==1 and Settings.query.count()==1
    target=tmp_path/'backup.db'
    assert runner.invoke(args=['backup',str(target)]).exit_code==0
    assert runner.invoke(args=['backup',str(target)]).exit_code!=0
    with sqlite3.connect(path) as source:
        head=source.execute('SELECT version_num FROM alembic_version').fetchone()[0]
    with sqlite3.connect(target) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert connection.execute('SELECT username FROM user WHERE id=1').fetchone()[0]=='new-admin'
        assert connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]==head
    restored=create_app(dict(TESTING=True,SECRET_KEY='test-only-secret',SQLALCHEMY_DATABASE_URI='sqlite:///'+str(target)))
    assert restored.test_client().get('/').status_code==200
    with app.app_context():
        db.session.remove();db.engine.dispose()
    with restored.app_context():
        db.session.remove();db.engine.dispose()


def test_settings_zero_and_receipt_width(app,staff):
    with app.app_context():
        settings=core.settings()
        keys=['site_name','phone','email','address','directions_url','facebook_url','instagram_url','twitter_url',
            'opening_hour','closing_hour','price_per_hour','evening_rate','evening_start_hour','evening_end_hour',
            'discount_percentage','discount_start_hour','discount_end_hour',
            'minimum_minutes','rounding_minutes','max_booking_hours','booking_days_ahead','delivery_fee','default_language',
            'timezone','receipt_width','label_size']
        data={key:getattr(settings,key) or '' for key in keys}
    data.update(price_per_hour=0,evening_rate=0,evening_end_hour=0,discount_percentage=0,discount_start_hour=0,
        discount_end_hour=0,minimum_minutes=0,delivery_fee=0,receipt_width=58,configured='on')
    response=post(staff,'/admin/settings',data)
    assert response.status_code==302,response.get_data(as_text=True)
    with app.app_context():
        assert core.settings().price_per_hour==core.settings().minimum_minutes==core.settings().delivery_fee==0
    response=post(staff,'/pos/quick',dict(product_id=[1],quantity=[1],discount=0,method='cash'))
    assert b'--receipt-width:58mm' in staff.get(response.location).data


def test_expense_filters_and_void_audit(app,staff):
    with app.app_context():
        day=str(core.business_date())
    result=post(staff,'/admin/expenses',dict(date=day,category='rent',amount=1500,description='Test expense',payment_method='card'))
    assert result.status_code==302
    assert b'1,500' in staff.get('/admin/expenses?method=card&category=rent&status=active').data
    assert b'1,500' not in staff.get('/admin/expenses?method=cash').data
    assert post(staff,'/admin/expenses/1/edit',dict(action='archive',reason='Fictional correction')).status_code==302
    with app.app_context():
        assert core.reports(core.business_date(),core.business_date())['money']['IQD']['expenses_total']==0
        assert ActivityLog.query.filter_by(action='Record archived',entity_type='expense').count()==1
