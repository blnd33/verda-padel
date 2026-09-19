import hashlib
from datetime import timedelta
from flask import Blueprint, request, session, render_template, redirect, flash
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import User, LoginAttempt
from app.services import core
from app.security import landing

auth = Blueprint('auth', __name__, url_prefix='/auth')

@auth.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(landing(current_user))
    if request.method == 'POST':
        username = core.text_value(request.form.get('username'), True, 80).lower()
        fingerprint = hashlib.sha256((request.remote_addr or '').encode()).hexdigest()
        since = core.now()-timedelta(minutes=15)
        if LoginAttempt.query.filter(LoginAttempt.fingerprint==fingerprint,LoginAttempt.created_at>since).count() >= 8:
            raise core.RuleError('Too many login attempts. Please try again in 15 minutes.')
        user = User.query.filter_by(username=username).first()
        if not user or not user.is_active or not user.check_password(request.form.get('password','')):
            db.session.add(LoginAttempt(fingerprint=fingerprint))
            flash('Invalid username or password.', 'error')
            return redirect('/auth/login')
        login_user(user)
        session.permanent=True
        session['staff_version']=user.session_version
        core.audit('Staff signed in',user)
        return redirect(landing(user))
    return render_template('login.html')

@auth.post('/logout')
def logout():
    logout_user()
    session.pop('staff_version',None)
    return redirect('/')
