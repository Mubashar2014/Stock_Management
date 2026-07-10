import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'njkhasdfjkashfjksdhfjkasdhfjkdahlj312#$%#$%#$sbdjh')

    # MySQL Database Connection String
    # Format: mysql+mysqlconnector://user:password@host/dbname
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+mysqlconnector://root:Qwerty0.@localhost/stockmaterial_db'
    )

    # Disable tracking modifications to save memory
    SQLALCHEMY_TRACK_MODIFICATIONS = False