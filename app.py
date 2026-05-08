from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
import uuid
import os
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import os
import logging
import requests
import time
from sqlalchemy import event, exc
from sqlalchemy.pool import Pool
from functools import wraps

# Initialize extensions
db = SQLAlchemy()


# Database connection health check and retry decorator
def with_db_retry(max_retries=3, delay=1):

    def decorator(func):

        @wraps(func)
        def app_retry_wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (exc.DisconnectionError, exc.OperationalError) as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(
                        f"Database connection error (attempt {attempt + 1}/{max_retries}): {str(e)}"
                    )
                    print("Retrying database connection...")
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
                    # Force connection pool refresh
                    db.engine.dispose()
                except Exception as e:
                    raise e
            return None

        return app_retry_wrapper

    return decorator


# Connection pool event listeners for health monitoring
@event.listens_for(Pool, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    print("New database connection established")


@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    print("Connection checked out from pool")


@event.listens_for(Pool, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    print("Connection returned to pool")


@event.listens_for(Pool, "invalidate")
def receive_invalidate(dbapi_connection, connection_record, exception):
    print(f"Connection invalidated: {exception}")


# User Model
class User(db.Model):
    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.String(36),
                   primary_key=True,
                   default=lambda: str(uuid.uuid4()))
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    company_name = db.Column(db.String(100), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# UserSettings Model
class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36),
                        db.ForeignKey('user.id'),
                        nullable=False)
    account_sid = db.Column(db.String(100), nullable=True)
    account_token = db.Column(db.String(100), nullable=True)
    sms_number = db.Column(db.String(20), nullable=True)
    is_number_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)


# Contact Model for SMS management
class Contact(db.Model):
    __tablename__ = 'contacts'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36),
                        db.ForeignKey('user.id'),
                        nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    thread_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)


# Message Model for chat history
class Message(db.Model):
    __tablename__ = 'messages'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer,
                           db.ForeignKey('contacts.id'),
                           nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(10),
                             nullable=False)  # 'incoming' or 'outgoing'
    ai_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Backend Log Model for comprehensive logging
class BackendLog(db.Model):
    __tablename__ = 'backend_logs'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer,
                           db.ForeignKey('contacts.id'),
                           nullable=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    log_level = db.Column(
        db.String(10), nullable=False)  # 'INFO', 'ERROR', 'WARNING', 'DEBUG'
    log_category = db.Column(
        db.String(50),
        nullable=False)  # 'SMS', 'AUTH', 'DATABASE', 'AI_RESPONSE', etc.
    action = db.Column(
        db.String(100),
        nullable=False)  # 'MESSAGE_RECEIVED', 'AI_RESPONSE_GENERATED', etc.
    description = db.Column(db.Text, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    thread_id = db.Column(db.String(100), nullable=True)
    request_data = db.Column(db.Text,
                             nullable=True)  # JSON string of request data
    response_data = db.Column(db.Text,
                              nullable=True)  # JSON string of response data
    error_details = db.Column(db.Text, nullable=True)
    duration_ms = db.Column(db.Integer,
                            nullable=True)  # Duration in milliseconds
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'extreme-game-truck-secret-key-2024'

    # Enhanced database configuration with connection pooling
    database_url = os.environ.get(
        'DATABASE_URL',
        f"postgresql://{os.environ.get('PGUSER')}:{os.environ.get('PGPASSWORD')}@{os.environ.get('PGHOST')}:{os.environ.get('PGPORT')}/{os.environ.get('PGDATABASE')}?sslmode=require"
    )

    # Use Neon's connection pooler for better reliability
    if '.us-east-2' in database_url:
        database_url = database_url.replace('.us-east-2', '-pooler.us-east-2')

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Enhanced SQLAlchemy engine configuration
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_timeout': 20,
        'pool_recycle': 3600,  # Recycle connections every hour
        'pool_pre_ping': True,  # Verify connections before use
        'max_overflow': 20,
        'echo': False,  # Set to True for SQL debugging
        'connect_args': {
            "keepalives_idle": 600,
            "keepalives_interval": 30,
            "keepalives_count": 3,
        }
    }

    # Initialize extensions
    db.init_app(app)
    CORS(app,
         origins="*",
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         supports_credentials=False)

    # Make models available to blueprints
    app.db = db
    app.User = User
    app.UserSettings = UserSettings
    app.Contact = Contact
    app.Message = Message
    app.BackendLog = BackendLog

    # Database health check function
    def check_db_health():
        try:
            with app.app_context():
                db.session.execute(db.text('SELECT 1'))
                db.session.commit()
                return True
        except Exception as e:
            print(f"Database health check failed: {str(e)}")
            return False

    app.check_db_health = check_db_health

    # Register blueprints
    from backend.auth import auth_bp
    from backend.user import user_bp
    from backend.settings import settings_bp
    from backend.dashboard import dashboard_bp
    from backend.sms import sms_bp
    from backend.egt_widget_message import egt_widget_message_bp
    from backend.logs import logs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sms_bp)
    app.register_blueprint(egt_widget_message_bp)
    app.register_blueprint(logs_bp)

    # Serve React static files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react_app(path):
        if path != "" and os.path.exists(os.path.join('dist', path)):
            response = send_from_directory('dist', path)
            # No cache for HTML files
            response.headers[
                'Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        else:
            response = send_from_directory('dist', 'index.html')
            # Never cache index.html
            response.headers[
                'Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

    # Serve static assets
    @app.route('/assets/<path:filename>')
    def serve_assets(filename):
        response = send_from_directory('dist/assets', filename)
        # No cache for assets - always fresh
        response.headers[
            'Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return app


app = create_app()


# Database health check endpoint
@app.route('/api/health/db', methods=['GET'])
def db_health_check():
    try:
        health_status = app.check_db_health()
        if health_status:
            return jsonify({
                'status': 'healthy',
                'message': 'Database connection is working'
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'message': 'Database connection failed'
            }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Health check error: {str(e)}'
        }), 500


if __name__ == '__main__':
    with app.app_context():
        try:
            # Create all database tables with retry logic
            max_retries = 3  # Reduced retries for faster startup
            for attempt in range(max_retries):
                try:
                    db.create_all()
                    print("Database tables created successfully!")
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(
                            f"Failed to create database tables after {max_retries} attempts: {str(e)}"
                        )
                        raise e
                    print(
                        f"Database creation attempt {attempt + 1} failed: {str(e)}"
                    )
                    print("Retrying...")
                    time.sleep(1)  # Reduced delay
        except Exception as e:
            print(f"Critical database error: {str(e)}")

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)

    # Use PORT environment variable if available (for deployment), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
