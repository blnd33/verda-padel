# app/models/category.py
from app import db
from datetime import datetime


class Category(db.Model):
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True)

    # Multilingual names
    name_en = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100))

    # Multilingual descriptions
    description_en = db.Column(db.Text)
    description_ar = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)

    # ✅ NEW: where to show this category
    show_on_website = db.Column(db.Boolean, default=True, nullable=False)
    show_on_pos = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ FIX: use back_populates instead of backref to avoid duplicate "products"
    products = db.relationship('Product', back_populates='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name_en}>'

    def get_name(self, lang='en'):
        """Get name in specified language"""
        names = {
            'en': self.name_en,
            'ar': self.name_ar or self.name_en
        }
        return names.get(lang, self.name_en)

    def to_dict(self):
        return {
            'id': self.id,
            'name_en': self.name_en,
            'name_ar': self.name_ar,
            'description_en': self.description_en,
            'description_ar': self.description_ar,
            'is_active': self.is_active,

            # ✅ NEW
            'show_on_website': self.show_on_website,
            'show_on_pos': self.show_on_pos,

            'created_at': self.created_at.isoformat() if self.created_at else None
        }