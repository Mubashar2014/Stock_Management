from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import StockOut, Customer, Material,StockIn
from app.db import db
from datetime import datetime
from decimal import Decimal

stock_out_bp = Blueprint('stock_out', __name__)


# 1. LIST VIEW WITH DATE FILTERS & TODAY DEFAULT
@stock_out_bp.route('/')
@login_required
def list_stock_out():
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    query = StockOut.query

    if not start_date_str and not end_date_str:
        today = datetime.utcnow().date()
        query = query.filter(StockOut.date == today)
    else:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(StockOut.date >= start_date)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(StockOut.date <= end_date)

    all_sales = query.order_by(StockOut.date.desc(), StockOut.id.desc()).all()
    return render_template('stock_out/list.html', entries=all_sales, start_date=start_date_str, end_date=end_date_str)


# File ke sab se upar yeh line check karein ya add karein:
from sqlalchemy import func

# Aap ka updated add_stock_out route:
@stock_out_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_stock_out():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        material_id = request.form.get('material_id')
        quantity = Decimal(request.form.get('quantity', 0))
        rate = Decimal(request.form.get('rate', 0))
        other_expenses = Decimal(request.form.get('other_expenses', 0) or 0)
        other_expenses_details = request.form.get('other_expenses_details', '').strip()
        discount = Decimal(request.form.get('discount', 0) or 0)
        paid_amount = Decimal(request.form.get('paid_amount', 0) or 0)
        date_str = request.form.get('date')
        notes = request.form.get('notes', '').strip()

        if not customer_id or not material_id or quantity <= 0 or rate <= 0:
            flash('برائے مہربانی تمام لازمی معلومات صحیح درج کریں۔', 'danger')
            return redirect(url_for('stock_out.add_stock_out'))

        # --- LIVE STOCK CHECK LOGIC ---
        total_in = db.session.query(func.sum(StockIn.quantity)).filter(StockIn.material_id == material_id).scalar() or 0
        total_out = db.session.query(func.sum(StockOut.quantity)).filter(StockOut.material_id == material_id).scalar() or 0
        available_stock = Decimal(total_in - total_out)

        if quantity > available_stock:
            material = Material.query.get(material_id)
            unit_name = material.unit if material else ''
            flash(f'ناکام! مطلوبہ مقدار دستیاب نہیں ہے۔ آپ کے پاس کل {available_stock} {unit_name} اسٹاک موجود ہے۔', 'danger')
            return redirect(url_for('stock_out.add_stock_out'))
        # ------------------------------

        total_amount = (quantity * rate) + other_expenses - discount
        remaining = total_amount - paid_amount
        transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()

        try:
            new_entry = StockOut(
                customer_id=customer_id, material_id=material_id, quantity=quantity,
                rate=rate, other_expenses=other_expenses, other_expenses_details=other_expenses_details,
                discount=discount, total_amount=total_amount, paid_amount=paid_amount,
                remaining=remaining, date=transaction_date, notes=notes
            )
            db.session.add(new_entry)

            customer = Customer.query.get(customer_id)
            if customer:
                customer.current_balance += float(remaining)

            db.session.commit()
            flash('فروخت کا اندراج کامیابی سے محفوظ کر لیا گیا ہے!', 'success')
            return redirect(url_for('stock_out.list_stock_out'))
        except Exception as e:
            db.session.rollback()
            flash(f'خرابی: {str(e)}', 'danger')
            return redirect(url_for('stock_out.add_stock_out'))

    customers = Customer.query.order_by(Customer.name.asc()).all()
    materials = Material.query.order_by(Material.name.asc()).all()
    today = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('stock_out/add.html', customers=customers, materials=materials, today=today)


@stock_out_bp.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_stock_out(entry_id):
    entry = StockOut.query.get_or_404(entry_id)

    if request.method == 'POST':
        old_remaining = entry.remaining
        old_customer_id = entry.customer_id
        old_quantity = entry.quantity  # Purani quantity save kar li

        customer_id = request.form.get('customer_id')
        material_id = request.form.get('material_id')
        quantity = Decimal(request.form.get('quantity', 0))
        rate = Decimal(request.form.get('rate', 0))
        other_expenses = Decimal(request.form.get('other_expenses', 0) or 0)
        other_expenses_details = request.form.get('other_expenses_details', '').strip()
        discount = Decimal(request.form.get('discount', 0) or 0)
        paid_amount = Decimal(request.form.get('paid_amount', 0) or 0)
        date_str = request.form.get('date')
        notes = request.form.get('notes', '').strip()

        if not customer_id or not material_id or quantity <= 0 or rate <= 0:
            flash('تمام لازمی فیلڈز درست بھریں۔', 'danger')
            return redirect(url_for('stock_out.edit_stock_out', entry_id=entry_id))

        # --- LIVE STOCK CHECK FOR EDIT ---
        total_in = db.session.query(func.sum(StockIn.quantity)).filter(StockIn.material_id == material_id).scalar() or 0
        total_out = db.session.query(func.sum(StockOut.quantity)).filter(
            StockOut.material_id == material_id).scalar() or 0

        # Agar material same hai, to is entry ki purani quantity stock mein wapas shamil karke check karenge
        if int(material_id) == entry.material_id:
            available_stock = Decimal(total_in - total_out) + Decimal(old_quantity)
        else:
            available_stock = Decimal(total_in - total_out)

        if quantity > available_stock:
            material = Material.query.get(material_id)
            unit_name = material.unit if material else ''
            flash(f'ناکام! تصحیح شدہ مقدار دستیاب نہیں ہے۔ اس مٹیریل کا کل اسٹاک {available_stock} {unit_name} ہے۔',
                  'danger')
            return redirect(url_for('stock_out.edit_stock_out', entry_id=entry_id))
        # ----------------------------------

        new_total_amount = (quantity * rate) + other_expenses - discount
        new_remaining = new_total_amount - paid_amount

        try:
            old_customer = Customer.query.get(old_customer_id)
            if old_customer:
                old_customer.current_balance -= float(old_remaining)

            entry.customer_id = customer_id
            entry.material_id = material_id
            entry.quantity = quantity
            entry.rate = rate
            entry.other_expenses = other_expenses
            entry.other_expenses_details = other_expenses_details
            entry.discount = discount
            entry.total_amount = new_total_amount
            entry.paid_amount = paid_amount
            entry.remaining = new_remaining
            entry.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            entry.notes = notes

            new_customer = Customer.query.get(customer_id)
            if new_customer:
                new_customer.current_balance += float(new_remaining)

            db.session.commit()
            flash('فروخت کا ریکارڈ کامیابی سے اپڈیٹ کر دیا گیا ہے!', 'success')
            return redirect(url_for('stock_out.list_stock_out'))

        except Exception as e:
            db.session.rollback()
            flash(f'خرابی: {str(e)}', 'danger')
            return redirect(url_for('stock_out.edit_stock_out', entry_id=entry_id))

    customers = Customer.query.order_by(Customer.name.asc()).all()
    materials = Material.query.order_by(Material.name.asc()).all()
    return render_template('stock_out/edit.html', entry=entry, customers=customers, materials=materials)
# 4. DELETE SALE
@stock_out_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_stock_out(entry_id):
    entry = StockOut.query.get_or_404(entry_id)
    try:
        customer = Customer.query.get(entry.customer_id)
        if customer:
            customer.current_balance -= float(entry.remaining)

        db.session.delete(entry)
        db.session.commit()
        flash('فروخت کا ریکارڈ ختم اور گاہک کا بیلنس ریورس کر دیا گیا ہے۔', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خرابی: {str(e)}', 'danger')

    return redirect(url_for('stock_out.list_stock_out'))