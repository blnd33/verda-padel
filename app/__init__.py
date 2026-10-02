import os
import secrets
import logging
import json
import time
import sqlite3
from datetime import timedelta
from pathlib import Path
from flask import Flask, request, session, g, redirect, render_template, jsonify, make_response
from sqlalchemy import event, text, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

@event.listens_for(Engine, 'connect')
def sqlite_connection(connection, record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=30000')
        cursor.close()

def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    from dotenv import load_dotenv
    load_dotenv(Path(app.root_path).parent / '.env')
    production = os.environ.get('VERDA_ENV') == 'production'
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        if production:
            raise RuntimeError('Set a strong SECRET_KEY before production startup.')
        secret_file = Path(app.instance_path) / '.session-secret'
        if not secret_file.exists():
            secret_file.write_text(secrets.token_hex(32), encoding='utf-8')
        secret = secret_file.read_text(encoding='utf-8').strip()
    app.config.update(SECRET_KEY=secret,
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///verda.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False, MAX_CONTENT_LENGTH=45*1024*1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=production,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), WTF_CSRF_TIME_LIMIT=8*3600,
        DEBUG=False)
    if config:
        app.config.update(config)
    app.logger.setLevel(logging.INFO)
    db.init_app(app)
    from app import models
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)
    from app.services import core
    from app.security import permitted, NAVIGATION
    from app.i18n import translate, clock, clock_of, hour12, meridiem
    from app.routes.public import main, booking, store
    from app.routes.auth import auth
    from app.routes.admin import admin
    from app.routes.pos import pos
    for bp in [main, booking, store, auth, admin, pos]:
        app.register_blueprint(bp)

    @app.url_defaults
    def version_static_urls(endpoint, values):
        """Stamp every static URL with the file's modification time. The service
        worker serves /static/ cache-first, so without this a changed stylesheet
        or script keeps its old URL and visitors never receive the update."""
        if endpoint != 'static' or 'v' in values or not values.get('filename'):
            return
        try:
            values['v'] = int(os.stat(os.path.join(app.static_folder, values['filename'])).st_mtime)
        except OSError:
            pass

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(models.User, int(user_id))
        except (TypeError, ValueError):
            return None
        return user if user and user.is_active and session.get('staff_version') == user.session_version else None

    @app.before_request
    def begin_request():
        g.request_started=time.monotonic()
        if request.endpoint == 'static':
            return
        if 'client_key' not in session:
            session['client_key'] = secrets.token_urlsafe(24)
        if request.method in ['POST','PUT','PATCH','DELETE']:
            # Serialize the validation/write interval across worker processes.
            if db.engine.dialect.name == 'sqlite':
                db.session.execute(text('BEGIN IMMEDIATE'))
            else:
                lock = db.session.execute(select(models.TransactionLock).where(models.TransactionLock.id==1).with_for_update()).scalar_one()
            g.transaction = True
            key = request.headers.get('Idempotency-Key') or request.form.get('_operation')
            if not key or len(key) > 120:
                raise core.RuleError('Reload the page before submitting this action.')
            g.operation_key = key
            old = db.session.get(models.Operation, key)
            if old:
                if old.owner != session['client_key'] or old.endpoint != request.path:
                    return jsonify(error='Invalid request reference.'), 409
                g.replayed = True
                return redirect(old.location, old.status) if old.location else make_response(old.body or '', old.status, {'Content-Type':'application/json'})

    @app.after_request
    def finish_request(response):
        if getattr(g, 'transaction', False):
            if response.status_code < 400:
                if not getattr(g, 'replayed', False):
                    db.session.add(models.Operation(key=g.operation_key, owner=session['client_key'], endpoint=request.path,
                        location=response.headers.get('Location'), body=response.get_data(as_text=True) if response.is_json else '', status=response.status_code))
                db.session.commit()
            else:
                db.session.rollback()
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-src 'self' https://www.google.com https://maps.google.com; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
        if request.path.startswith(('/admin','/pos','/auth','/booking/confirmation','/store/confirmation')):
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
            response.headers['Cache-Control'] = 'no-store'
        if request.endpoint!='static':
            app.logger.info(json.dumps(dict(event='http_request',endpoint=request.endpoint,
                method=request.method,status=response.status_code,
                duration_ms=round((time.monotonic()-getattr(g,'request_started',time.monotonic()))*1000))))
        return response

    @app.context_processor
    def globals_for_templates():
        from urllib.parse import urlencode
        from flask_login import current_user
        s = core.settings()
        lang = session.get('lang', s.default_language if s else 'en')
        def content(key, fallback=''):
            data = (s.content or {}).get(key, {}) if s else {}
            return (data.get(lang) or data.get('en') or fallback) if isinstance(data, dict) else data or fallback
        def query_link(**values):
            params=request.args.to_dict(flat=True)
            params.update(values)
            return request.path+'?'+urlencode(params)
        def grouped_nav():
            current=request.full_path.rstrip('?')
            groups=[]
            for group, permission, label, url in NAVIGATION:
                if not permitted(permission):
                    continue
                active=current==url or (url not in ['/admin','/pos'] and '?' not in url and request.path.startswith(url))
                if not groups or groups[-1]['name']!=group:
                    groups.append(dict(name=group,links=[],active=False))
                groups[-1]['links'].append(dict(label=label,url=url,active=active))
                groups[-1]['active']=groups[-1]['active'] or active
            return groups
        def media_mode(prefix):
            data=(s.content or {}) if s else {}
            mode=data.get(prefix+'_media') or ('image' if data.get(prefix+'_image') else 'illustration')
            return mode if data.get(prefix+'_'+mode) else 'illustration'
        def media_url(prefix):
            data=(s.content or {}) if s else {}
            return data.get(prefix+'_'+media_mode(prefix))
        def venue_map():
            """Google Maps embed and directions links for the venue: exact
            coordinates when set, otherwise the address text, otherwise none."""
            from urllib.parse import quote
            if not s:
                return None
            place=s.map_coordinates or (s.address or '').strip()
            if not place:
                return None
            target=quote(place,safe=',')
            return dict(embed=f'https://www.google.com/maps?q={target}&z=16&output=embed',
                directions=f'https://www.google.com/maps/dir/?api=1&destination={target}' if s.map_coordinates or not s.directions_url else s.directions_url,
                open=f'https://www.google.com/maps/search/?api=1&query={target}')
        def line_name(line):
            snapshot=(line.get('snapshot') if isinstance(line,dict) else line.snapshot) or {}
            return snapshot.get('name_'+lang) or snapshot.get('name_en') or '—'
        unread_count=0
        if current_user.is_authenticated:
            allowed=[p for p in __import__('app.security',fromlist=['PERMISSIONS']).PERMISSIONS if current_user.allowed(p)]
            read_ids=select(models.NotificationRead.notification_id).where(models.NotificationRead.user_id==current_user.id)
            unread_count=models.Notification.query.filter(models.Notification.scope.in_(allowed),
                db.or_(models.Notification.user_id.is_(None),models.Notification.user_id==current_user.id),
                ~models.Notification.id.in_(read_ids)).count()
        return dict(settings=s, lang=lang, rtl=lang=='ar', t=lambda key:translate(key, lang),
            title={'main.home':'Home','main.information':'Contact' if request.path=='/contact' else 'Our story',
                'booking.book':'Book a court','booking.confirmation':'Booking details',
                'store.products':'Store','store.product':'Product details','store.cart':'Cart',
                'store.checkout':'Checkout','store.order_confirmation':'Order details','auth.login':'Sign in',
                'pos.receipt':'Receipt','admin.receipt':'Receipt'}.get(request.endpoint,''),
            can=permitted, nav=grouped_nav(), form_key=lambda:secrets.token_urlsafe(24),
            cart_count=sum(session.get('cart', {}).values()), content=content,
            media_mode=media_mode, media_url=media_url,
            business_today=core.business_date() if s else None, quote_session=core.session_quote, line_amounts=core.line_amounts, venue_map=venue_map(), balance=core.balance,
            permissions=__import__('app.security',fromlist=['PERMISSIONS']).PERMISSIONS,
            page_link=lambda page:query_link(page=page),export_link=lambda:query_link(export='csv'),line_name=line_name,
            receipt_time=lambda value,record:clock_of(core.local(value,(record.venue_snapshot or {}).get('timezone',s.timezone)),lang,True) if value else '—',
            clock=lambda hour,minute=0,short=False:clock(hour,minute,lang,short),hour12=hour12,meridiem=lambda hour:meridiem(hour,lang),unread_count=unread_count)

    app.jinja_env.filters['iqd'] = lambda value:f'{core.money(value or 0):,}'
    from app import money as currency
    # {{ amount|money(currency) }} -> '3,000 IQD' or '$45.00'; |money_input for form fields.
    app.jinja_env.filters['money'] = lambda value,code='IQD':currency.fmt(core.money(value or 0),code or 'IQD')
    app.jinja_env.filters['money_input'] = lambda value,code='IQD':currency.field_value(value,code or 'IQD')
    app.jinja_env.globals.update(CURRENCIES=currency.CURRENCIES,CURRENCY_LABELS=currency.LABELS)
    def current_lang():
        s = core.settings()
        return session.get('lang', s.default_language if s else 'en')
    app.jinja_env.filters['venue_time'] = lambda value:clock_of(core.local(value),current_lang(),True) if value else '—'
    app.jinja_env.filters['venue_clock'] = lambda value:clock_of(core.local(value),current_lang()) if value else '—'
    app.jinja_env.filters['short_ref'] = lambda value:(value or '')[:10].upper()

    @app.errorhandler(core.RuleError)
    def rule_error(error):
        db.session.rollback()
        if request.is_json:
            return jsonify(error=translate(str(error),session.get('lang','en'))), 422
        return render_template('error.html', title='Check your details', message=str(error)), 422

    @app.errorhandler(IntegrityError)
    def duplicate_error(error):
        db.session.rollback()
        return render_template('error.html', title='Please try again', message='This record conflicts with an existing record. Reload and try again.'), 409

    @app.errorhandler(OperationalError)
    def database_error(error):
        db.session.rollback()
        app.logger.error('database_operation_failed')
        return 'Verda Padel: database unavailable. Run setup or try again shortly.', 503

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def access_error(error):
        return render_template('error.html', title='Page unavailable', message='The page is unavailable or you do not have permission.'), error.code

    @app.errorhandler(500)
    def unexpected_error(error):
        db.session.rollback()
        return render_template('error.html', title='Please try again', message='Something went wrong. Your request was not completed.'), 500

    from app.cli import register_commands
    register_commands(app)
    return app
