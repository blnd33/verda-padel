# app/models/order.py
from app import db
from datetime import datetime


class Order(db.Model):
    __tablename__ = 'order'

    reference = db.Column(db.String(64), unique=True, index=True)
    delivery_fee = db.Column(db.BigInteger, default=0, server_default='0', nullable=False)
    business_day = db.Column(db.Date, index=True)
    venue_snapshot = db.Column(db.JSON)
    finalized_at = db.Column(db.DateTime)
    stock_restored = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    voided = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    archived = db.Column(db.Boolean, default=False, server_default='0', nullable=False)

    id = db.Column(db.Integer, primary_key=True)

    # Customer Info
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(100))

    # Delivery / Pickup
    delivery_method = db.Column(db.String(20), default='delivery', nullable=False)  # delivery | pickup

    # Address (only used if delivery_method == 'delivery')
    area = db.Column(db.String(100))  # e.g. Duhok / Malta / ...
    address = db.Column(db.Text)      # detailed address

    # Order Details
    total_price = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, processing, delivered, cancelled
    notes = db.Column(db.Text)

    # ✅ Google Sheets sync tracking (send only after admin confirmation)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    items = db.relationship(
        'OrderItem',
        backref='order',
        lazy=True,
    )

    def __repr__(self):
        return f'<Order {self.id} - {self.customer_name}>'

    # ----------------- Helpers -----------------
    @property
    def is_delivery(self) -> bool:
        return (self.delivery_method or '').lower() == 'delivery'

    @property
    def is_pickup(self) -> bool:
        return (self.delivery_method or '').lower() == 'pickup'

    def normalize_address_for_pickup(self):
        """
        If pickup: make sure address fields are empty in DB.
        Call this before saving (optional but recommended).
        """
        if self.is_pickup:
            self.area = None
            self.address = None

    def validate(self):
        """
        Simple validation rules:
        - delivery: address should exist (optionally also area)
        - pickup: no address required
        """
        method = (self.delivery_method or '').lower().strip()
        if method not in ('delivery', 'pickup'):
            raise ValueError("delivery_method must be 'delivery' or 'pickup'")

        if method == 'delivery':
            if not self.address or not str(self.address).strip():
                raise ValueError("Address is required for delivery")
            # If you want to force area too, uncomment:
            # if not self.area or not str(self.area).strip():
            #     raise ValueError("Area is required for delivery")

        if method == 'pickup':
            self.area = None
            self.address = None

    def to_dict(self):
        return {
            'id': self.id,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'customer_email': self.customer_email,

            'delivery_method': self.delivery_method,
            'is_delivery': self.is_delivery,
            'is_pickup': self.is_pickup,

            'area': self.area if self.is_delivery else None,
            'address': self.address if self.is_delivery else None,

            'total_price': self.total_price,
            'status': self.status,
            'notes': self.notes,

            # ✅ Sheet tracking

            'created_at': self.created_at.isoformat() if self.created_at else None,
            'items': [item.to_dict() for item in (self.items or [])]
        }


class OrderItem(db.Model):
    __tablename__ = 'order_item'

    snapshot = db.Column(db.JSON)

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.BigInteger, nullable=False)

    # Relationships
    product = db.relationship('Product', backref='order_items')

    def __repr__(self):
        return f'<OrderItem {self.id} - Order {self.order_id}>'

    def to_dict(self):
        product_name = self.product.name_en if self.product else 'N/A'

        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': product_name,
            'quantity': int(self.quantity or 0),
            'price': float(self.price or 0)
        }
