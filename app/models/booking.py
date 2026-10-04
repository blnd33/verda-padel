from datetime import datetime, timedelta
from app import db


class Booking(db.Model):
    __tablename__ = 'booking'

    reference = db.Column(db.String(64), unique=True, index=True)
    business_day = db.Column(db.Date, index=True)
    starts_at = db.Column(db.DateTime, index=True)
    ends_at = db.Column(db.DateTime, index=True)
    pricing_snapshot = db.Column(db.JSON)
    previous_status = db.Column(db.String(20))
    archived = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    __table_args__ = (db.Index('ix_booking_court_interval', 'stadium_id', 'starts_at', 'ends_at'),
                      # A weekly regular has at most one game per business day.
                      db.UniqueConstraint('regular_id', 'business_day', name='uq_booking_regular_day'))

    id = db.Column(db.Integer, primary_key=True)
    stadium_id = db.Column(db.Integer, db.ForeignKey('stadium.id'), nullable=False)

    # Customer Info
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(100))

    # Booking Details
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration_hours = db.Column(db.Integer, nullable=False)

    # Pricing
    original_price = db.Column(db.BigInteger, nullable=False, default=0)
    discount_percentage = db.Column(db.Integer, default=0)
    discount_amount = db.Column(db.BigInteger, default=0)
    final_price = db.Column(db.BigInteger, nullable=False, default=0)

    # Status: pending, pending_cancel, confirmed, completed, cancelled
    status = db.Column(db.String(20), default='pending')

    # External integration fields (Tapane)
    source = db.Column(db.String(20), nullable=False, default='website')  # website or staff

    # Google Sheets sync tracking

    # Notes and rejection reason
    notes = db.Column(db.Text)
    rejection_reason = db.Column(db.String(255))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime)
    # Weekly regular series this booking belongs to, if any.
    regular_id = db.Column(db.Integer, db.ForeignKey('regular_booking.id'), index=True)
    # Staff dismissed the "it's their time" reminder; it is not shown again.
    start_prompt_declined_at = db.Column(db.DateTime)
    start_prompt_declined_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f'<Booking {self.id} - {self.customer_name} - {self.date}>'

    @property
    def display_date(self):
        return self.business_day or self.date

    @property
    def display_date_str(self):
        """التاريخ كـ string للعرض في الـ templates"""
        d = self.display_date
        return str(d) if d else ''

    def to_dict(self):
        return {
            'id': self.id,
            'stadium_name': self.stadium.name if self.stadium else 'N/A',
            'stadium_id': self.stadium_id,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'customer_email': self.customer_email,
            'date': str(self.date),
            'display_date': self.display_date_str,  # ✅ التاريخ الصحيح للعرض
            'start_time': str(self.start_time) if self.start_time else None,
            'end_time': str(self.end_time) if self.end_time else None,
            'duration_hours': self.duration_hours,
            'original_price': self.original_price,
            'discount_percentage': self.discount_percentage,
            'discount_amount': self.discount_amount,
            'final_price': self.final_price,
            'status': self.status,
            'source': self.source,
            'notes': self.notes,
            'rejection_reason': self.rejection_reason,
            'created_at': str(self.created_at) if self.created_at else None,
            'confirmed_at': str(self.confirmed_at) if self.confirmed_at else None,
        }

    def get_status_badge(self):
        badges = {
            'pending': 'badge-pending',
            'pending_cancel': 'badge-warning',
            'confirmed': 'badge-confirmed',
            'completed': 'badge-completed',
            'cancelled': 'badge-cancelled'
        }
        return badges.get(self.status, 'badge-secondary')

    def get_status_text(self, lang='en'):
        texts = {
            'pending': {
                'ar': 'قيد الانتظار',
                'en': 'Pending'
            },
            'pending_cancel': {
                'ar': 'طلب إلغاء',
                'en': 'Cancel Request'
            },
            'confirmed': {
                'ar': 'مؤكد',
                'en': 'Confirmed'
            },
            'completed': {
                'ar': 'مكتمل',
                'en': 'Completed'
            },
            'cancelled': {
                'ar': 'ملغي',
                'en': 'Cancelled'
            }
        }
        return texts.get(self.status, {}).get(lang, self.status)
