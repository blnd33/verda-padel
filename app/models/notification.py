# app/models/notification.py
from datetime import datetime
from app import db

class Notification(db.Model):
    __tablename__ = "notifications"

    scope = db.Column(db.String(40), default='dashboard')

    id = db.Column(db.Integer, primary_key=True)

    # null = visible to all admins
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=True)

    url = db.Column(db.String(300), nullable=True)

    is_read = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)