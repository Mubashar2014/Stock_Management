"""Utility functions for the application."""
import os
import re
import tempfile
import base64
import urllib.parse
from io import BytesIO
from datetime import datetime
from decimal import Decimal
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_URDU_SHAPING = True
except ImportError:
    arabic_reshaper = None
    get_display = None
    _HAS_URDU_SHAPING = False
from app.models import StockIn, StockOut, Cashbook
from PIL import Image, ImageDraw, ImageFont, features

# Pillow with libraqm handles Arabic shaping/RTL natively; without it we
# fall back to arabic-reshaper + bidi (and plain text if those are missing).
_HAS_RAQM = bool(features.check('raqm'))

# Bundle the fonts inside the project so it works on any server.
# DejaVu (Latin) is essential: many servers lack it, and the Noto Naskh
# Arabic face has NO Latin letters — without bundled DejaVu, Latin text
# falls back to tofu boxes on those servers.
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'fonts')
FONT_FILE = os.path.join(_FONT_DIR, 'NotoNaskhArabic-Regular.ttf')
_DEJAVU_FILE = os.path.join(_FONT_DIR, 'DejaVuSans.ttf')
_DEJAVU_BOLD_FILE = os.path.join(_FONT_DIR, 'DejaVuSans-Bold.ttf')

_FONT_CACHE = {}


def register_urdu_font():
    """Register an Urdu-capable font. Returns the font name."""
    if 'name' in _FONT_CACHE:
        return _FONT_CACHE['name']

    candidates = [
        FONT_FILE,
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('UrduFont', path))
                _FONT_CACHE['name'] = 'UrduFont'
                return 'UrduFont'
            except Exception:
                continue

    print(f"[WARNING] Urdu font not found. Place it at: {FONT_FILE}")
    _FONT_CACHE['name'] = 'Helvetica'
    return 'Helvetica'


_LATIN_RUN = re.compile(r'[\x20-\x7E]+')


def ur(text):
    """
    Shape + reorder Urdu text and return safe Paragraph markup.
    English/digit runs are switched to Helvetica because the Urdu font
    has no Latin letters.
    """
    text = '' if text is None else str(text)
    if _HAS_URDU_SHAPING:
        shown = get_display(arabic_reshaper.reshape(text))
    else:
        # arabic-reshaper/python-bidi not installed: PDF Urdu will render
        # unshaped, but the app keeps running (PNG receipts are unaffected).
        shown = text

    out, last = [], 0
    for m in _LATIN_RUN.finditer(shown):
        out.append(escape(shown[last:m.start()]))
        out.append(f'<font name="Helvetica">{escape(m.group())}</font>')
        last = m.end()
    out.append(escape(shown[last:]))
    return ''.join(out)


def P(text, style):
    """Paragraph with Urdu shaping applied."""
    return Paragraph(ur(text), style)


# ---------- PIL (PNG image) text helpers ----------

_ARABIC_RE = re.compile(
    '[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
)

_PIL_FONT_CACHE = {}

_URDU_PIL_FONTS = [
    FONT_FILE,
    os.path.join(_FONT_DIR, 'NotoNaskhArabic-Bold.ttf'),
    '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf',
    '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
    '/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Regular.ttf',
    '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
]
# Bundled DejaVu first — guarantees Latin renders even when the server has
# no system fonts. The Noto faces are a last resort (digits-only fallback).
_LATIN_PIL_FONTS_BOLD = [
    _DEJAVU_BOLD_FILE,
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
]
_LATIN_PIL_FONTS = [
    _DEJAVU_FILE,
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/TTF/DejaVuSans.ttf',
]


def _load_pil_font(size, urdu=False, bold=False):
    """Load and cache a PIL font; falls back to the default bitmap font."""
    key = (size, urdu, bold)
    if key in _PIL_FONT_CACHE:
        return _PIL_FONT_CACHE[key]

    if urdu:
        # Naskh bold is preferred but the regular face is an acceptable
        # fallback; the bundled font guarantees availability.
        candidates = _URDU_PIL_FONTS if not bold else \
            [os.path.join(os.path.dirname(FONT_FILE), 'NotoNaskhArabic-Bold.ttf')] + _URDU_PIL_FONTS
    else:
        candidates = (_LATIN_PIL_FONTS_BOLD if bold else _LATIN_PIL_FONTS) + _URDU_PIL_FONTS

    font = ImageFont.load_default()
    for path in candidates:
        if path and os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue

    _PIL_FONT_CACHE[key] = font
    return font


def _pil_font_for(text, size, bold=False):
    """Pick an Urdu-capable font when the text contains Arabic script."""
    has_arabic = bool(_ARABIC_RE.search(str(text or '')))
    return _load_pil_font(size, urdu=has_arabic, bold=bold)


def _draw_text(draw, xy, text, size, fill=None, anchor=None, bold=False):
    """Draw one line of text on a PIL image with automatic Urdu support.

    - Switches to a bundled Noto Naskh Arabic font when the text contains
      Arabic-script characters (so Urdu names render instead of tofu boxes).
    - Uses raqm shaping/RTL when available, else arabic-reshaper + bidi.
    """
    text = '' if text is None else str(text)
    font = _pil_font_for(text, size, bold=bold)

    kwargs = {}
    if anchor:
        kwargs['anchor'] = anchor

    if _ARABIC_RE.search(text):
        if _HAS_RAQM:
            kwargs['direction'] = 'rtl'
        elif _HAS_URDU_SHAPING:
            text = '\u200f' + get_display(arabic_reshaper.reshape(text))

    try:
        draw.text(xy, text, font=font, fill=fill, **kwargs)
    except (TypeError, ValueError):
        # Older Pillow / no-raqm build: retry without the direction kwarg.
        kwargs.pop('direction', None)
        draw.text(xy, text, font=font, fill=fill, **kwargs)


def _base_styles(urdu_font, title_size=20):
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'], fontSize=title_size,
        textColor=colors.HexColor('#667eea'), spaceAfter=12, alignment=1,
        fontName=urdu_font)
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'], fontSize=14,
        textColor=colors.HexColor('#333333'), spaceAfter=8, alignment=1,
        fontName=urdu_font)
    normal_style = ParagraphStyle(
        'CustomNormal', parent=styles['Normal'], fontSize=11,
        fontName=urdu_font, spaceAfter=6, alignment=1)
    return styles, title_style, heading_style, normal_style


def _table_style(bg, align='CENTER', size=10, pad=8):
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg)),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), align),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), size),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ])


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
    doc = SimpleDocTemplate(pdf_io, pagesize=letter, rightMargin=0.5*inch,
                            leftMargin=0.5*inch, topMargin=0.75*inch,
                            bottomMargin=0.75*inch)
    styles, title_style, heading_style, normal_style = _base_styles(urdu_font)
    story = []

    # Header
    receipt_type = "رسید - خریداری" if entry_type == 'stock_in' else "رسید - فروخت"
    story.append(P("Sher Ali Building Material", title_style))
    story.append(P(receipt_type, heading_style))
    story.append(Spacer(1, 0.2*inch))

    # Receipt info
    info_data = [
        [P("رسید نمبر:", normal_style), P(f"#{entry.id}", normal_style)],
        [P("تاریخ:", normal_style), P(entry.date.strftime('%d/%m/%Y'), normal_style)],
    ]
    info_table = Table(info_data, colWidths=[2*inch, 2*inch])
    info_table.setStyle(_table_style('#f8f9fa'))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))

    # Person info
    if entry_type == 'stock_in':
        person, person_label = entry.supplier, "سپلائر:"
    else:
        person, person_label = entry.customer, "گاہک:"

    person_data = [
        [P(person_label, normal_style), P(person.name, normal_style)],
        [P("فون:", normal_style), P(person.phone or '-', normal_style)],
    ]
    person_table = Table(person_data, colWidths=[2*inch, 2*inch])
    person_table.setStyle(_table_style('#e9ecef'))
    story.append(person_table)
    story.append(Spacer(1, 0.2*inch))

    # Material details
    material_data = [
        [P("مٹیریل:", normal_style), P(entry.material.name, normal_style)],
        [P("مقدار:", normal_style), P(f"{entry.quantity} {entry.material.unit}", normal_style)],
        [P("شرح:", normal_style), P(f"Rs. {entry.rate:,.0f}", normal_style)],
    ]
    material_table = Table(material_data, colWidths=[2*inch, 2*inch])
    material_table.setStyle(_table_style('#f0f0f0'))
    story.append(material_table)
    story.append(Spacer(1, 0.25*inch))

    # Financial summary
    subtotal = Decimal(str(entry.quantity)) * Decimal(str(entry.rate))
    financial_data = [[P("ذیلی کل:", normal_style), P(f"Rs. {subtotal:,.0f}", normal_style)]]

    if entry.other_expenses > 0:
        financial_data.append([P("دیگر اخراجات:", normal_style),
                               P(f"Rs. {entry.other_expenses:,.0f}", normal_style)])
    if hasattr(entry, 'discount') and entry.discount > 0:
        financial_data.append([P("رعایت:", normal_style),
                               P(f"Rs. {entry.discount:,.0f}", normal_style)])

    # Last row (remaining) is white-on-blue, so it gets its own style
    white_style = ParagraphStyle('WhiteBold', parent=normal_style,
                                 fontSize=12, textColor=colors.white)

    financial_data.append([P("کل رقم:", normal_style),
                           P(f"Rs. {entry.total_amount:,.0f}", normal_style)])
    financial_data.append([P("وصول شدہ:", normal_style),
                           P(f"Rs. {entry.paid_amount:,.0f}", normal_style)])
    financial_data.append([P("باقی رقم:", white_style),
                           P(f"Rs. {entry.remaining:,.0f}", white_style)])

    financial_table = Table(financial_data, colWidths=[2.5*inch, 1.5*inch])
    financial_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -2), colors.HexColor('#e9ecef')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#667eea')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(financial_table)
    story.append(Spacer(1, 0.3*inch))

    # Footer
    story.append(P("شکریہ آپ کے کاروبار کے لیے!", normal_style))
    story.append(P("Sher Ali Building Material - Stock Management System", normal_style))

    doc.build(story)
    pdf_io.seek(0)
    return pdf_io.getvalue()


def create_receipt_image(entry, entry_type='stock_in'):
    """
    Create receipt image (PNG) for sharing.
    Uses PIL for quick PNG generation without complex font rendering.
    
    Args:
        entry: StockIn or StockOut entry
        entry_type: 'stock_in' or 'stock_out'
    
    Returns:
        bytes: PNG image data
    """
    width, height = 800, 1000
    
    if entry_type == 'stock_in':
        gradient_start = (102, 126, 234)  # Purple
        gradient_end = (118, 75, 162)
    else:
        gradient_start = (17, 153, 142)  # Teal
        gradient_end = (56, 239, 125)  # Green
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)

    # Font sizes (per-string font is chosen automatically by _draw_text)
    S_LARGE, S_MEDIUM, S_NORMAL, S_SMALL = 40, 28, 22, 18

    # Draw gradient header
    for y in range(200):
        ratio = y / 200
        r = int(gradient_start[0] * (1 - ratio) + gradient_end[0] * ratio)
        g = int(gradient_start[1] * (1 - ratio) + gradient_end[1] * ratio)
        b = int(gradient_start[2] * (1 - ratio) + gradient_end[2] * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))

    # Header text
    _draw_text(draw, (width//2, 50), "Sher Ali Building Material", S_MEDIUM, fill='white', anchor='mm', bold=True)
    receipt_type = "Purchase Receipt" if entry_type == 'stock_in' else "Sales Receipt"
    _draw_text(draw, (width//2, 90), receipt_type, S_NORMAL, fill='white', anchor='mm')
    _draw_text(draw, (width//2, 130), f"Receipt #{entry.id}", S_NORMAL, fill='white', anchor='mm')
    _draw_text(draw, (width//2, 165), entry.date.strftime('%d/%m/%Y'), S_SMALL, fill='white', anchor='mm')

    y_pos = 240
    x_margin = 50

    if entry_type == 'stock_in':
        person = entry.supplier
        person_label = "Supplier"
    else:
        person = entry.customer
        person_label = "Customer"

    _draw_text(draw, (x_margin, y_pos), f"{person_label}:", S_NORMAL, fill='#333')
    _draw_text(draw, (width - x_margin, y_pos), person.name, S_NORMAL, fill='#000', anchor='rm')
    y_pos += 40

    if person.phone:
        _draw_text(draw, (x_margin, y_pos), "Phone:", S_NORMAL, fill='#333')
        _draw_text(draw, (width - x_margin, y_pos), person.phone, S_NORMAL, fill='#000', anchor='rm')
        y_pos += 40

    draw.line([(x_margin, y_pos), (width - x_margin, y_pos)], fill='#ddd', width=2)
    y_pos += 30

    _draw_text(draw, (x_margin, y_pos), "Material:", S_NORMAL, fill='#333')
    _draw_text(draw, (width - x_margin, y_pos), entry.material.name, S_NORMAL, fill='#000', anchor='rm')
    y_pos += 40

    _draw_text(draw, (x_margin, y_pos), "Quantity:", S_NORMAL, fill='#333')
    _draw_text(draw, (width - x_margin, y_pos), f"{entry.quantity} {entry.material.unit}", S_NORMAL, fill='#000', anchor='rm')
    y_pos += 40

    _draw_text(draw, (x_margin, y_pos), "Rate:", S_NORMAL, fill='#333')
    _draw_text(draw, (width - x_margin, y_pos), f"Rs. {entry.rate:,.0f}", S_NORMAL, fill='#000', anchor='rm')
    y_pos += 50

    draw.rectangle([(x_margin, y_pos), (width - x_margin, y_pos + 250)], outline='#ddd', width=2)
    y_pos += 20

    _draw_text(draw, (x_margin + 20, y_pos), "Subtotal:", S_NORMAL, fill='#666')
    _draw_text(draw, (width - x_margin - 20, y_pos), f"Rs. {(entry.quantity * entry.rate):,.0f}", S_NORMAL, fill='#000', anchor='rm')
    y_pos += 40

    if entry.other_expenses > 0:
        _draw_text(draw, (x_margin + 20, y_pos), "Other Expenses:", S_NORMAL, fill='#666')
        _draw_text(draw, (width - x_margin - 20, y_pos), f"Rs. {entry.other_expenses:,.0f}", S_NORMAL, fill='#000', anchor='rm')
        y_pos += 40

    if hasattr(entry, 'discount') and entry.discount > 0:
        _draw_text(draw, (x_margin + 20, y_pos), "Discount:", S_NORMAL, fill='#666')
        _draw_text(draw, (width - x_margin - 20, y_pos), f"- Rs. {entry.discount:,.0f}", S_NORMAL, fill='#dc3545', anchor='rm')
        y_pos += 40

    draw.line([(x_margin + 20, y_pos), (width - x_margin - 20, y_pos)], fill='#999', width=2)
    y_pos += 15

    _draw_text(draw, (x_margin + 20, y_pos), "TOTAL:", S_MEDIUM, fill='#000', bold=True)
    _draw_text(draw, (width - x_margin - 20, y_pos), f"Rs. {entry.total_amount:,.0f}", S_MEDIUM, fill=gradient_start, anchor='rm', bold=True)
    y_pos += 45

    _draw_text(draw, (x_margin + 20, y_pos), "Paid:", S_NORMAL, fill='#666')
    _draw_text(draw, (width - x_margin - 20, y_pos), f"Rs. {entry.paid_amount:,.0f}", S_NORMAL, fill='#28a745', anchor='rm')
    y_pos += 60

    box_y = y_pos
    draw.rectangle([(x_margin, box_y), (width - x_margin, box_y + 120)], fill=gradient_start)

    _draw_text(draw, (width//2, box_y + 30), "REMAINING AMOUNT", S_NORMAL, fill='white', anchor='mm')
    _draw_text(draw, (width//2, box_y + 75), f"Rs. {entry.remaining:,.0f}", S_LARGE, fill='white', anchor='mm', bold=True)

    y_pos = box_y + 140
    _draw_text(draw, (width//2, y_pos), "Thank you for your business!", S_SMALL, fill='#666', anchor='mm')
    _draw_text(draw, (width//2, y_pos + 25), "Sher Ali Building Material", S_SMALL, fill='#999', anchor='mm')

    img_io = BytesIO()
    img.save(img_io, 'PNG', quality=95)
    img_io.seek(0)
    return img_io.getvalue()


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
    opening_balance = Decimal(str(person.opening_balance or 0))

    if person_type == 'supplier':
        stock_transactions = StockIn.query.filter_by(supplier_id=person.id).all()
        payments = Cashbook.query.filter_by(reference_type='supplier', reference_id=person.id).all()
    else:
        stock_transactions = StockOut.query.filter_by(customer_id=person.id).all()
        payments = Cashbook.query.filter_by(reference_type='customer', reference_id=person.id).all()

    total_debits = sum(Decimal(str(tx.total_amount)) for tx in stock_transactions) if stock_transactions else Decimal('0')
    total_credits = sum(Decimal(str(p.amount)) for p in payments) if payments else Decimal('0')
    closing_balance = opening_balance + total_debits - total_credits

    urdu_font = register_urdu_font()

    pdf_io = BytesIO()
    doc = SimpleDocTemplate(pdf_io, pagesize=letter, rightMargin=0.5*inch,
                            leftMargin=0.5*inch, topMargin=0.75*inch,
                            bottomMargin=0.75*inch)
    styles, title_style, heading_style, normal_style = _base_styles(urdu_font, title_size=18)
    story = []

    # Header
    statement_type = "بیان - سپلائر" if person_type == 'supplier' else "بیان - گاہک"
    story.append(P("Sher Ali Building Material", title_style))
    story.append(P(statement_type, title_style))
    story.append(Spacer(1, 0.2*inch))

    # Person info
    person_data = [
        [P("نام:", normal_style), P(person.name, normal_style)],
        [P("فون:", normal_style), P(person.phone or '-', normal_style)],
        [P("پتہ:", normal_style), P(person.address or '-', normal_style)],
        [P("تاریخ:", normal_style), P(datetime.now().strftime('%d/%m/%Y'), normal_style)],
    ]
    person_table = Table(person_data, colWidths=[1.5*inch, 3.5*inch])
    person_table.setStyle(_table_style('#f8f9fa', align='CENTER'))
    story.append(person_table)
    story.append(Spacer(1, 0.3*inch))

    # Balance summary
    balance_data = [
        [P("ابتدائی بقایا:", normal_style), P(f"Rs. {opening_balance:,.0f}", normal_style)],
        [P("کل واجب الادا:", normal_style), P(f"Rs. {total_debits:,.0f}", normal_style)],
        [P("کل ادائیگی:", normal_style), P(f"Rs. {total_credits:,.0f}", normal_style)],
    ]
    balance_table = Table(balance_data, colWidths=[2*inch, 3*inch])
    balance_table.setStyle(_table_style('#e9ecef'))
    story.append(balance_table)
    story.append(Spacer(1, 0.2*inch))

    # Closing balance (white text on blue)
    balance_status = "روپے واجب الادا" if closing_balance > 0 else "صاف ستھرا"
    big_white = ParagraphStyle('BigWhite', parent=normal_style, fontSize=14,
                               textColor=colors.white)
    white = ParagraphStyle('White', parent=normal_style, textColor=colors.white)

    closing_data = [
        [P("موجودہ بیلنس:", big_white), P(f"Rs. {closing_balance:,.0f}", big_white)],
        [P("حالت:", white), P(balance_status, white)],
    ]
    closing_table = Table(closing_data, colWidths=[2*inch, 3*inch])
    closing_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#667eea')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(closing_table)
    story.append(Spacer(1, 0.3*inch))

    # Footer
    story.append(P("شکریہ آپ کے کاروبار کے لیے!", normal_style))
    story.append(P("Stock Management System", normal_style))

    doc.build(story)
    pdf_io.seek(0)
    return pdf_io.getvalue()


def create_khata_statement_image(person, person_type):
    """
    Create Khata statement image (PNG) for sharing.
    Calculates balance dynamically from transactions.
    
    Args:
        person: Supplier or Customer object
        person_type: 'supplier' or 'customer'
    
    Returns:
        bytes: PNG image data
    """
    width, height = 800, 800
    
    if person_type == 'supplier':
        gradient_start = (102, 126, 234)  # Purple
        gradient_end = (118, 75, 162)
    else:
        gradient_start = (17, 153, 142)  # Teal
        gradient_end = (56, 239, 125)
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)

    # Font sizes (per-string font is chosen automatically by _draw_text)
    S_XLARGE, S_MEDIUM, S_NORMAL, S_SMALL = 50, 28, 22, 18

    # Draw gradient header
    for y in range(180):
        ratio = y / 180
        r = int(gradient_start[0] * (1 - ratio) + gradient_end[0] * ratio)
        g = int(gradient_start[1] * (1 - ratio) + gradient_end[1] * ratio)
        b = int(gradient_start[2] * (1 - ratio) + gradient_end[2] * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))

    _draw_text(draw, (width//2, 50), "Sher Ali Building Material", S_MEDIUM, fill='white', anchor='mm', bold=True)
    _draw_text(draw, (width//2, 90), "Account Statement", S_NORMAL, fill='white', anchor='mm')
    person_label = "Supplier" if person_type == 'supplier' else "Customer"
    _draw_text(draw, (width//2, 135), f"{person_label} Account", S_SMALL, fill='white', anchor='mm')

    y_pos = 220
    x_margin = 60

    box_height = 200
    draw.rectangle([(x_margin, y_pos), (width - x_margin, y_pos + box_height)], fill='#f8f9fa', outline='#ddd', width=2)

    y_pos += 25
    _draw_text(draw, (x_margin + 30, y_pos), "Name:", S_NORMAL, fill='#666')
    _draw_text(draw, (width - x_margin - 30, y_pos), person.name, S_MEDIUM, fill='#000', anchor='rm', bold=True)
    y_pos += 50

    if person.phone:
        _draw_text(draw, (x_margin + 30, y_pos), "Phone:", S_NORMAL, fill='#666')
        _draw_text(draw, (width - x_margin - 30, y_pos), person.phone, S_NORMAL, fill='#000', anchor='rm')
        y_pos += 50

    if person.address:
        _draw_text(draw, (x_margin + 30, y_pos), "Address:", S_NORMAL, fill='#666')
        addr = person.address[:40] + '...' if len(person.address) > 40 else person.address
        _draw_text(draw, (width - x_margin - 30, y_pos), addr, S_NORMAL, fill='#000', anchor='rm')
        y_pos += 50

    now = datetime.now()
    _draw_text(draw, (x_margin + 30, y_pos), "Date:", S_NORMAL, fill='#666')
    _draw_text(draw, (width - x_margin - 30, y_pos), now.strftime('%d/%m/%Y'), S_NORMAL, fill='#000', anchor='rm')

    # Balance box
    y_pos = 450
    box_height = 220
    draw.rectangle([(x_margin, y_pos), (width - x_margin, y_pos + box_height)], fill=gradient_start)

    _draw_text(draw, (width//2, y_pos + 40), "CURRENT BALANCE", S_MEDIUM, fill='white', anchor='mm', bold=True)
    _draw_text(draw, (width//2, y_pos + 120), f"Rs. {person.current_balance:,.0f}", S_XLARGE, fill='white', anchor='mm', bold=True)

    status = "Amount Due" if person.current_balance > 0 else "Clear"
    _draw_text(draw, (width//2, y_pos + 180), status, S_NORMAL, fill='white', anchor='mm')

    # Footer
    _draw_text(draw, (width//2, 710), "Thank you for your business!", S_SMALL, fill='#666', anchor='mm')
    _draw_text(draw, (width//2, 740), "Stock Management System", S_SMALL, fill='#999', anchor='mm')

    img_io = BytesIO()
    img.save(img_io, 'PNG', quality=95)
    img_io.seek(0)
    return img_io.getvalue()


# ---------- Temporary file helper ----------

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
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=f'{prefix}_')
    temp_file.write(image_bytes)
    temp_file.close()
    return temp_file.name


def image_to_base64(image_bytes):
    """Convert image bytes to base64 string for embedding."""
    return base64.b64encode(image_bytes).decode('utf-8')


def _clean_phone(phone, default_cc='92'):
    """Normalize a phone number to digits-only international format.

    Handles: '03113335055' (local), '+92 311 3335055', '0092...',
    '92311...' and bare national numbers like '311...'.
    Returns '' if missing.
    """
    raw = (phone or '').strip()
    if not raw:
        return ''

    # Explicit international prefix: keep the digits as-is (they already
    # include the country code).
    if raw.startswith('+') or raw.startswith('00'):
        digits = re.sub(r'\D', '', raw)
        if digits.startswith('00'):
            digits = digits[2:]
        return digits

    digits = re.sub(r'\D', '', raw)
    if not digits:
        return ''
    if digits.startswith('0'):
        # Local format, e.g. 03113335055 -> 923113335055
        return default_cc + digits[1:]
    if digits.startswith(default_cc):
        return digits
    # Bare national number without leading zero, e.g. 3113335055
    return default_cc + digits


def send_whatsapp_image_browser(phone, message_text):
    """
    Generate WhatsApp Web link with pre-filled message.
    Image will be downloaded separately and user attaches it.

    Returns:
        dict: {url, phone, message}
    """
    phone = _clean_phone(phone)
    whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message_text)}" if phone else ''
    return {'url': whatsapp_url, 'phone': phone, 'message': message_text}


def get_whatsapp_desktop_link(phone, message_text):
    """
    Generate link to open WhatsApp Desktop with message.

    Returns:
        dict: {desktop_url, web_url, phone, message}
    """
    phone = _clean_phone(phone)
    text = urllib.parse.quote(message_text)
    desktop_url = f"whatsapp://send?phone={phone}&text={text}" if phone else ''
    web_url = f"https://wa.me/{phone}?text={text}" if phone else ''
    return {'desktop_url': desktop_url, 'web_url': web_url,
            'phone': phone, 'message': message_text}