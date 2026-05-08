
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
import logging
import jwt
from werkzeug.security import check_password_hash
from sqlalchemy import exc
import time
from functools import wraps

auth_bp = Blueprint('auth', __name__)

# Database connection retry decorator
def with_db_retry(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def auth_retry_wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (exc.DisconnectionError, exc.OperationalError) as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"Database connection error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    print("Retrying database connection...")
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
                    # Force connection pool refresh
                    current_app.db.engine.dispose()
                except Exception as e:
                    raise e
            return None
        return auth_retry_wrapper
    return decorator

@auth_bp.route('/api/auth/login', methods=['POST'])
@with_db_retry(max_retries=3)
def login():
    try:
        data = request.json
        
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'message': 'Email and password are required'}), 400
        
        # Find user with enhanced retry logic
        User = current_app.User
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not check_password_hash(user.password, data['password']):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, current_app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'fullName': user.full_name,
                'email': user.email
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'message': 'Login failed'}), 500

@auth_bp.route('/api/auth/register', methods=['POST'])
@with_db_retry(max_retries=3)
def register():
    try:
        from werkzeug.security import generate_password_hash
        import uuid
        
        data = request.json
        
        if not data:
            return jsonify({'message': 'No data provided'}), 400
            
        # Validate required fields
        required_fields = ['fullName', 'email', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'message': f'{field} is required'}), 400
        
        # Check if email already exists
        User = current_app.User
        db = current_app.db
        
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'message': 'Email already registered'}), 409
        
        # Hash the password
        hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
        
        # Create new user
        new_user = User(
            id=str(uuid.uuid4()),
            full_name=data['fullName'],
            email=data['email'],
            company_name=data.get('companyName', ''),  # Optional field
            password=hashed_password,
            is_verified=True  # Auto-verify for development
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'message': 'Registration successful!',
            'verified': True
        }), 201
        
    except Exception as e:
        db = current_app.db
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    try:
        user_id = request.json.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User ID is required'}), 400
            
        # Log the logout event
        logging.info(f"User {user_id} logged out at {datetime.now()}")
        
        return jsonify({'success': True, 'message': 'Logout recorded successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to record logout'}), 500
