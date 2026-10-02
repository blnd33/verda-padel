from app import db
from datetime import datetime


class POSSession(db.Model):
    __tablename__ = 'pos_session'

    reference = db.Column(db.String(64), unique=True, index=True)
    business_day = db.Column(db.Date, index=True)
    occupancy_key = db.Column(db.String(80), unique=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), unique=True)
    booking = db.relationship('Booking', backref='pos_sessions')
    pricing_snapshot = db.Column(db.JSON)
    venue_snapshot = db.Column(db.JSON)
    location_snapshot = db.Column(db.String(100))
    actual_seconds = db.Column(db.Integer, default=0)
    billed_seconds = db.Column(db.Integer, default=0)
    discount_kind = db.Column(db.String(20))
    discount_value = db.Column(db.Integer, default=0)
    # A fixed invoice discount comes off one currency's total; a percentage off both.
    discount_currency = db.Column(db.String(3), default='IQD', server_default='IQD', nullable=False)
    # Dollar side of the bill (cents); total_amount / manual_discount are the dinar side.
    total_usd = db.Column(db.BigInteger, default=0, server_default='0', nullable=False)
    manual_discount_usd = db.Column(db.BigInteger, default=0, server_default='0', nullable=False)
    finalized_at = db.Column(db.DateTime, index=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    cashier = db.relationship('User')
    stock_restored = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    voided = db.Column(db.Boolean, default=False, server_default='0', nullable=False)

    id = db.Column(db.Integer, primary_key=True)

    session_type = db.Column(db.String(20), nullable=False)

    stadium_id = db.Column(db.Integer, db.ForeignKey('stadium.id'), nullable=True)
    table_id = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=True)

    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))

    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)

    # وقت اللعب
    play_time_minutes = db.Column(db.Integer, default=0)
    play_time_price = db.Column(db.BigInteger, default=0)

    # الخصومات
    auto_discount = db.Column(db.BigInteger, default=0)
    manual_discount = db.Column(db.BigInteger, default=0)
    discount_note = db.Column(db.String(200))

    status = db.Column(db.String(20), default='active')
    payment_method = db.Column(db.String(20))
    total_amount = db.Column(db.BigInteger, default=0)

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stadium = db.relationship('Stadium', backref='pos_sessions')
    table = db.relationship('Table', backref='pos_sessions')
    orders = db.relationship('POSOrder', backref='session', lazy=True)

    def __repr__(self):
        return f'<POSSession {self.id} - {self.session_type}>'

    def get_location_name(self):
        if self.session_type == 'stadium' and self.stadium:
            return self.stadium.name
        elif self.session_type == 'table' and self.table:
            return self.table.name
        elif self.session_type == 'person':
            return self.customer_name
        return 'بيع سريع'

    def get_orders_total(self):
        total = 0
        for order in self.orders:
            total += order.total_price
        return total

    def calculate_total(self):
        orders_total = self.get_orders_total()
        subtotal = self.play_time_price + orders_total
        total_discount = self.auto_discount + self.manual_discount
        self.total_amount = max(0, subtotal - total_discount)
        return self.total_amount

    def to_dict(self):
        return {
            'id': self.id,
            'session_type': self.session_type,
            'location_name': self.get_location_name(),
            'customer_name': self.customer_name,
            'start_time': str(self.start_time),
            'status': self.status,
            'total_amount': self.total_amount,
            'play_time_minutes': self.play_time_minutes,
            'play_time_price': self.play_time_price,
            'auto_discount': self.auto_discount,
            'manual_discount': self.manual_discount,
            'discount_note': self.discount_note,
            'orders_count': len(self.orders)
        }