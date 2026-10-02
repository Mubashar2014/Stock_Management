from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from app.models import StockIn, Supplier, Material, Cashbook
from app.db import db
from app.utils import create_receipt_image, save_temp_image
from datetime import datetime
from decimal import Decimal
import urllib.parse
import os

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

            # Auto-create Cashbook entry if payment was made
            if paid_amount > 0:
                material = Material.query.get(material_id)
                material_name = material.name if material else 'مٹیریل'
                cashbook_entry = Cashbook(
                    type='debit',
                    amount=paid_amount,
                    reference_type='supplier',
                    reference_id=supplier_id,
                    description=f'خریداری کی ادائیگی - {material_name} ({quantity} {material.unit if material else ""})',
                    date=transaction_date
                )
                db.session.add(cashbook_entry)

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
            old_paid_amount = entry.paid_amount
            
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

            # Step D: Update Cashbook entries for payment changes
            # Delete old cashbook entry if it exists
            if old_paid_amount > 0:
                old_cashbook = Cashbook.query.filter_by(
                    reference_type='supplier',
                    reference_id=old_supplier_id,
                    type='debit',
                    amount=old_paid_amount,
                    date=entry.date
                ).first()
                if old_cashbook:
                    db.session.delete(old_cashbook)

            # Create new cashbook entry if payment was made
            if paid_amount > 0:
                material = Material.query.get(material_id)
                material_name = material.name if material else 'مٹیریل'
                cashbook_entry = Cashbook(
                    type='debit',
                    amount=paid_amount,
                    reference_type='supplier',
                    reference_id=supplier_id,
                    description=f'خریداری کی ادائیگی - {material_name} ({quantity} {material.unit if material else ""})',
                    date=datetime.strptime(date_str, '%Y-%m-%d').date()
                )
                db.session.add(cashbook_entry)

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

        # Delete associated cashbook entry if payment was made
        if entry.paid_amount > 0:
            cashbook_entry = Cashbook.query.filter_by(
                reference_type='supplier',
                reference_id=entry.supplier_id,
                type='debit',
                amount=entry.paid_amount,
                date=entry.date
            ).first()
            if cashbook_entry:
                db.session.delete(cashbook_entry)

        db.session.delete(entry)
        db.session.commit()
        flash('خریداری کا ریکارڈ ختم اور سپلائر کا بیلنس ریورس کر دیا گیا ہے۔', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خرابی: {str(e)}', 'danger')

    return redirect(url_for('stock_in.list_stock_in'))



# 5. RECEIPT VIEW
@stock_in_bp.route('/receipt/<int:entry_id>')
@login_required
def view_receipt(entry_id):
    entry = StockIn.query.get_or_404(entry_id)
    now = datetime.now()
    return render_template('receipts/stock_in_receipt.html', entry=entry, now=now)


# 6. DOWNLOAD RECEIPT IMAGE
@stock_in_bp.route('/receipt/<int:entry_id>/image')
@login_required
def download_receipt_image(entry_id):
    """Generate and download receipt as PNG image."""
    entry = StockIn.query.get_or_404(entry_id)
    
    # Create image using PIL
    image_bytes = create_receipt_image(entry, entry_type='stock_in')
    
    # Save to temp file
    temp_path = save_temp_image(image_bytes, prefix=f'stock_in_receipt_{entry.id}')
    
    # Send file and clean up
    response = send_file(
        temp_path,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'receipt_stock_in_{entry.id}.png'
    )
    
    # Schedule cleanup after sending
    @response.call_on_close
    def cleanup():
        try:
            os.unlink(temp_path)
        except:
            pass
    
    return response


# 7. WHATSAPP SHARE (Image-based with Desktop + Web fallback)
@stock_in_bp.route('/whatsapp/<int:entry_id>')
@login_required
def share_whatsapp(entry_id):
    """Share receipt image via WhatsApp Desktop or Web."""
    from app.utils import get_whatsapp_desktop_link
    
    entry = StockIn.query.get_or_404(entry_id)
    
    # Create message
    material_name = entry.material.name if entry.material else 'مٹیریل'
    message = f"""رسید - خریداری #{entry.id}
{entry.supplier.name}
مٹیریل: {material_name}
مقدار: {entry.quantity} {entry.material.unit if entry.material else ''}
شرح: {"{:,.0f}".format(entry.rate)} روپے
کل رقم: {"{:,.0f}".format(entry.total_amount)} روپے
باقی رقم: {"{:,.0f}".format(entry.remaining)} روپے"""
    
    # Get phone number
    phone = entry.supplier.phone if entry.supplier else ''
    
    # Create WhatsApp links (Desktop primary, Web fallback)
    wa_data = get_whatsapp_desktop_link(phone, message)
    
    # Generate image
    image_bytes = create_receipt_image(entry, entry_type='stock_in')
    
    # Save temporary image
    temp_path = save_temp_image(image_bytes, prefix=f'stock_in_receipt_{entry.id}')
    
    # Create a temporary URL for download
    image_download_url = f"{request.host_url}stock-in/receipt/{entry_id}/image"
    
    return render_template(
        'whatsapp_share.html',
        wa_link=wa_data['desktop_url'],
        wa_web_link=wa_data['web_url'],
        image_url=image_download_url,
        filename=f'receipt_stock_in_{entry.id}.png'
    )
