from app import db
from datetime import datetime


class Product(db.Model):
    __tablename__ = 'product'

    track_stock = db.Column(db.Boolean, default=True, server_default='1', nullable=False)
    low_stock_threshold = db.Column(db.Integer, default=5, server_default='5', nullable=False)
    featured = db.Column(db.Boolean, default=False, server_default='0', nullable=False)
    __table_args__ = (db.CheckConstraint('stock >= 0', name='ck_product_stock'),
                     db.CheckConstraint('price >= 0', name='ck_product_price'))

    id = db.Column(db.Integer, primary_key=True)

    name_en = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100))

    description_en = db.Column(db.Text)
    description_ar = db.Column(db.Text)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    # Price and cost share one currency; dollars are stored in cents.
    currency = db.Column(db.String(3), default='IQD', server_default='IQD', nullable=False)
    cost_price = db.Column(db.Integer, default=0)
    price = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)

    show_in_website = db.Column(db.Boolean, default=True)
    show_in_pos = db.Column(db.Boolean, default=True)

    barcode = db.Column(db.String(50), unique=True, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('Category', back_populates='products')

    def __repr__(self):
        return f'<Product {self.name_en}>'

    def get_name(self, lang='en'):
        names = {
            'en': self.name_en,
            'ar': self.name_ar or self.name_en
        }
        return names.get(lang, self.name_en)

    def get_description(self, lang='en'):
        descriptions = {
            'en': self.description_en,
            'ar': self.description_ar or self.description_en
        }
        return descriptions.get(lang, self.description_en)

    @property
    def profit_per_item(self):
        return int(self.price or 0) - int(self.cost_price or 0)

    def to_dict(self):
        return {
            'id': self.id,
            'name_en': self.name_en,
            'name_ar': self.name_ar,
            'category_id': self.category_id,
            'cost_price': self.cost_price,
            'price': self.price,
            'stock': self.stock,
            'image': self.image,
            'is_active': self.is_active,
            'show_in_website': self.show_in_website,
            'show_in_pos': self.show_in_pos,
            'barcode': self.barcode,
            'profit_per_item': self.profit_per_item
        }