from datetime import datetime
from app import db


class RegularBooking(db.Model):
    """A weekly standing slot for a regular player: the same court, weekday,
    start hour and length every week. The system keeps the next occurrence
    reserved as a real confirmed Booking until staff stop the series."""
    __tablename__ = 'regular_booking'

    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    stadium_id = db.Column(db.Integer, db.ForeignKey('stadium.id'), nullable=False)
    # Business-day weekday (0 = Monday) and start hour, the same meaning as a
    # booking's business date and hour: 1 AM on a "Tuesday" is Tuesday night.
    weekday = db.Column(db.Integer, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    duration_hours = db.Column(db.Integer, nullable=False, default=1)
    starts_on = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, nullable=False, default=True, server_default='1')
    # Last week that could not be reserved because the slot was taken or blocked.
    conflict_on = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    ended_at = db.Column(db.DateTime)
    ended_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    end_reason = db.Column(db.String(255))

    stadium = db.relationship('Stadium')
    bookings = db.relationship('Booking', backref='regular', lazy=True, order_by='Booking.starts_at')

    def __repr__(self):
        return f'<RegularBooking {self.id} {self.customer_name} wd{self.weekday} {self.hour}h>'
