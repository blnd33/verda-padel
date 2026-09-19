import pytest
from flask_migrate import upgrade
from app import create_app,db
from app.models import *

@pytest.fixture
def app(tmp_path):
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'test.db'),
        'SECRET_KEY':'test-only-secret-key','WTF_CSRF_ENABLED':False})
    with app.app_context():
        upgrade()
        db.session.add(Settings(id=1,site_name='Verda Padel',configured=True,default_language='en',
            opening_hour=9,closing_hour=2,price_per_hour=30000,discount_percentage=0))
        admin=User(username='test-admin',email='test-admin@example.invalid',role='super_admin',is_admin=True,is_active=True)
        admin.set_password('Test-only-password!234')
        cashier=User(username='test-cashier',email='cashier@example.invalid',role='admin',is_active=True,
            permissions=['pos','receipts','debts'])
        cashier.set_password('Test-only-password!234')
        db.session.add_all([admin,cashier,Stadium(name='Test Court',price_per_hour=30000),Table(name='Test Table',capacity=4)])
        cat=Category(name_en='Test')
        db.session.add(cat)
        db.session.flush()
        db.session.add(Product(name_en='Test racket',category_id=cat.id,price=12000,cost_price=7000,
            stock=10,barcode='TEST-001',track_stock=True,featured=True))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def staff(client):
    with client.session_transaction() as session:
        session['_user_id']='1'
        session['_fresh']=True
        session['staff_version']=1
        session['lang']='en'
    return client

@pytest.fixture
def cashier(client):
    with client.session_transaction() as session:
        session['_user_id']='2'
        session['_fresh']=True
        session['staff_version']=1
    return client
