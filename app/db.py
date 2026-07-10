from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Instantiate the extensions without binding them to an app yet (App Factory Pattern)
db = SQLAlchemy()
migrate = Migrate()