from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import StockIn, StockOut, Material, Cashbook
from app.db import db
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import calendar

profit_bp = Blueprint('profit', __name__)


def _decimal(val):
    """Safely convert any value to Decimal."""
    if val is None:
        return Decimal('0')
    return Decimal(str(val))


def _weighted_avg_cost(material_id, up_to_date):
    """
    Calculate the weighted average purchase cost per unit for a material,
    considering all StockIn entries up to and including up_to_date.
    Cost per unit = (sum of total_amount + other_expenses) / sum of quantity
    """
    result = db.session.query(
        func.sum(StockIn.total_amount + StockIn.other_expenses),
        func.sum(StockIn.quantity)
    ).filter(
        StockIn.material_id == material_id,
        StockIn.date <= up_to_date
    ).one()

    total_cost = _decimal(result[0])
    total_qty  = _decimal(result[1])

    if total_qty == 0:
        return Decimal('0')
    return (total_cost / total_qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _build_report(start_dt, end_dt):
    """
    Core calculation engine.
    Returns a dict with all figures needed by the template.
    """

    # ── 1. Sales in period ─────────────────────────────────────────────
    sales = (
        StockOut.query
        .filter(StockOut.date >= start_dt, StockOut.date <= end_dt)
        .order_by(StockOut.date.asc(), StockOut.id.asc())
        .all()
    )

    # ── 2. Per-material aggregation ────────────────────────────────────
    # Group by material_id
    material_map = {}  # material_id → aggregated data
    for s in sales:
        mid = s.material_id
        if mid not in material_map:
            material_map[mid] = {
                'material': s.material,
                'qty_sold':  Decimal('0'),
                'revenue':   Decimal('0'),
                'cost':      Decimal('0'),
            }
        material_map[mid]['qty_sold'] += _decimal(s.quantity)
        material_map[mid]['revenue']  += _decimal(s.total_amount)

    # Assign weighted avg cost for each material
    for mid, data in material_map.items():
        avg_cost = _weighted_avg_cost(mid, end_dt)
        data['avg_cost_per_unit'] = avg_cost
        data['cost']              = (data['qty_sold'] * avg_cost).quantize(
                                        Decimal('0.01'), rounding=ROUND_HALF_UP)
        data['gross_profit']      = data['revenue'] - data['cost']
        data['profit_per_unit']   = (
            (data['gross_profit'] / data['qty_sold']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if data['qty_sold'] > 0 else Decimal('0')
        )

    material_rows = sorted(material_map.values(), key=lambda x: x['material'].name)

    # ── 3. Totals ──────────────────────────────────────────────────────
    total_revenue      = sum(r['revenue']      for r in material_rows)
    total_cost         = sum(r['cost']         for r in material_rows)
    total_gross_profit = sum(r['gross_profit'] for r in material_rows)

    # ── 4. Cashbook overhead expenses (debit, type=other) ─────────────
    overhead_entries = (
        Cashbook.query
        .filter(
            Cashbook.date >= start_dt,
            Cashbook.date <= end_dt,
            Cashbook.type == 'debit',
            Cashbook.reference_type == 'other'
        )
        .order_by(Cashbook.date.asc())
        .all()
    )
    total_overhead = sum(_decimal(e.amount) for e in overhead_entries)

    # ── 5. Net profit ──────────────────────────────────────────────────
    net_profit = total_gross_profit - total_overhead

    # ── 6. Purchase summary for the period (info only) ────────────────
    purchase_total = db.session.query(
        func.sum(StockIn.total_amount + StockIn.other_expenses)
    ).filter(
        StockIn.date >= start_dt,
        StockIn.date <= end_dt
    ).scalar()
    total_purchases = _decimal(purchase_total)

    return {
        'material_rows':      material_rows,
        'overhead_entries':   overhead_entries,
        'total_revenue':      total_revenue,
        'total_cost':         total_cost,
        'total_gross_profit': total_gross_profit,
        'total_overhead':     total_overhead,
        'net_profit':         net_profit,
        'total_purchases':    total_purchases,
        'sale_count':         len(sales),
    }


@profit_bp.route('/')
@login_required
def index():
    today      = date.today()
    mode       = request.args.get('mode', 'daily')   # 'daily' | 'monthly'

    # ── Daily mode ─────────────────────────────────────────────────────
    if mode == 'daily':
        date_str = request.args.get('date', today.strftime('%Y-%m-%d'))
        try:
            view_date = date.fromisoformat(date_str)
        except ValueError:
            view_date = today

        start_dt = view_date
        end_dt   = view_date

        prev_date = (view_date - timedelta(days=1)).strftime('%Y-%m-%d')
        next_date = (view_date + timedelta(days=1)).strftime('%Y-%m-%d')

        period_label = view_date.strftime('%d %B %Y')
        nav_ctx = {
            'prev_url': f"?mode=daily&date={prev_date}",
            'next_url': f"?mode=daily&date={next_date}",
            'today_url': f"?mode=daily&date={today.strftime('%Y-%m-%d')}",
            'is_today': view_date == today,
            'date_val': view_date.strftime('%Y-%m-%d'),
        }

    # ── Monthly mode ───────────────────────────────────────────────────
    else:
        mode = 'monthly'
        year_str  = request.args.get('year',  str(today.year))
        month_str = request.args.get('month', str(today.month))
        try:
            year  = int(year_str)
            month = int(month_str)
            if not (1 <= month <= 12):
                raise ValueError
        except ValueError:
            year, month = today.year, today.month

        # First and last day of month
        first_day = date(year, month, 1)
        last_day  = date(year, month, calendar.monthrange(year, month)[1])
        start_dt  = first_day
        end_dt    = last_day

        # Prev / next month
        prev_month_date = first_day - timedelta(days=1)
        next_month_date = last_day  + timedelta(days=1)

        month_names_ur = {
            1:'جنوری', 2:'فروری', 3:'مارچ', 4:'اپریل',
            5:'مئی',   6:'جون',   7:'جولائی', 8:'اگست',
            9:'ستمبر', 10:'اکتوبر', 11:'نومبر', 12:'دسمبر'
        }
        period_label = f"{month_names_ur[month]} {year}"
        nav_ctx = {
            'prev_url':  f"?mode=monthly&year={prev_month_date.year}&month={prev_month_date.month}",
            'next_url':  f"?mode=monthly&year={next_month_date.year}&month={next_month_date.month}",
            'today_url': f"?mode=monthly&year={today.year}&month={today.month}",
            'is_today':  (year == today.year and month == today.month),
            'year':  year,
            'month': month,
        }
        view_date = first_day

    # ── Build the report ───────────────────────────────────────────────
    report = _build_report(start_dt, end_dt)

    return render_template(
        'profit/index.html',
        mode=mode,
        period_label=period_label,
        nav=nav_ctx,
        start_dt=start_dt,
        end_dt=end_dt,
        today=today,
        **report,
    )
