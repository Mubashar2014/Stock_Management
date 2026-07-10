from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.models import Cashbook, Supplier, Customer
from app.db import db
from datetime import datetime, timedelta
from decimal import Decimal

cashbook_bp = Blueprint('cashbook', __name__)


@cashbook_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # 1. DATE SELECTION
    date_param = request.args.get('date', '').strip()
    if date_param:
        try:
            view_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            view_date = datetime.utcnow().date()
    else:
        view_date = datetime.utcnow().date()

    view_date_str = view_date.strftime('%Y-%m-%d')
    prev_date_str = (view_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date_str = (view_date + timedelta(days=1)).strftime('%Y-%m-%d')
    today_str = datetime.utcnow().date().strftime('%Y-%m-%d')

    # 2. SINGLE PAGE EDIT MODE
    edit_entry = None
    edit_id = request.args.get('edit_id')
    if edit_id:
        edit_entry = Cashbook.query.get(edit_id)

    # 3. FORM SUBMISSION (ADD / UPDATE)
    if request.method == 'POST':
        form_id = request.form.get('entry_id')
        date_str = request.form.get('date')
        cash_type = request.form.get('type')
        reference_type = request.form.get('reference_type')
        reference_id = request.form.get('reference_id')
        description = request.form.get('description', '').strip()
        amount = Decimal(request.form.get('amount', 0))

        if not cash_type or amount <= 0 or not description:
            flash('براہ کرم تمام فیلڈز درست پُر کریں۔', 'danger')
            return redirect(url_for('cashbook.index', date=view_date_str))

        transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        ref_id_val = int(reference_id) if (reference_type in ['supplier', 'customer'] and reference_id) else None

        try:
            if form_id:  # EDIT UPDATE
                entry = Cashbook.query.get_or_404(form_id)
                entry.date = transaction_date
                entry.type = cash_type
                entry.reference_type = reference_type
                entry.reference_id = ref_id_val
                entry.description = description
                entry.amount = amount
                flash('اندراج کامیابی سے تبدیل ہو گیا!', 'success')
            else:  # NEW ADDITION
                new_entry = Cashbook(
                    date=transaction_date, type=cash_type, amount=amount,
                    reference_type=reference_type, reference_id=ref_id_val, description=description
                )
                db.session.add(new_entry)
                flash('نیا اندراج کامیابی سے محفوظ ہو گیا!', 'success')

            db.session.commit()
            return redirect(url_for('cashbook.index', date=transaction_date.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            flash(f'خرابی: {str(e)}', 'danger')

    # 4. OPENING BALANCE CALCULATION (Pichle Dino Ka Net Totals)
    prior_credit = db.session.query(db.func.sum(Cashbook.amount)).filter(Cashbook.date < view_date,
                                                                         Cashbook.type == 'credit').scalar() or 0
    prior_debit = db.session.query(db.func.sum(Cashbook.amount)).filter(Cashbook.date < view_date,
                                                                        Cashbook.type == 'debit').scalar() or 0
    opening_balance = Decimal(prior_credit) - Decimal(prior_debit)

    # 5. CURRENT SELECTED DAY DATA
    current_entries = Cashbook.query.filter(Cashbook.date == view_date).order_by(Cashbook.id.asc()).all()

    day_credit_list = [e for e in current_entries if e.type == 'credit']
    day_debit_list = [e for e in current_entries if e.type == 'debit']

    # Day totals for internal math
    day_credit_total = sum(Decimal(e.amount) for e in day_credit_list)
    day_debit_total = sum(Decimal(e.amount) for e in day_debit_list)

    # Shifting Opening Balance into view variables for presentation
    if opening_balance > 0:
        display_opening_credit = opening_balance
        display_opening_debit = Decimal(0)
    else:
        display_opening_credit = Decimal(0)
        display_opening_debit = abs(opening_balance)

    # Current Day Net View Totals
    view_total_credit = day_credit_total + display_opening_credit
    view_total_debit = day_debit_total + display_opening_debit
    day_net_balance = view_total_credit - view_total_debit

    # 6. ALL TIME CUMULATIVE STATS (For Bottom Bar)
    all_time_credit = db.session.query(db.func.sum(Cashbook.amount)).filter(Cashbook.type == 'credit').scalar() or 0
    all_time_debit = db.session.query(db.func.sum(Cashbook.amount)).filter(Cashbook.type == 'debit').scalar() or 0
    all_time_balance = Decimal(all_time_credit) - Decimal(all_time_debit)

    # Dropdowns
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    customers = Customer.query.order_by(Customer.name.asc()).all()

    return render_template(
        'cashbook/index.html',
        credit_entries=day_credit_list,
        debit_entries=day_debit_list,
        opening_balance=opening_balance,
        display_opening_credit=display_opening_credit,
        display_opening_debit=display_opening_debit,
        view_total_credit=view_total_credit,
        view_total_debit=view_total_debit,
        day_net_balance=day_net_balance,
        all_time_credit=all_time_credit,
        all_time_debit=all_time_debit,
        all_time_balance=all_time_balance,
        suppliers=suppliers,
        customers=customers,
        today=today_str,
        view_date=view_date_str,
        prev_date=prev_date_str,
        next_date=next_date_str,
        edit_entry=edit_entry
    )
@cashbook_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = Cashbook.query.get_or_404(entry_id)
    if entry.reference_type in ['supplier', 'customer'] and entry.reference_id is not None:
        flash('یہ اندراج بلنگ فارم سے خودکار طور پر تیار ہوا ہے، اسے وہاں سے ہی ختم کیا جا سکتا ہے۔', 'danger')
        return redirect(url_for('cashbook.index'))

    try:
        db.session.delete(entry)
        db.session.commit()
        flash('ریکارڈ کامیابی سے ختم کر دیا گیا ہے۔', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خرابی: {str(e)}', 'danger')
    return redirect(url_for('cashbook.index'))