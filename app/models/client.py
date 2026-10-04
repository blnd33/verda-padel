from datetime import datetime
from app import db


class Client(db.Model):
    """A customer account for people who come often: their bills can be saved
    to the account and paid off whenever they like. The account stays until
    staff delete it."""
    __tablename__ = 'client'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    phone = db.Column(db.String(20))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    debts = db.relationship('ManualDebt', backref='client', lazy=True, order_by='ManualDebt.id')
    sessions = db.relationship('POSSession', backref='client', lazy=True)

    def __repr__(self):
        return f'<Client {self.id} {self.name}>'
