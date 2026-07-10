from app import create_app
from app.db import db
from app.models import User

app = create_app()

with app.app_context():
    # Look for existing admin user
    admin_exists = User.query.filter_by(username='admin').first()
    if not admin_exists:
        new_admin = User()
        new_admin.username = 'sherali'
        new_admin.set_password('stock@123') # Set clean baseline password
        db.session.add(new_admin)
        db.session.commit()
        print("Success: Admin master profile generated cleanly! Username: admin | Password: admin123")
    else:
        print("Master profile 'admin' already configured inside active user system database.")