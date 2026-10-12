"""Utility functions for the application."""
import os
import tempfile
import base64
import urllib.parse
from io import BytesIO
from datetime import datetime
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from app.models import StockIn, StockOut, Cashbook


def register_urdu_font():
    """Register Urdu font for PDF generation."""
    try:
        font_path = "/usr/share/fonts/truetype/noto/NotoSansUrdu-Regular.ttf"
        if not os.path.exists(font_path):
            # Fallback to any available Urdu font
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        pdfmetrics.registerFont(TTFont('Urdu', font_path))
        return 'Urdu'
    except:
        return 'Helvetica'


def create_receipt_pdf(entry, entry_type='stock_in'):
    """
    Create receipt PDF using ReportLab with Urdu support.
    
    Args:
        entry: StockIn or StockOut entry
        entry_type: 'stock_in' or 'stock_out'
    
    Returns:
        bytes: PDF data
    """
    urdu_font = register_urdu_font()
    
    pdf_io = BytesIO()
    doc = SimpleDocTemplate(pdf_io, pagesize=letter, rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=12,
        alignment=1
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        fontName=urdu_font
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        fontName=urdu_font,
        spaceAfter=6
    )
    
    # Header
    title = "Sher Ali Building Material"
    receipt_type = "رسید - خریداری" if entry_type == 'stock_in' else "رسید - فروخت"
    
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(receipt_type, heading_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Receipt info table
    info_data = [
        [Paragraph("رسید نمبر:", normal_style), Paragraph(f"#{entry.id}", normal_style)],
        [Paragraph("تاریخ:", normal_style), Paragraph(entry.date.strftime('%d/%m/%Y'), normal_style)],
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 2*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), urdu_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Person info
    if entry_type == 'stock_in':
        person = entry.supplier
        person_label = "سپلائر:"
    else:
        person = entry.customer
        person_label = "گاہک:"
    
    person_data = [
        [Paragraph(person_label, normal_style), Paragraph(person.name, normal_style)],
        [Paragraph("فون:", normal_style), Paragraph(person.phone or '-', normal_style)],
    ]
    
    person_table = Table(person_data, colWidths=[2*inch, 2*inch])
    person_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e9ecef')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), urdu_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(person_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Material details
    material_data = [
        [Paragraph("مٹیریل:", normal_style), Paragraph(entry.material.name, normal_style)],
        [Paragraph("مقدار:", normal_style), Paragraph(f"{entry.quantity} {entry.material.unit}", normal_style)],
        [Paragraph("شرح:", normal_style), Paragraph(f"Rs. {entry.rate:,.0f}", normal_style)],
    ]
    
    material_table = Table(material_data, colWidths=[2*inch, 2*inch])
    material_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), urdu_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(material_table)
    story.append(Spacer(1, 0.25*inch))
    
    # Financial summary
    subtotal = Decimal(str(entry.quantity)) * Decimal(str(entry.rate))
    
    financial_data = [
        [Paragraph("ذیلی کل:", normal_style), Paragraph(f"Rs. {subtotal:,.0f}", normal_style)],
    ]
    
    if entry.other_expenses > 0:
        financial_data.append([Paragraph("دیگر اخراجات:", normal_style), 
                               Paragraph(f"Rs. {entry.other_expenses:,.0f}", normal_style)])
    
    if hasattr(entry, 'discount') and entry.discount > 0:
        financial_data.append([Paragraph("رعایت:", normal_style), 
                               Paragraph(f"Rs. {entry.discount:,.0f}", normal_style)])
    
    financial_data.append([Paragraph("کل رقم:", normal_style), 
                          Paragraph(f"Rs. {entry.total_amount:,.0f}", normal_style)])
    financial_data.append([Paragraph("وصول شدہ:", normal_style), 
                          Paragraph(f"Rs. {entry.paid_amount:,.0f}", normal_style)])
    financial_data.append([Paragraph("باقی رقم:", normal_style), 
                          Paragraph(f"Rs. {entry.remaining:,.0f}", normal_style)])
    
    financial_table = Table(financial_data, colWidths=[2.5*inch, 1.5*inch])
    financial_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
        ('BACKGROUND', (1, 0), (1, -3), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), urdu_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BOLD', (0, -1), (-1, -1), True),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(financial_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    story.append(Paragraph("شکریہ آپ کے کاروبار کے لیے!", normal_style))
    story.append(Paragraph("Sher Ali Building Material - Stock Management System", styles['Normal']))
    
    doc.build(story)
    pdf_io.seek(0)
    return pdf_io.getvalue()


def create_receipt_image(entry, entry_type='stock_in'):
    """
    DEPRECATED: Use create_receipt_pdf instead.
    Kept for backwards compatibility.
    """
    return create_receipt_pdf(entry, entry_type)


def create_khata_statement_pdf(person, person_type):
    """
    Create Khata statement PDF using ReportLab with Urdu support.
    Calculates balance dynamically from transactions.
    
    Args:
        person: Supplier or Customer object
        person_type: 'supplier' or 'customer'
    
    Returns:
        bytes: PDF data
    """
    from decimal import Decimal
    
    # Calculate closing balance dynamically
    opening_balance = Decimal(str(person.opening_balance or 0))
    
    if person_type == 'supplier':
        stock_transactions = StockIn.query.filter_by(supplier_id=person.id).all()
        payments = Cashbook.query.filter_by(reference_type='supplier', reference_id=person.id).all()
    else:
        stock_transactions = StockOut.query.filter_by(customer_id=person.id).all()
        payments = Cashbook.query.filter_by(reference_type='customer', reference_id=person.id).all()
    
    # Calculate totals
    total_debits = sum(Decimal(str(tx.total_amount)) for tx in stock_transactions) if stock_transactions else Decimal('0')
    total_credits = sum(Decimal(str(p.amount)) for p in payments) if payments else Decimal('0')
    closing_balance = opening_balance + total_debits - total_credits
    
    urdu_font = register_urdu_font()
    
    pdf_io = BytesIO()
    doc = SimpleDocTemplate(pdf_io, pagesize=letter, rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=12,
        alignment=1
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        fontName=urdu_font,
        spaceAfter=6
    )
    
    # Header
    title = "Sher Ali Building Material"
    statement_type = "بیان - سپلائر" if person_type == 'supplier' else "بیان - گاہک"
    
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(statement_type, title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Person info
    person_label = "سپلائر:" if person_type == 'supplier' else "گاہک:"
    person_data = [
        [Paragraph("نام:", normal_style), Paragraph(person.name, normal_style)],
        [Paragraph("فون:", normal_style), Paragraph(person.phone or '-', normal_style)],
        [Paragraph("پتہ:", normal_style), Paragraph(person.address or '-', normal_style)],
        [Paragraph("تاریخ:", normal_style), Paragraph(datetime.now().strftime('%d/%m/%Y'), normal_style)],
    ]
    
    person_table = Table(person_data, colWidths=[1.5*inch, 3.5*inch])
    person_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), urdu_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(person_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Balance summary
    balance_data = [
        [Paragraph("ابتدائی بقایا:", normal_style), Paragraph(f"Rs. {opening_balance:,.0f}", normal_style)],
        [Paragraph("کل واجب الادا:", normal_style), Paragraph(f"Rs. {total_debits:,.0f}", normal_style)],
        [Paragraph("کل ادائیگی:", normal_style), Paragraph(f"Rs. {total_credits:,.0f}", normal_style)],
    ]
    
    balance_table = Table(balance_data, colWidths=[2*inch, 3*inch])
    balance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -2), colors.HexColor('#e9ecef')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), urdu_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(balance_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Closing balance display (DYNAMIC)
    balance_status = "روپے واجب الادا" if closing_balance > 0 else "صاف ستھرا"
    
    closing_data = [
        [Paragraph("موجودہ بیلنس:", ParagraphStyle('Bold', parent=normal_style, fontSize=14, bold=True)), 
         Paragraph(f"Rs. {closing_balance:,.0f}", ParagraphStyle('Bold', parent=normal_style, fontSize=14, bold=True))],
        [Paragraph("حالت:", normal_style), Paragraph(balance_status, normal_style)],
    ]
    
    closing_table = Table(closing_data, colWidths=[2*inch, 3*inch])
    closing_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), urdu_font),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(closing_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    story.append(Paragraph("شکریہ آپ کے کاروبار کے لیے!", normal_style))
    story.append(Paragraph("Stock Management System", styles['Normal']))
    
    doc.build(story)
    pdf_io.seek(0)
    return pdf_io.getvalue()


def create_khata_statement_image(person, person_type):
    """
    DEPRECATED: Use create_khata_statement_pdf instead.
    Kept for backwards compatibility.
    """
    return create_khata_statement_pdf(person, person_type)


def save_temp_image(image_bytes, prefix='receipt', is_pdf=True):
    """
    Save image/PDF bytes to temporary file.
    
    Args:
        image_bytes: Image/PDF data as bytes
        prefix: Filename prefix
        is_pdf: If True, saves as PDF; otherwise as PNG
    
    Returns:
        str: Path to temporary file
    """
    suffix = '.pdf' if is_pdf else '.png'
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        prefix=f'{prefix}_'
    )
    temp_file.write(image_bytes)
    temp_file.close()
    return temp_file.name


def image_to_base64(image_bytes):
    """Convert image bytes to base64 string for embedding."""
    return base64.b64encode(image_bytes).decode('utf-8')


def send_whatsapp_image_browser(phone, message_text):
    """
    Generate WhatsApp Web link with pre-filled message.
    Image will be downloaded separately and user attaches it.
    
    Args:
        phone: Phone number (with or without country code)
        message_text: Message to send
    
    Returns:
        dict: {url: whatsapp_url, phone: cleaned_phone}
    """
    # Clean phone number
    if phone:
        phone = phone.lstrip('0')
        if not phone.startswith('92'):
            phone = '92' + phone
    else:
        phone = ''
    
    # Create WhatsApp URL with message
    whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message_text)}"
    
    return {
        'url': whatsapp_url,
        'phone': phone,
        'message': message_text
    }


def get_whatsapp_desktop_link(phone, message_text):
    """
    Generate link to open WhatsApp Desktop with message.
    
    Args:
        phone: Phone number (with or without country code)
        message_text: Message to send
    
    Returns:
        dict: {desktop_url: whatsapp_desktop_url, web_url: whatsapp_web_url, phone: cleaned_phone}
    """
    # Clean phone number
    if phone:
        phone = phone.lstrip('0')
        if not phone.startswith('92'):
            phone = '92' + phone
    else:
        phone = ''
    
    # WhatsApp Desktop URL scheme (works on Windows, macOS, Linux)
    # Note: WhatsApp Desktop must be installed
    desktop_url = f"whatsapp://send?phone={phone}&text={urllib.parse.quote(message_text)}"
    web_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message_text)}"
    
    return {
        'desktop_url': desktop_url,
        'web_url': web_url,
        'phone': phone,
        'message': message_text
    }
