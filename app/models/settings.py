from app import db
from datetime import datetime


class Settings(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)

    # أوقات العمل
    opening_hour = db.Column(db.Integer, default=9)
    closing_hour = db.Column(db.Integer, default=23)

    # الأسعار
    price_per_hour = db.Column(db.Integer, default=0)

    # Higher evening rate; zero keeps a single rate all day.
    evening_rate = db.Column(db.Integer, default=0, server_default='0', nullable=False)
    evening_start_hour = db.Column(db.Integer, default=18, server_default='18', nullable=False)
    evening_end_hour = db.Column(db.Integer, default=0, server_default='0', nullable=False)

    # الخصم
    discount_percentage = db.Column(db.Integer, default=0)
    discount_amount = db.Column(db.Integer, default=0)
    discount_start_hour = db.Column(db.Integer, default=0)
    discount_end_hour = db.Column(db.Integer, default=0)

    # معلومات الموقع
    site_name = db.Column(db.String(100), default='Verda Padel')
    configured = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    demo_mode = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    default_language = db.Column(db.String(4), default='en', server_default='en', nullable=False)
    timezone = db.Column(db.String(80), default='Asia/Baghdad', server_default='Asia/Baghdad', nullable=False)
    minimum_minutes = db.Column(db.Integer, default=60, server_default='60', nullable=False)
    rounding_minutes = db.Column(db.Integer, default=60, server_default='60', nullable=False)
    max_booking_hours = db.Column(db.Integer, default=4, server_default='4', nullable=False)
    booking_days_ahead = db.Column(db.Integer, default=30, server_default='30', nullable=False)
    delivery_enabled = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    delivery_fee = db.Column(db.BigInteger, default=0, server_default='0', nullable=False)
    directions_url = db.Column(db.String(300))
    # "latitude,longitude" of the venue; drives the website map and directions.
    map_coordinates = db.Column(db.String(60))
    receipt_width = db.Column(db.Integer, default=80, server_default='80', nullable=False)
    auto_print = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    label_size = db.Column(db.String(20), default='50x30', server_default='50x30', nullable=False)
    content = db.Column(db.JSON, default=dict)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)

    # Social Media
    facebook_url = db.Column(db.String(200))
    instagram_url = db.Column(db.String(200))
    twitter_url = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Settings {self.site_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'opening_hour': self.opening_hour,
            'closing_hour': self.closing_hour,
            'price_per_hour': self.price_per_hour,
            'discount_percentage': self.discount_percentage,
            'discount_amount': self.discount_amount,
            'discount_start_hour': self.discount_start_hour,
            'discount_end_hour': self.discount_end_hour,
            'site_name': self.site_name,
            'phone': self.phone,
            'email': self.email,
            'address': self.address
        }
