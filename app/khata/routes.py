from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import Supplier, Customer, StockIn, StockOut, Cashbook
from app.db import db
from sqlalchemy import func
from decimal import Decimal
from datetime import datetime, date

khata_bp = Blueprint('khata', __name__)


@khata_bp.route('/')
@login_required
def index():
    """Main khata page — shows supplier/customer selector panel."""
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    customers = Customer.query.order_by(Customer.name.asc()).all()
    return render_template(
        'khata/index.html',
        suppliers=suppliers,
        customers=customers,
        person=None,
        ledger_rows=[],
        person_type=None,
        start_date='',
        end_date='',
        closing_balance=Decimal('0'),
    )


@khata_bp.route('/<string:person_type>/<int:person_id>')
@login_required
def khata_detail(person_type, person_id):
    """Detailed ledger for a specific supplier or customer."""
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    customers = Customer.query.order_by(Customer.name.asc()).all()

    # Validate person_type
    if person_type not in ('supplier', 'customer'):
        return render_template(
            'khata/index.html',
            suppliers=suppliers, customers=customers,
            person=None, ledger_rows=[], person_type=None,
            start_date='', end_date='', closing_balance=Decimal('0'),
        )

    # Load the person
    if person_type == 'supplier':
        person = Supplier.query.get_or_404(person_id)
    else:
        person = Customer.query.get_or_404(person_id)

    # Date filters
    today_str = date.today().strftime('%Y-%m-%d')
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str   = request.args.get('end_date', today_str).strip()

    try:
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        end_dt = date.today()

    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_dt = None
    else:
        start_dt = None

    # ── Build chronological ledger ──────────────────────────────────────
    # Opening balance = person's opening_balance (pre-system balance)
    opening_balance = Decimal(str(person.opening_balance))

    rows = []  # Each row: {date, description, debit, credit, balance}

    # Row 0 — opening balance entry
    rows.append({
        'date': None,
        'description': 'ابتدائی بقایا (Opening Balance)',
        'debit':  opening_balance if opening_balance > 0 else Decimal('0'),
        'credit': abs(opening_balance) if opening_balance < 0 else Decimal('0'),
        'is_opening': True,
    })

    # Collect all transactions from DB (no date filter on select — apply after)
    if person_type == 'supplier':
        stock_transactions = (
            StockIn.query
            .filter_by(supplier_id=person_id)
            .order_by(StockIn.date.asc(), StockIn.id.asc())
            .all()
        )
        payments = (
            Cashbook.query
            .filter_by(reference_type='supplier', reference_id=person_id)
            .order_by(Cashbook.date.asc(), Cashbook.id.asc())
            .all()
        )
    else:
        stock_transactions = (
            StockOut.query
            .filter_by(customer_id=person_id)
            .order_by(StockOut.date.asc(), StockOut.id.asc())
            .all()
        )
        payments = (
            Cashbook.query
            .filter_by(reference_type='customer', reference_id=person_id)
            .order_by(Cashbook.date.asc(), Cashbook.id.asc())
            .all()
        )

    # Merge stock transactions + payments into one sorted list
    events = []
    for tx in stock_transactions:
        events.append({
            'date': tx.date,
            'type': 'transaction',
            'obj': tx,
        })
    for p in payments:
        events.append({
            'date': p.date,
            'type': 'payment',
            'obj': p,
        })

    # Sort by date then id-like order
    events.sort(key=lambda e: (e['date'], e['type']))

    for ev in events:
        obj = ev['obj']
        ev_date = ev['date']

        if ev['type'] == 'transaction':
            # For supplier: StockIn → money owed to supplier (debit)
            # For customer: StockOut → money owed by customer (debit)
            if person_type == 'supplier':
                desc = f"خریداری — {obj.material.name if obj.material else '?'} ({obj.quantity} {obj.material.unit if obj.material else ''})"
            else:
                desc = f"فروخت — {obj.material.name if obj.material else '?'} ({obj.quantity} {obj.material.unit if obj.material else ''})"
            rows.append({
                'date': ev_date,
                'description': desc,
                'debit':  Decimal(str(obj.total_amount)),
                'credit': Decimal('0'),
                'is_opening': False,
            })
            # If partial payment was made at the time of transaction
            if obj.paid_amount and Decimal(str(obj.paid_amount)) > 0:
                rows.append({
                    'date': ev_date,
                    'description': 'ادائیگی (لین دین کے ساتھ)',
                    'debit':  Decimal('0'),
                    'credit': Decimal(str(obj.paid_amount)),
                    'is_opening': False,
                })
        else:
            # Cashbook payment
            obj_p = ev['obj']
            if obj_p.type == 'credit':
                # Credit in cashbook = money received = reduces what customer owes
                rows.append({
                    'date': ev_date,
                    'description': obj_p.description or 'ادائیگی (کیش بک)',
                    'debit':  Decimal('0'),
                    'credit': Decimal(str(obj_p.amount)),
                    'is_opening': False,
                })
            else:
                # Debit in cashbook for supplier = payment to supplier
                rows.append({
                    'date': ev_date,
                    'description': obj_p.description or 'ادائیگی (کیش بک)',
                    'debit':  Decimal('0'),
                    'credit': Decimal(str(obj_p.amount)),
                    'is_opening': False,
                })

    # ── Compute running balance & apply date filter ────────────────────
    running = Decimal('0')
    filtered_rows = []

    for row in rows:
        running = running + row['debit'] - row['credit']
        row['balance'] = running

        # Apply date filter (opening row always shown, others filtered)
        if row.get('is_opening'):
            filtered_rows.append(row)
            continue

        if start_dt and row['date'] < start_dt:
            # Don't show but keep running balance up to start
            filtered_rows = [r for r in filtered_rows if r.get('is_opening')]
            # Adjust opening row's balance to pre-start running balance
            if filtered_rows:
                filtered_rows[0]['balance'] = running - row['debit'] + row['credit']
            continue

        if row['date'] > end_dt:
            continue

        filtered_rows.append(row)

    # Recalculate running balance cleanly on filtered rows
    balance = Decimal('0')
    for row in filtered_rows:
        if row.get('is_opening'):
            balance = opening_balance
            row['balance'] = balance
        else:
            balance = balance + row['debit'] - row['credit']
            row['balance'] = balance

    closing_balance = balance

    return render_template(
        'khata/index.html',
        suppliers=suppliers,
        customers=customers,
        person=person,
        person_type=person_type,
        person_id=person_id,
        ledger_rows=filtered_rows,
        start_date=start_date_str,
        end_date=end_date_str,
        closing_balance=closing_balance,
        today=today_str,
    )
