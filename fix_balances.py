"""
Script to recalculate and sync all supplier/customer current_balance 
to match actual transaction ledger
"""
from app import create_app
from app.models import Supplier, Customer, StockIn, StockOut, Cashbook
from app.db import db
from decimal import Decimal

app = create_app()

with app.app_context():
    print("🔧 Starting Balance Recalculation...\n")
    
    # Fix Suppliers
    print("📦 Processing Suppliers...")
    suppliers = Supplier.query.all()
    for supplier in suppliers:
        # Calculate actual balance from transactions
        opening = Decimal(str(supplier.opening_balance))
        
        # Add StockIn amounts
        stock_in_total = db.session.query(db.func.sum(StockIn.remaining)).filter(
            StockIn.supplier_id == supplier.id
        ).scalar() or 0
        
        # Subtract Cashbook payments
        cashbook_debit = db.session.query(db.func.sum(Cashbook.amount)).filter(
            Cashbook.reference_type == 'supplier',
            Cashbook.reference_id == supplier.id,
            Cashbook.type == 'debit'
        ).scalar() or 0
        
        cashbook_credit = db.session.query(db.func.sum(Cashbook.amount)).filter(
            Cashbook.reference_type == 'supplier',
            Cashbook.reference_id == supplier.id,
            Cashbook.type == 'credit'
        ).scalar() or 0
        
        calculated_balance = opening + Decimal(str(stock_in_total)) - Decimal(str(cashbook_debit)) + Decimal(str(cashbook_credit))
        
        old_balance = supplier.current_balance
        supplier.current_balance = float(calculated_balance)
        
        print(f"  • {supplier.name}")
        print(f"    Old: {old_balance:,.2f} → New: {calculated_balance:,.2f}")
    
    # Fix Customers
    print("\n👥 Processing Customers...")
    customers = Customer.query.all()
    for customer in customers:
        # Calculate actual balance from transactions
        opening = Decimal(str(customer.opening_balance))
        
        # Add StockOut amounts
        stock_out_total = db.session.query(db.func.sum(StockOut.remaining)).filter(
            StockOut.customer_id == customer.id
        ).scalar() or 0
        
        # Subtract Cashbook payments
        cashbook_credit = db.session.query(db.func.sum(Cashbook.amount)).filter(
            Cashbook.reference_type == 'customer',
            Cashbook.reference_id == customer.id,
            Cashbook.type == 'credit'
        ).scalar() or 0
        
        cashbook_debit = db.session.query(db.func.sum(Cashbook.amount)).filter(
            Cashbook.reference_type == 'customer',
            Cashbook.reference_id == customer.id,
            Cashbook.type == 'debit'
        ).scalar() or 0
        
        calculated_balance = opening + Decimal(str(stock_out_total)) - Decimal(str(cashbook_credit)) + Decimal(str(cashbook_debit))
        
        old_balance = customer.current_balance
        customer.current_balance = float(calculated_balance)
        
        print(f"  • {customer.name}")
        print(f"    Old: {old_balance:,.2f} → New: {calculated_balance:,.2f}")
    
    # Commit changes
    db.session.commit()
    print("\n✅ All balances recalculated and synced successfully!")
