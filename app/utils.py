"""Utility functions for the application."""
import os
import tempfile
import base64
import urllib.parse
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


def create_receipt_image(entry, entry_type='stock_in'):
    """
    Create receipt image using Pillow (PIL).
    
    Args:
        entry: StockIn or StockOut entry
        entry_type: 'stock_in' or 'stock_out'
    
    Returns:
        bytes: PNG image data
    """
    # Image dimensions
    width = 800
    height = 1000
    
    # Colors
    if entry_type == 'stock_in':
        gradient_start = (102, 126, 234)  # Purple
        gradient_end = (118, 75, 162)
    else:
        gradient_start = (17, 153, 142)  # Teal
        gradient_end = (56, 239, 125)  # Green
    
    # Create image
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts (with fallback)
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw gradient header
    for y in range(200):
        ratio = y / 200
        r = int(gradient_start[0] * (1 - ratio) + gradient_end[0] * ratio)
        g = int(gradient_start[1] * (1 - ratio) + gradient_end[1] * ratio)
        b = int(gradient_start[2] * (1 - ratio) + gradient_end[2] * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))
    
    # Header text
    draw.text((width//2, 50), "Sher Ali Building Material", font=font_medium, fill='white', anchor='mm')
    receipt_type = "Purchase Receipt" if entry_type == 'stock_in' else "Sales Receipt"
    draw.text((width//2, 90), receipt_type, font=font_normal, fill='white', anchor='mm')
    draw.text((width//2, 130), f"Receipt #{entry.id}", font=font_normal, fill='white', anchor='mm')
    draw.text((width//2, 165), entry.date.strftime('%d/%m/%Y'), font=font_small, fill='white', anchor='mm')
    
    # Body starts at y=220
    y_pos = 240
    x_margin = 50
    
    # Person info
    if entry_type == 'stock_in':
        person = entry.supplier
        person_label = "Supplier"
    else:
        person = entry.customer
        person_label = "Customer"
    
    draw.text((x_margin, y_pos), f"{person_label}:", font=font_normal, fill='#333')
    draw.text((width - x_margin, y_pos), person.name, font=font_normal, fill='#000', anchor='rm')
    y_pos += 40
    
    if person.phone:
        draw.text((x_margin, y_pos), "Phone:", font=font_normal, fill='#333')
        draw.text((width - x_margin, y_pos), person.phone, font=font_normal, fill='#000', anchor='rm')
        y_pos += 40
    
    # Separator line
    draw.line([(x_margin, y_pos), (width - x_margin, y_pos)], fill='#ddd', width=2)
    y_pos += 30
    
    # Material details
    draw.text((x_margin, y_pos), "Material:", font=font_normal, fill='#333')
    draw.text((width - x_margin, y_pos), entry.material.name, font=font_normal, fill='#000', anchor='rm')
    y_pos += 40
    
    draw.text((x_margin, y_pos), "Quantity:", font=font_normal, fill='#333')
    draw.text((width - x_margin, y_pos), f"{entry.quantity} {entry.material.unit}", font=font_normal, fill='#000', anchor='rm')
    y_pos += 40
    
    draw.text((x_margin, y_pos), "Rate:", font=font_normal, fill='#333')
    draw.text((width - x_margin, y_pos), f"Rs. {entry.rate:,.0f}", font=font_normal, fill='#000', anchor='rm')
    y_pos += 50
    
    # Financial summary box
    draw.rectangle([(x_margin, y_pos), (width - x_margin, y_pos + 250)], outline='#ddd', width=2)
    y_pos += 20
    
    draw.text((x_margin + 20, y_pos), "Subtotal:", font=font_normal, fill='#666')
    draw.text((width - x_margin - 20, y_pos), f"Rs. {(entry.quantity * entry.rate):,.0f}", font=font_normal, fill='#000', anchor='rm')
    y_pos += 40
    
    if entry.other_expenses > 0:
        draw.text((x_margin + 20, y_pos), "Other Expenses:", font=font_normal, fill='#666')
        draw.text((width - x_margin - 20, y_pos), f"Rs. {entry.other_expenses:,.0f}", font=font_normal, fill='#000', anchor='rm')
        y_pos += 40
    
    if hasattr(entry, 'discount') and entry.discount > 0:
        draw.text((x_margin + 20, y_pos), "Discount:", font=font_normal, fill='#666')
        draw.text((width - x_margin - 20, y_pos), f"- Rs. {entry.discount:,.0f}", font=font_normal, fill='#dc3545', anchor='rm')
        y_pos += 40
    
    # Separator
    draw.line([(x_margin + 20, y_pos), (width - x_margin - 20, y_pos)], fill='#999', width=2)
    y_pos += 15
    
    draw.text((x_margin + 20, y_pos), "TOTAL:", font=font_medium, fill='#000')
    draw.text((width - x_margin - 20, y_pos), f"Rs. {entry.total_amount:,.0f}", font=font_medium, fill=gradient_start, anchor='rm')
    y_pos += 45
    
    draw.text((x_margin + 20, y_pos), "Paid:", font=font_normal, fill='#666')
    draw.text((width - x_margin - 20, y_pos), f"Rs. {entry.paid_amount:,.0f}", font=font_normal, fill='#28a745', anchor='rm')
    y_pos += 60
    
    # Remaining amount highlight box
    box_y = y_pos
    draw.rectangle([(x_margin, box_y), (width - x_margin, box_y + 120)], fill=gradient_start)
    
    draw.text((width//2, box_y + 30), "REMAINING AMOUNT", font=font_normal, fill='white', anchor='mm')
    draw.text((width//2, box_y + 75), f"Rs. {entry.remaining:,.0f}", font=font_large, fill='white', anchor='mm')
    
    # Footer
    y_pos = box_y + 140
    draw.text((width//2, y_pos), "Thank you for your business!", font=font_small, fill='#666', anchor='mm')
    draw.text((width//2, y_pos + 25), "Sher Ali Building Material", font=font_small, fill='#999', anchor='mm')
    
    # Convert to bytes
    img_io = BytesIO()
    img.save(img_io, 'PNG', quality=95)
    img_io.seek(0)
    return img_io.getvalue()


def create_khata_statement_image(person, person_type):
    """
    Create Khata statement image using Pillow (PIL).
    
    Args:
        person: Supplier or Customer object
        person_type: 'supplier' or 'customer'
    
    Returns:
        bytes: PNG image data
    """
    # Image dimensions
    width = 800
    height = 800
    
    # Colors
    if person_type == 'supplier':
        gradient_start = (102, 126, 234)  # Purple
        gradient_end = (118, 75, 162)
    else:
        gradient_start = (17, 153, 142)  # Teal
        gradient_end = (56, 239, 125)
    
    # Create image
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts
    try:
        font_xlarge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        font_xlarge = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw gradient header
    for y in range(180):
        ratio = y / 180
        r = int(gradient_start[0] * (1 - ratio) + gradient_end[0] * ratio)
        g = int(gradient_start[1] * (1 - ratio) + gradient_end[1] * ratio)
        b = int(gradient_start[2] * (1 - ratio) + gradient_end[2] * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))
    
    # Header text
    draw.text((width//2, 50), "Sher Ali Building Material", font=font_medium, fill='white', anchor='mm')
    draw.text((width//2, 90), "Account Statement", font=font_normal, fill='white', anchor='mm')
    person_label = "Supplier" if person_type == 'supplier' else "Customer"
    draw.text((width//2, 135), f"{person_label} Account", font=font_small, fill='white', anchor='mm')
    
    # Body starts at y=200
    y_pos = 220
    x_margin = 60
    
    # Person info box
    box_height = 200
    draw.rectangle([(x_margin, y_pos), (width - x_margin, y_pos + box_height)], fill='#f8f9fa', outline='#ddd', width=2)
    
    y_pos += 25
    draw.text((x_margin + 30, y_pos), "Name:", font=font_normal, fill='#666')
    draw.text((width - x_margin - 30, y_pos), person.name, font=font_medium, fill='#000', anchor='rm')
    y_pos += 50
    
    if person.phone:
        draw.text((x_margin + 30, y_pos), "Phone:", font=font_normal, fill='#666')
        draw.text((width - x_margin - 30, y_pos), person.phone, font=font_normal, fill='#000', anchor='rm')
        y_pos += 50
    
    if person.address:
        draw.text((x_margin + 30, y_pos), "Address:", font=font_normal, fill='#666')
        # Truncate long addresses
        addr = person.address[:40] + '...' if len(person.address) > 40 else person.address
        draw.text((width - x_margin - 30, y_pos), addr, font=font_normal, fill='#000', anchor='rm')
        y_pos += 50
    
    now = datetime.now()
    draw.text((x_margin + 30, y_pos), "Date:", font=font_normal, fill='#666')
    draw.text((width - x_margin - 30, y_pos), now.strftime('%d/%m/%Y'), font=font_normal, fill='#000', anchor='rm')
    
    # Balance box
    y_pos = 450
    box_height = 220
    draw.rectangle([(x_margin, y_pos), (width - x_margin, y_pos + box_height)], fill=gradient_start)
    
    draw.text((width//2, y_pos + 40), "CURRENT BALANCE", font=font_medium, fill='white', anchor='mm')
    draw.text((width//2, y_pos + 120), f"Rs. {person.current_balance:,.0f}", font=font_xlarge, fill='white', anchor='mm')
    
    status = "Amount Due" if person.current_balance > 0 else "Clear"
    draw.text((width//2, y_pos + 180), status, font=font_normal, fill='white', anchor='mm')
    
    # Footer
    draw.text((width//2, 710), "Thank you for your business!", font=font_small, fill='#666', anchor='mm')
    draw.text((width//2, 740), "Stock Management System", font=font_small, fill='#999', anchor='mm')
    
    # Convert to bytes
    img_io = BytesIO()
    img.save(img_io, 'PNG', quality=95)
    img_io.seek(0)
    return img_io.getvalue()


def save_temp_image(image_bytes, prefix='receipt'):
    """
    Save image bytes to temporary file.
    
    Args:
        image_bytes: Image data as bytes
        prefix: Filename prefix
    
    Returns:
        str: Path to temporary file
    """
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix='.png',
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
