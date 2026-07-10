from app.db import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


# 1. USERS MODEL (Authentication) [cite: 17, 18]
class User(UserMixin, db.Model):  # <--- UserMixin yahan lagayein
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# 2. SUPPLIERS MODEL [cite: 19, 20]
class Supplier(db.Model):
    __tablename__ = 'suppliers'
    __table_args__ = {'mysql_collate': 'utf8mb4_unicode_ci'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.Text, nullable=True)

    # Yeh columns lazmi check karein ke isi naam se hain ya nahi:
    opening_balance = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    stocks_in = db.relationship('StockIn', backref='supplier', lazy=True)


# 3. CUSTOMERS MODEL [cite: 23, 24]
class Customer(db.Model):
    __tablename__ = 'customers'
    __table_args__ = {'mysql_collate': 'utf8mb4_unicode_ci'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.Text, nullable=True)
    opening_balance = db.Column(db.Float, default=0.0)  # Shuruati khata
    current_balance = db.Column(db.Float, default=0.0)  # Live khata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    stocks_out = db.relationship('StockOut', backref='customer', lazy=True)


# 4. MATERIALS MODEL [cite: 21, 25]
# 4. MATERIALS MODEL
class Material(db.Model):
    __tablename__ = 'materials'
    __table_args__ = {'mysql_collate': 'utf8mb4_unicode_ci'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(30), nullable=False)  # e.g., kg, meter, piece
    image_file = db.Column(db.String(100), nullable=False, default='default_material.png') # <--- New Image Column
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    stocks_in = db.relationship('StockIn', backref='material', lazy=True)
    stocks_out = db.relationship('StockOut', backref='material', lazy=True)


# 5. STOCK_IN MODEL (Material Purchases) [cite: 21, 22]
class StockIn(db.Model):
    __tablename__ = 'stock_in'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)  # qty * rate
    other_expenses = db.Column(db.Numeric(12, 2), default=0.00)
    other_expenses_details = db.Column(db.Text, nullable=True)
    paid_amount = db.Column(db.Numeric(12, 2), default=0.00)
    remaining = db.Column(db.Numeric(12, 2), nullable=False)  # Auto calculated
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# 6. STOCK_OUT MODEL (Material Sales) [cite: 25, 26]
class StockOut(db.Model):
    __tablename__ = 'stock_out'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)

    # Nayi Columns
    other_expenses = db.Column(db.Numeric(12, 2), default=0.00)
    other_expenses_details = db.Column(db.Text, nullable=True)
    discount = db.Column(db.Numeric(12, 2), default=0.00)  # Naya discount column

    total_amount = db.Column(db.Numeric(12, 2), nullable=False)  # (qty * rate) + expenses - discount
    paid_amount = db.Column(db.Numeric(12, 2), default=0.00)
    remaining = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)




# 7. CASHBOOK MODEL [cite: 31, 32]
class Cashbook(db.Model):
    __tablename__ = 'cashbook'
    __table_args__ = {'mysql_collate': 'utf8mb4_unicode_ci'}

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Enum('credit', 'debit', name='cashbook_type'), nullable=False)  # credit=In, debit=Out
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reference_type = db.Column(db.Enum('supplier', 'customer', 'other', name='ref_type'), nullable=False)
    reference_id = db.Column(db.Integer, nullable=True)  # Loose linking to keep dynamic logs clean
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

