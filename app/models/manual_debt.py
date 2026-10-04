from app import db
from datetime import datetime, date

class ManualDebt(db.Model):
    __tablename__ = "manual_debts"

    session_id = db.Column(db.Integer, db.ForeignKey('pos_session.id'))
    pos_session = db.relationship('POSSession')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Set when the debt sits on a client account; the name/phone copy stays for history.
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), index=True)
    # A bill on debt owes each currency separately, so one debt per bill per currency.
    __table_args__ = (db.CheckConstraint('amount >= 0 AND paid_amount >= 0 AND paid_amount <= amount', name='ck_debt_balance'),
                      db.UniqueConstraint('session_id', 'currency', name='uq_manual_debts_session_currency'))

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)

    amount = db.Column(db.Integer, nullable=False, default=0)      # total debt, minor units
    currency = db.Column(db.String(3), default='IQD', server_default='IQD', nullable=False)
    paid_amount = db.Column(db.Integer, nullable=False, default=0) # paid part

    note = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False, default=date.today)

    status = db.Column(db.String(20), nullable=False, default="open")  # open/paid

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def remaining(self):
        rem = (self.amount or 0) - (self.paid_amount or 0)
        return rem if rem > 0 else 0