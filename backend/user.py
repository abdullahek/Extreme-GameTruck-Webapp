from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import jwt

user_bp = Blueprint('user', __name__)

def token_required(f):
    @wraps(f)
    def user_token_wrapper(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']

            # Access models from current_app with retry logic
            User = current_app.User
            db = current_app.db

            # Retry logic for database queries
            max_retries = 3
            user_obj = None

            for attempt in range(max_retries):
                try:
                    user_obj = User.query.filter_by(id=current_user_id).first()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        current_app.logger.error(f"Database query failed after {max_retries} attempts: {str(e)}")
                        return jsonify({'message': 'Database connection error. Please try again.'}), 503
                    current_app.logger.warning(f"Database query attempt {attempt + 1} failed: {str(e)}")
                    # Force connection refresh
                    db.engine.dispose()
                    import time
                    time.sleep(1 * (attempt + 1))

            if not user_obj:
                return jsonify({'message': 'User not found!'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401

        return f(user_obj, *args, **kwargs)
    return user_token_wrapper

@user_bp.route('/api/user/profile', methods=['GET', 'PUT'])
@token_required
def user_profile(user):
    if request.method == 'GET':
        return jsonify({
            "id": user['id'],
            "fullName": user['full_name'],
            "email": user['email'],
            "isVerified": user['is_verified']
        }), 200

    elif request.method == 'PUT':
        # Update profile logic
        data = request.json
        User = current_app.User
        db = current_app.db
        user_to_update = User.query.filter_by(id=user['id']).first()
        if user_to_update:
            user_to_update.full_name = data.get('fullName', user_to_update.full_name)
            db.session.commit()
            return jsonify({"message": "Profile updated successfully"}), 200
        return jsonify({"message": "User not found"}), 404