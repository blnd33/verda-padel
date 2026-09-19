# app/models/activity_log.py
from datetime import datetime
from app import db

class ActivityLog(db.Model):
    __tablename__ = "activity_log"

    before_values = db.Column(db.JSON)
    after_values = db.Column(db.JSON)

    id = db.Column(db.Integer, primary_key=True)

    # who did it
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # what happened
    action = db.Column(db.String(50), nullable=False)       # approve_booking, add_product, update_order_status...
    entity_type = db.Column(db.String(30), nullable=True)   # booking, order, product, pos_session...
    entity_id = db.Column(db.Integer, nullable=True)

    # extra info for dashboard
    title = db.Column(db.String(200), nullable=True)
    note = db.Column(db.Text, nullable=True)

    # money/payment (optional)
    amount = db.Column(db.Integer, nullable=True)           # IQD
    payment_method = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # relationship (optional)
    user = db.relationship("User", backref=db.backref("activity_logs", lazy=True))