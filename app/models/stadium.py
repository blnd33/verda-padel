# app/models/stadium.py
from app import db
from datetime import datetime


class Stadium(db.Model):
    __tablename__ = 'stadium'

    archived = db.Column(db.Boolean, default=False, server_default='0', nullable=False)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    price_per_hour = db.Column(db.BigInteger, default=None)
    is_active = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(200))
    show_in_pos = db.Column(db.Boolean, default=True)
    show_in_booking = db.Column(db.Boolean, default=True)
    # Amenity badges on the public court card; each shows only when ticked.
    has_led = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    has_ac = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    has_turf = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    has_panoramic = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    bookings = db.relationship('Booking', backref='stadium', lazy=True)

    def __repr__(self):
        return f'<Stadium {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'location': self.location,
            'price_per_hour': self.price_per_hour,
            'is_active': self.is_active,
            'image_url': self.image_url

        }
