from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import StockIn, Supplier, Material
from app.db import db
from datetime import datetime
from decimal import Decimal

stock_in_bp = Blueprint('stock_in', __name__)


# 1. UPGRADED LIST VIEW WITH DATE FILTERS & TODAY DEFAULT
@stock_in_bp.route('/')
@login_required
def list_stock_in():
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    query = StockIn.query

    # Agar koi filter nahi diya gaya, to default sirf aaj ki transactions dikhani hain
    if not start_date_str and not end_date_str:
        today = datetime.utcnow().date()
        query = query.filter(StockIn.date == today)
    else:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(StockIn.date >= start_date)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(StockIn.date <= end_date)

    all_stock = query.order_by(StockIn.date.desc(), StockIn.id.desc()).all()
    return render_template('stock_in/list.html',
                           entries=all_stock,
                           start_date=start_date_str,
                           end_date=end_date_str)


# 2. ADD TRANSACTION (Unchanged & Working)
@stock_in_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_stock_in():
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id')
        material_id = request.form.get('material_id')
        quantity = Decimal(request.form.get('quantity', 0))
        rate = Decimal(request.form.get('rate', 0))
        other_expenses = Decimal(request.form.get('other_expenses', 0))
        other_expenses_details = request.form.get('other_expenses_details', '').strip()
        paid_amount = Decimal(request.form.get('paid_amount', 0))
        date_str = request.form.get('date')
        notes = request.form.get('notes', '').strip()

        if not supplier_id or not material_id or quantity <= 0 or rate <= 0:
            flash('برائے مہربانی تمام لازمی معلومات صحیح درج کریں۔', 'danger')
            return redirect(url_for('stock_in.add_stock_in'))

        total_amount = (quantity * rate) + other_expenses
        remaining = total_amount - paid_amount
        transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()

        try:
            new_entry = StockIn(
                supplier_id=supplier_id, material_id=material_id, quantity=quantity,
                rate=rate, total_amount=total_amount, other_expenses=other_expenses,
                other_expenses_details=other_expenses_details, paid_amount=paid_amount,
                remaining=remaining, date=transaction_date, notes=notes
            )
            db.session.add(new_entry)

            supplier = Supplier.query.get(supplier_id)
            if supplier:
                supplier.current_balance += float(remaining)

            db.session.commit()
            flash('خریداری کا اندراج کامیابی سے محفوظ کر لیا گیا ہے!', 'success')
            return redirect(url_for('stock_in.list_stock_in'))
        except Exception as e:
            db.session.rollback()
            flash(f'خرابی: {str(e)}', 'danger')
            return redirect(url_for('stock_in.add_stock_in'))

    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    materials = Material.query.order_by(Material.name.asc()).all()
    today = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('stock_in/add.html', suppliers=suppliers, materials=materials, today=today)


# 3. EDIT TRANSACTION WITH FINANCIAL REVERSAL MATH
@stock_in_bp.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_stock_in(entry_id):
    entry = StockIn.query.get_or_404(entry_id)

    if request.method == 'POST':
        old_remaining = entry.remaining
        old_supplier_id = entry.supplier_id

        # Naye inputs receive karna
        supplier_id = request.form.get('supplier_id')
        material_id = request.form.get('material_id')
        quantity = Decimal(request.form.get('quantity', 0))
        rate = Decimal(request.form.get('rate', 0))
        other_expenses = Decimal(request.form.get('other_expenses', 0))
        other_expenses_details = request.form.get('other_expenses_details', '').strip()
        paid_amount = Decimal(request.form.get('paid_amount', 0))
        date_str = request.form.get('date')
        notes = request.form.get('notes', '').strip()

        if not supplier_id or not material_id or quantity <= 0 or rate <= 0:
            flash('تمام لازمی فیلڈز درست بھریں۔', 'danger')
            return redirect(url_for('stock_in.edit_stock_in', entry_id=entry_id))

        new_total_amount = (quantity * rate) + other_expenses
        new_remaining = new_total_amount - paid_amount

        try:
            # Step A: Purane balance ka asar khatam (Reverse) karna
            old_supplier = Supplier.query.get(old_supplier_id)
            if old_supplier:
                old_supplier.current_balance -= float(old_remaining)

            # Step B: Data update karna
            entry.supplier_id = supplier_id
            entry.material_id = material_id
            entry.quantity = quantity
            entry.rate = rate
            entry.total_amount = new_total_amount
            entry.other_expenses = other_expenses
            entry.other_expenses_details = other_expenses_details
            entry.paid_amount = paid_amount
            entry.remaining = new_remaining
            entry.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            entry.notes = notes

            # Step C: Naye balance ka asar supplier par apply karna
            new_supplier = Supplier.query.get(supplier_id)
            if new_supplier:
                new_supplier.current_balance += float(new_remaining)

            db.session.commit()
            flash('خریداری کا ریکارڈ کامیابی سے اپڈیٹ کر دیا گیا ہے!', 'success')
            return redirect(url_for('stock_in.list_stock_in'))

        except Exception as e:
            db.session.rollback()
            flash(f'اپڈیٹ کے دوران خرابی آئی: {str(e)}', 'danger')
            return redirect(url_for('stock_in.edit_stock_in', entry_id=entry_id))

    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    materials = Material.query.order_by(Material.name.asc()).all()
    return render_template('stock_in/edit.html', entry=entry, suppliers=suppliers, materials=materials)


# 4. DELETE TRANSACTION (Unchanged & Working)
@stock_in_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_stock_in(entry_id):
    entry = StockIn.query.get_or_404(entry_id)
    try:
        supplier = Supplier.query.get(entry.supplier_id)
        if supplier:
            supplier.current_balance -= float(entry.remaining)

        db.session.delete(entry)
        db.session.commit()
        flash('خریداری کا ریکارڈ ختم اور سپلائر کا بیلنس ریورس کر دیا گیا ہے۔', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خرابی: {str(e)}', 'danger')

    return redirect(url_for('stock_in.list_stock_in'))