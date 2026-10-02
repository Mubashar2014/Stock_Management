from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from app.models import StockOut, Customer, Material, StockIn, Cashbook
from app.db import db
from app.utils import create_receipt_image, save_temp_image
from datetime import datetime
from decimal import Decimal
import urllib.parse
import os

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

            # Auto-create Cashbook entry if payment was received
            if paid_amount > 0:
                material = Material.query.get(material_id)
                material_name = material.name if material else 'مٹیریل'
                cashbook_entry = Cashbook(
                    type='credit',
                    amount=paid_amount,
                    reference_type='customer',
                    reference_id=customer_id,
                    description=f'فروخت کی وصولی - {material_name} ({quantity} {material.unit if material else ""})',
                    date=transaction_date
                )
                db.session.add(cashbook_entry)

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
            old_paid_amount = entry.paid_amount
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

            # Update Cashbook entries for payment changes
            # Delete old cashbook entry if it exists
            if old_paid_amount > 0:
                old_cashbook = Cashbook.query.filter_by(
                    reference_type='customer',
                    reference_id=old_customer_id,
                    type='credit',
                    amount=old_paid_amount,
                    date=entry.date
                ).first()
                if old_cashbook:
                    db.session.delete(old_cashbook)

            # Create new cashbook entry if payment was received
            if paid_amount > 0:
                material = Material.query.get(material_id)
                material_name = material.name if material else 'مٹیریل'
                cashbook_entry = Cashbook(
                    type='credit',
                    amount=paid_amount,
                    reference_type='customer',
                    reference_id=customer_id,
                    description=f'فروخت کی وصولی - {material_name} ({quantity} {material.unit if material else ""})',
                    date=datetime.strptime(date_str, '%Y-%m-%d').date()
                )
                db.session.add(cashbook_entry)

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
@stock_out_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_stock_out(entry_id):
    entry = StockOut.query.get_or_404(entry_id)
    try:
        customer = Customer.query.get(entry.customer_id)
        if customer:
            customer.current_balance -= float(entry.remaining)

        # Delete associated cashbook entry if payment was received
        if entry.paid_amount > 0:
            cashbook_entry = Cashbook.query.filter_by(
                reference_type='customer',
                reference_id=entry.customer_id,
                type='credit',
                amount=entry.paid_amount,
                date=entry.date
            ).first()
            if cashbook_entry:
                db.session.delete(cashbook_entry)

        db.session.delete(entry)
        db.session.commit()
        flash('فروخت کا ریکارڈ ختم اور گاہک کا بیلنس ریورس کر دیا گیا ہے۔', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خرابی: {str(e)}', 'danger')

    return redirect(url_for('stock_out.list_stock_out'))



# 5. RECEIPT VIEW
@stock_out_bp.route('/receipt/<int:entry_id>')
@login_required
def view_receipt(entry_id):
    entry = StockOut.query.get_or_404(entry_id)
    now = datetime.now()
    return render_template('receipts/stock_out_receipt.html', entry=entry, now=now)


# 6. DOWNLOAD RECEIPT IMAGE
@stock_out_bp.route('/receipt/<int:entry_id>/image')
@login_required
def download_receipt_image(entry_id):
    """Generate and download receipt as PNG image."""
    entry = StockOut.query.get_or_404(entry_id)
    
    # Create image using PIL
    image_bytes = create_receipt_image(entry, entry_type='stock_out')
    
    # Save to temp file
    temp_path = save_temp_image(image_bytes, prefix=f'stock_out_receipt_{entry.id}')
    
    # Send file and clean up
    response = send_file(
        temp_path,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'receipt_stock_out_{entry.id}.png'
    )
    
    # Schedule cleanup after sending
    @response.call_on_close
    def cleanup():
        try:
            os.unlink(temp_path)
        except:
            pass
    
    return response


# 7. WHATSAPP SHARE (Image-based)
@stock_out_bp.route('/whatsapp/<int:entry_id>')
@login_required
def share_whatsapp(entry_id):
    """Share receipt image via WhatsApp Web."""
    from app.utils import send_whatsapp_image_browser
    
    entry = StockOut.query.get_or_404(entry_id)
    
    # Create message
    material_name = entry.material.name if entry.material else 'مٹیریل'
    message = f"""رسید - فروخت #{entry.id}
{entry.customer.name}
مٹیریل: {material_name}
مقدار: {entry.quantity} {entry.material.unit if entry.material else ''}
شرح: {"{:,.0f}".format(entry.rate)} روپے
کل رقم: {"{:,.0f}".format(entry.total_amount)} روپے
باقی رقم: {"{:,.0f}".format(entry.remaining)} روپے"""
    
    # Get phone number
    phone = entry.customer.phone if entry.customer else ''
    
    # Create WhatsApp link
    wa_data = send_whatsapp_image_browser(phone, message)
    
    # Generate image
    image_bytes = create_receipt_image(entry, entry_type='stock_out')
    
    # Save temporary image
    temp_path = save_temp_image(image_bytes, prefix=f'stock_out_receipt_{entry.id}')
    
    # Create a temporary URL for download
    from flask import url_for as flask_url_for
    image_download_url = f"{request.host_url}stock-out/receipt/{entry_id}/image"
    
    return render_template(
        'whatsapp_share.html',
        wa_link=wa_data['url'],
        image_url=image_download_url,
        filename=f'receipt_stock_out_{entry.id}.png'
    )
