
from flask_sqlalchemy import SQLAlchemy
import logging

db = SQLAlchemy()

def init_app(app):
    app.logger.setLevel(logging.INFO)
    db.init_app(app)
    
    with app.app_context():
        try:
            db.engine.connect()
            app.logger.info("Database connection successful")
        except Exception as e:
            app.logger.error(f"Database connection failed: {str(e)}")
