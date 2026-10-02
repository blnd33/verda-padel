from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(db.Model, UserMixin):
    __tablename__ = 'user'

    permissions = db.Column(db.JSON, default=list)
    session_version = db.Column(db.Integer, default=1, nullable=False, server_default='1')

    def allowed(self, permission):
        return bool(self.is_active and (self.role == 'super_admin' or permission in (self.permissions or [])))

    # ---- Roles ----
    ROLE_SUPER_ADMIN = "super_admin"
    ROLE_ADMIN = "admin"
    ROLE_CASHIER = "cashier"
    ROLES = (ROLE_CASHIER, ROLE_ADMIN, ROLE_SUPER_ADMIN)
    # A new cashier starts with the till and its receipts; more can be ticked.
    CASHIER_PERMISSIONS = ['pos', 'receipts']

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    # Optional: staff sign in with their username.
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # ✅ Main role (source of truth)
    role = db.Column(db.String(20), default=ROLE_ADMIN, nullable=False)

    # ✅ KEEP this column (Option B) but we will auto-sync it from role
    is_admin = db.Column(db.Boolean, default=False)

    # ✅ Flask-Login active flag
    is_active = db.Column(db.Boolean, default=True)

    # ---- Permissions ----
    can_manage_bookings = db.Column(db.Boolean, default=True)
    can_manage_products = db.Column(db.Boolean, default=True)
    can_manage_orders = db.Column(db.Boolean, default=True)
    can_manage_stadiums = db.Column(db.Boolean, default=False)
    can_manage_settings = db.Column(db.Boolean, default=False)
    can_view_reports = db.Column(db.Boolean, default=False)
    can_access_dashboard = db.Column(db.Boolean, default=False)  # ✅ NEW: Dashboard access permission

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # -------------------------
    # Password helpers
    # -------------------------
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # -------------------------
    # Role helpers
    # -------------------------
    @property
    def is_super_admin(self) -> bool:
        return self.role == self.ROLE_SUPER_ADMIN

    @property
    def is_admin_role(self) -> bool:
        """True for admin or super_admin."""
        return self.role in (self.ROLE_ADMIN, self.ROLE_SUPER_ADMIN)

    def sync_role_flags(self):
        """
        Keep legacy column is_admin synced with role.
        Call this before saving whenever role changes.
        """
        self.is_admin = self.is_admin_role

        # Super admin must have all permissions
        if self.is_super_admin:
            self.can_manage_bookings = True
            self.can_manage_products = True
            self.can_manage_orders = True
            self.can_manage_stadiums = True
            self.can_manage_settings = True
            self.can_view_reports = True
            self.can_access_dashboard = True  # ✅ NEW: Super admin always has dashboard access
            self.is_active = True

    # -------------------------
    # Flask-Login override
    # -------------------------
    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"