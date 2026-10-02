from app import db
from datetime import datetime


class POSOrder(db.Model):
    __tablename__ = 'pos_order'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('pos_session.id'), nullable=False)

    # التفاصيل
    total_price = db.Column(db.BigInteger, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, preparing, ready, delivered
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    items = db.relationship('POSOrderItem', backref='order', lazy=True)

    def __repr__(self):
        return f'<POSOrder {self.id}>'

    def calculate_total(self):
        total = 0
        for item in self.items:
            total += item.price * item.quantity
        self.total_price = total
        return total

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'total_price': self.total_price,
            'status': self.status,
            'created_at': str(self.created_at),
            'items': [item.to_dict() for item in self.items]
        }


class POSOrderItem(db.Model):
    __tablename__ = 'pos_order_item'

    snapshot = db.Column(db.JSON)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('pos_order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.BigInteger, nullable=False)  # السعر وقت الطلب
    currency = db.Column(db.String(3), default='IQD', server_default='IQD', nullable=False)
    # Units given away: the customer pays nothing for them, stock still moves,
    # and reports carry them at their snapshot cost rather than as a sale.
    free_quantity = db.Column(db.Integer, default=0, server_default='0', nullable=False)
    # Line discount on the payable (non-free) units: 'percentage' or 'fixed' IQD.
    discount_kind = db.Column(db.String(20))
    discount_value = db.Column(db.BigInteger, default=0, server_default='0', nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    product = db.relationship('Product', backref='pos_order_items')

    def __repr__(self):
        return f'<POSOrderItem {self.id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name_en if self.product else 'N/A',
            'quantity': self.quantity,
            'price': self.price,
            'subtotal': self.price * self.quantity
        }