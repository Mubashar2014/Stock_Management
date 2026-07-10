from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import Customer
from app.db import db

customers_bp = Blueprint('customers', __name__)


# 1. CUSTOMERS LIST
@customers_bp.route('/')
@login_required
def list_customers():
    all_customers = Customer.query.order_by(Customer.id.desc()).all()
    return render_template('customers/list.html', customers=all_customers)


# 2. ADD CUSTOMER
@customers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        phone = request.form.get('phone').strip()
        address = request.form.get('address').strip()
        opening_balance = request.form.get('opening_balance', 0)

        try:
            opening_balance = float(opening_balance)
        except ValueError:
            opening_balance = 0.0

        new_customer = Customer(
            name=name,
            phone=phone,
            address=address,
            opening_balance=opening_balance,
            current_balance=opening_balance
        )
        db.session.add(new_customer)
        db.session.commit()
        flash('نئے گاہک کا اندراج کامیابی سے کر دیا گیا ہے!', 'success')
        return redirect(url_for('customer_bp.list_customers'))

    return render_template('customers/add.html')


# 3. EDIT CUSTOMER
@customers_bp.route('/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        customer.name = request.form.get('name').strip()
        customer.phone = request.form.get('phone').strip()
        customer.address = request.form.get('address').strip()

        try:
            old_opening = customer.opening_balance
            new_opening = float(request.form.get('opening_balance', 0))
            difference = new_opening - old_opening

            customer.opening_balance = new_opening
            customer.current_balance += difference
        except ValueError:
            pass

        db.session.commit()
        flash('گاہک کا ریکارڈ کامیابی سے تبدیل کر دیا گیا ہے!', 'success')
        return redirect(url_for('customer_bp.list_customers'))

    return render_template('customers/edit.html', customer=customer)


# 4. DELETE CUSTOMER
@customers_bp.route('/delete/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    flash('گاہک کا ریکارڈ سسٹم سے ختم کر دیا گیا ہے۔', 'warning')
    return redirect(url_for('customer_bp.list_customers'))