from datetime import datetime
from app import db


class TransactionLock(db.Model):
    __tablename__ = 'transaction_lock'
    id = db.Column(db.Integer, primary_key=True)


class Operation(db.Model):
    __tablename__ = 'operation'
    key = db.Column(db.String(120), primary_key=True)
    owner = db.Column(db.String(100), nullable=False)
    endpoint = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(500))
    body = db.Column(db.Text)
    status = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CourtBlock(db.Model):
    __tablename__ = 'court_block'
    id = db.Column(db.Integer, primary_key=True)
    stadium_id = db.Column(db.Integer, db.ForeignKey('stadium.id'), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(300), nullable=False)
    court = db.relationship('Stadium')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    __table_args__ = (db.CheckConstraint('ends_at > starts_at', name='ck_block_interval'),)


class StockMovement(db.Model):
    __tablename__ = 'stock_movement'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, index=True)
    product = db.relationship('Product')
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(300), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Payment(db.Model):
    __tablename__ = 'payment'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('pos_session.id'), index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), index=True)
    debt_id = db.Column(db.Integer, db.ForeignKey('manual_debts.id'), index=True)
    pos_session = db.relationship('POSSession', backref='payments')
    order = db.relationship('Order', backref='payments')
    debt = db.relationship('ManualDebt', backref='collections')
    amount = db.Column(db.BigInteger, nullable=False)
    method = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    business_day = db.Column(db.Date, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    __table_args__ = (db.CheckConstraint("method IN ('cash','card')", name='ck_payment_method'),)


class Adjustment(db.Model):
    __tablename__ = 'adjustment'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('pos_session.id'), unique=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True)
    amount = db.Column(db.BigInteger, nullable=False)
    cogs_reversal = db.Column(db.BigInteger, nullable=False, default=0, server_default='0')
    reason = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    business_day = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class NotificationRead(db.Model):
    __tablename__ = 'notification_read'
    notification_id = db.Column(db.Integer, db.ForeignKey('notifications.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)


class LoginAttempt(db.Model):
    __tablename__ = 'login_attempt'
    id = db.Column(db.Integer, primary_key=True)
    fingerprint = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
