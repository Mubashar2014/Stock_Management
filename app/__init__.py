from flask import Flask, redirect, url_for
from app.config import Config
from app.db import db, migrate
from flask_login import LoginManager, current_user

login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Login Manager Setup
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "برائے مہربانی پہلے لاگ ان کریں۔"
    login_manager.login_message_category = "danger"

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints Import aur Registration (As per your base.html names)
    from app.auth.routes import auth_bp
    from app.suppliers.routes import suppliers_bp
    from app.customers.routes import customers_bp
    from app.materials.routes import materials_bp
    from app.stock_in.routes import stock_in_bp
    from app.stock_out.routes import stock_out_bp
    from app.cashbook.routes import cashbook_bp


    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(suppliers_bp, url_prefix='/suppliers', name='supplier_bp')
    app.register_blueprint(customers_bp, url_prefix='/customers', name='customer_bp')
    app.register_blueprint(materials_bp, url_prefix='/materials', name='material_bp')
    app.register_blueprint(stock_in_bp, url_prefix='/stock-in', name='stock_in')
    app.register_blueprint(stock_out_bp, url_prefix='/stock-out', name='stock_out')
    app.register_blueprint(cashbook_bp, url_prefix='/cashbook', name='cashbook')

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('auth.dashboard'))
        return redirect(url_for('auth.login'))

    return app