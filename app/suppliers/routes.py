from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import Supplier
from app.db import db

suppliers_bp = Blueprint('suppliers', __name__)


# 1. SUPPLIERS LIST VIEW
@suppliers_bp.route('/')
@login_required
def list_suppliers():
    # Database se saare suppliers ko nikalna
    all_suppliers = Supplier.query.order_by(Supplier.id.desc()).all()
    return render_template('suppliers/list.html', suppliers=all_suppliers)


# 2. ADD NEW SUPPLIER
@suppliers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        phone = request.form.get('phone').strip()
        address = request.form.get('address').strip()
        opening_balance = request.form.get('opening_balance', 0)

        if not name:
            flash('برائے مہربانی سپلائر کا نام درج کریں۔', 'danger')
            return redirect(url_for('supplier_bp.add_supplier'))

        try:
            opening_balance = float(opening_balance)
        except ValueError:
            opening_balance = 0.0

        # Naya Supplier Model Object banana
        new_supplier = Supplier(
            name=name,
            phone=phone,
            address=address,
            opening_balance=opening_balance,
            current_balance=opening_balance  # Shuru mein current balance opening ke barabar hoga
        )

        db.session.add(new_supplier)
        db.session.commit()

        flash('سپلائر کا اندراج کامیابی سے کر دیا گیا ہے!', 'success')
        return redirect(url_for('supplier_bp.list_suppliers'))

    return render_template('suppliers/add.html')


# 3. EDIT SUPPLIER
@suppliers_bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)

    if request.method == 'POST':
        supplier.name = request.form.get('name').strip()
        supplier.phone = request.form.get('phone').strip()
        supplier.address = request.form.get('address').strip()

        try:
            old_opening = supplier.opening_balance
            new_opening = float(request.form.get('opening_balance', 0))

            # Balance ka Difference nikalna
            # Agar opening balance barhayein ge to current balance bhi barh jaye ga
            difference = new_opening - old_opening

            supplier.opening_balance = new_opening
            supplier.current_balance += difference  # Live balance mein farq ko adjust kiya

        except ValueError:
            pass

        db.session.commit()
        flash('سپلائر کا ریکارڈ کامیابی سے تبدیل کر دیا گیا ہے!', 'success')
        return redirect(url_for('supplier_bp.list_suppliers'))

    return render_template('suppliers/edit.html', supplier=supplier)
# 4. DELETE SUPPLIER
@suppliers_bp.route('/delete/<int:supplier_id>', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)

    # Yahan check laga sakte hain baad mein ke agar is supplier ka stock-in maujood ho to delete na karne dein
    db.session.delete(supplier)
    db.session.commit()

    flash('سپلائر کا ریکارڈ سسٹم سے ختم کر دیا گیا ہے۔', 'warning')
    return redirect(url_for('supplier_bp.list_suppliers'))