from app import db
from datetime import datetime, date

class ManualDebt(db.Model):
    __tablename__ = "manual_debts"

    session_id = db.Column(db.Integer, db.ForeignKey('pos_session.id'), unique=True)
    pos_session = db.relationship('POSSession')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    __table_args__ = (db.CheckConstraint('amount >= 0 AND paid_amount >= 0 AND paid_amount <= amount', name='ck_debt_balance'),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)

    amount = db.Column(db.Integer, nullable=False, default=0)      # total debt
    paid_amount = db.Column(db.Integer, nullable=False, default=0) # paid part

    note = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False, default=date.today)

    status = db.Column(db.String(20), nullable=False, default="open")  # open/paid

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def remaining(self):
        rem = (self.amount or 0) - (self.paid_amount or 0)
        return rem if rem > 0 else 0