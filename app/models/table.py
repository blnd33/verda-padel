from app import db
from datetime import datetime


class Table(db.Model):
    __tablename__ = 'table'

    archived = db.Column(db.Boolean, default=False, server_default='0', nullable=False)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # طاولة 1، طاولة 2...
    capacity = db.Column(db.Integer, default=4)  # عدد الكراسي
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Table {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'capacity': self.capacity,
            'is_active': self.is_active
        }