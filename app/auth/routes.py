from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.models import Material, StockIn, StockOut
from app.db import db
from sqlalchemy import func

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('supplier_bp.list_suppliers'))

    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('auth.dashboard'))
        else:
            flash('غلط یوزر نیم یا پاس ورڈ! دوبارہ کوشش کریں۔', 'danger')
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html')


@auth_bp.route('/dashboard')
@login_required
def dashboard():
    materials = Material.query.all()
    materials_data = []

    for material in materials:
        # Summing total purchased quantity
        total_in = db.session.query(func.sum(StockIn.quantity)).filter(StockIn.material_id == material.id).scalar() or 0

        # Summing total sold quantity
        total_out = db.session.query(func.sum(StockOut.quantity)).filter(
            StockOut.material_id == material.id).scalar() or 0

        # Calculating real-time remaining stock
        remaining_qty = total_in - total_out

        materials_data.append({
            'name': material.name,
            'unit': material.unit,
            'image_file': material.image_file,
            'remaining_qty': remaining_qty
        })

    return render_template('dashboard.html', materials=materials_data)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))