from flask import Flask, redirect, url_for, render_template, jsonify
from app.config import Config
from app.db import db, migrate
from flask_login import LoginManager, current_user
from sqlalchemy import text
import logging

login_manager = LoginManager()
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Setup logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    # Login Manager Setup
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "برائے مہربانی پہلے لاگ ان کریں۔"
    login_manager.login_message_category = "danger"

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        logger.error(f'Internal error: {str(e)}')
        return render_template('500.html'), 500

    @app.errorhandler(400)
    def bad_request(e):
        return render_template('400.html'), 400

    @app.before_request
    def before_request():
        """Ensure database connection is available"""
        try:
            db.session.execute(text('SELECT 1'))
        except Exception as e:
            logger.error(f'Database connection error: {str(e)}')
            db.session.rollback()

    # Blueprints Import aur Registration (As per your base.html names)
    from app.auth.routes import auth_bp
    from app.suppliers.routes import suppliers_bp
    from app.customers.routes import customers_bp
    from app.materials.routes import materials_bp
    from app.stock_in.routes import stock_in_bp
    from app.stock_out.routes import stock_out_bp
    from app.cashbook.routes import cashbook_bp
    from app.khata.routes import khata_bp
    from app.profit.routes import profit_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(suppliers_bp, url_prefix='/suppliers', name='supplier_bp')
    app.register_blueprint(customers_bp, url_prefix='/customers', name='customer_bp')
    app.register_blueprint(materials_bp, url_prefix='/materials', name='material_bp')
    app.register_blueprint(stock_in_bp, url_prefix='/stock-in', name='stock_in')
    app.register_blueprint(stock_out_bp, url_prefix='/stock-out', name='stock_out')
    app.register_blueprint(cashbook_bp, url_prefix='/cashbook', name='cashbook')
    app.register_blueprint(khata_bp, url_prefix='/khata', name='khata')
    app.register_blueprint(profit_bp, url_prefix='/profit', name='profit')

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('auth.dashboard'))
        return redirect(url_for('auth.login'))

    return app