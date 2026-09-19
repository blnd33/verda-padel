from functools import wraps
from flask import abort, redirect, url_for
from flask_login import current_user

PERMISSIONS = ['dashboard','bookings','orders','products','inventory','courts','tables',
               'pos','discounts','cancellations','debts','expenses','reports','receipts','settings','staff']

NAVIGATION = [
    ('Today','dashboard','Overview','/admin'),
    ('Today','bookings','Pending bookings','/admin/bookings?status=pending'),
    ('Today','bookings','Bookings','/admin/bookings'),
    ('Today','cancellations','Cancellations','/admin/bookings?status=pending_cancel'),
    ('Today','orders','Website orders','/admin/orders'),
    ('Selling','pos','Cashier','/pos'),
    ('Selling','pos','Quick sale','/pos/quick'),
    ('Selling','receipts','Receipt archive','/admin/archive'),
    ('Catalog','products','Products','/admin/products'),
    ('Catalog','products','Categories','/admin/categories'),
    ('Catalog','inventory','Inventory','/admin/inventory'),
    ('Catalog','products','Barcode labels','/admin/barcodes'),
    ('Venue','courts','Courts','/admin/courts'),
    ('Venue','tables','Tables','/admin/tables'),
    ('Money','debts','Debts','/admin/debts'),
    ('Money','expenses','Expenses','/admin/expenses'),
    ('Money','reports','Reports','/admin/reports'),
    ('System','dashboard','Activity','/admin/activity'),
    ('System','settings','Website & settings','/admin/settings'),
    ('System','staff','Staff & permissions','/admin/staff')]

def permitted(permission):
    return current_user.is_authenticated and current_user.allowed(permission)

def require(permission):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not current_user.allowed(permission):
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def landing(user):
    return next((url for group, permission, label, url in NAVIGATION if user.allowed(permission)), '/')
