import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.models import Material
from app.db import db

materials_bp = Blueprint('materials', __name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# 1. MATERIALS LIST
@materials_bp.route('/')
@login_required
def list_materials():
    all_materials = Material.query.order_by(Material.id.desc()).all()
    return render_template('materials/list.html', materials=all_materials)


# 2. ADD NEW MATERIAL
@materials_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_material():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        unit = request.form.get('unit').strip()
        description = request.form.get('description').strip()

        if not name or not unit:
            flash('برائے مہربانی مٹیریل کا نام اور اکائی (Unit) لازمی درج کریں۔', 'danger')
            return redirect(url_for('material_bp.add_material'))

        # Image Upload Handling
        image_file = 'default_material.png'
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Unique filename banane ke liye id ya timestamp use kar sakte hain, abhi direct save krty hain
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')

                # Agar directory nahi bani hui to auto-create ho jaye
                os.makedirs(upload_folder, exist_ok=True)

                file.save(os.path.join(upload_folder, filename))
                image_file = filename

        new_material = Material(
            name=name,
            unit=unit,
            description=description,
            image_file=image_file
        )

        db.session.add(new_material)
        db.session.commit()
        flash('نیا مٹیریل کامیابی سے شامل کر دیا گیا ہے!', 'success')
        return redirect(url_for('material_bp.list_materials'))

    return render_template('materials/add.html')


# 3. EDIT MATERIAL
@materials_bp.route('/edit/<int:material_id>', methods=['GET', 'POST'])
@login_required
def edit_material(material_id):
    material = Material.query.get_or_404(material_id)

    if request.method == 'POST':
        material.name = request.form.get('name').strip()
        material.unit = request.form.get('unit').strip()
        material.description = request.form.get('description').strip()

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                material.image_file = filename  # Database link update

        db.session.commit()
        flash('مٹیریل کا ریکارڈ کامیابی سے تبدیل کر دیا گیا ہے!', 'success')
        return redirect(url_for('material_bp.list_materials'))

    return render_template('materials/edit.html', material=material)


# 4. DELETE MATERIAL
@materials_bp.route('/delete/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    material = Material.query.get_or_404(material_id)

    # Rule: database se link remove hoga, image storage bucket/folder se physically delete nahi hogi
    db.session.delete(material)
    db.session.commit()

    flash('مٹیریل کا ریکارڈ سسٹم سے ختم کر دیا گیا ہے۔', 'warning')
    return redirect(url_for('material_bp.list_materials'))