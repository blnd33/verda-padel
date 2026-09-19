# app/models/expense.py
from app import db
from datetime import datetime


class Expense(db.Model):
    """
    نموذج المصاريف - Expense Model
    لتتبع جميع مصاريف النادي اليومية
    """
    __tablename__ = 'expense'

    voided = db.Column(db.Boolean, default=False, server_default='0', nullable=False)

    id = db.Column(db.Integer, primary_key=True)

    # Basic Info
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)  # رواتب، فواتير، صيانة، إلخ
    amount = db.Column(db.Integer, nullable=False)  # المبلغ بالدينار العراقي

    # Description
    description = db.Column(db.String(500))  # الوصف

    # Payment Info
    payment_method = db.Column(db.String(20), default='cash')  # cash, card

    # Reference (optional)
    reference_number = db.Column(db.String(100))  # رقم الفاتورة أو المرجع

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Who created it (optional)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return f'<Expense {self.id}: {self.category} - {self.amount} IQD>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'category': self.category,
            'amount': self.amount,
            'description': self.description,
            'payment_method': self.payment_method,
            'reference_number': self.reference_number,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @staticmethod
    def get_categories():
        """Get list of expense categories"""
        return {
            'salaries': 'رواتب',
            'bills': 'فواتير',
            'maintenance': 'صيانة',
            'cleaning': 'تنظيف',
            'purchases': 'مشتريات',
            'transportation': 'نقل',
            'hospitality': 'ضيافة',
            'rent': 'إيجار',
            'marketing': 'تسويق',
            'other': 'أخرى'
        }

    def get_category_name(self):
        """Get Arabic name of category"""
        categories = self.get_categories()
        return categories.get(self.category, self.category)