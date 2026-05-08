
from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import jwt
from datetime import datetime, timedelta

logs_bp = Blueprint('logs', __name__)

def token_required(f):
    @wraps(f)
    def logs_token_wrapper(*args, **kwargs):
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

            User = current_app.User
            user_obj = User.query.filter_by(id=current_user_id).first()

            if not user_obj:
                return jsonify({'message': 'User not found!'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401

        return f(user_obj, *args, **kwargs)
    return logs_token_wrapper


@logs_bp.route('/api/logs', methods=['GET'])
@token_required
def get_backend_logs(current_user):
    """Get backend logs with filtering options"""
    try:
        BackendLog = current_app.BackendLog
        Contact = current_app.Contact
        
        # Get query parameters
        contact_id = request.args.get('contact_id', type=int)
        log_category = request.args.get('category')
        log_level = request.args.get('level')
        phone_number = request.args.get('phone_number')
        days = request.args.get('days', default=7, type=int)
        limit = request.args.get('limit', default=100, type=int)
        
        # Build query
        query = BackendLog.query
        
        # Filter by date range
        if days > 0:
            since_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(BackendLog.created_at >= since_date)
        
        # Apply filters
        if contact_id:
            query = query.filter(BackendLog.contact_id == contact_id)
        
        if log_category:
            query = query.filter(BackendLog.log_category == log_category)
            
        if log_level:
            query = query.filter(BackendLog.log_level == log_level)
            
        if phone_number:
            query = query.filter(BackendLog.phone_number == phone_number)
        
        # Get user's contacts to filter logs
        user_contacts = Contact.query.filter_by(user_id=current_user.id).all()
        user_contact_ids = [c.id for c in user_contacts]
        
        # Filter to user's contacts or system-wide logs (no contact_id)
        if user_contact_ids:
            query = query.filter(
                (BackendLog.contact_id.in_(user_contact_ids)) | 
                (BackendLog.contact_id == None) |
                (BackendLog.user_id == current_user.id)
            )
        else:
            # If user has no contacts, only show their own logs
            query = query.filter(BackendLog.user_id == current_user.id)
        
        # Order by latest first and limit results
        logs = query.order_by(BackendLog.created_at.desc()).limit(limit).all()
        
        # Format response
        logs_data = []
        for log in logs:
            # Get contact info if available
            contact_info = None
            if log.contact_id:
                contact = Contact.query.get(log.contact_id)
                if contact:
                    contact_info = {
                        'id': contact.id,
                        'name': contact.name,
                        'phone_number': contact.phone_number
                    }
            
            logs_data.append({
                'id': log.id,
                'contact_id': log.contact_id,
                'contact_info': contact_info,
                'user_id': log.user_id,
                'log_level': log.log_level,
                'log_category': log.log_category,
                'action': log.action,
                'description': log.description,
                'phone_number': log.phone_number,
                'thread_id': log.thread_id,
                'request_data': log.request_data,
                'response_data': log.response_data,
                'error_details': log.error_details,
                'duration_ms': log.duration_ms,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'created_at': log.created_at.isoformat()
            })
        
        return jsonify({
            'logs': logs_data,
            'total_count': len(logs_data),
            'filters_applied': {
                'contact_id': contact_id,
                'category': log_category,
                'level': log_level,
                'phone_number': phone_number,
                'days': days,
                'limit': limit
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching backend logs: {str(e)}")
        return jsonify({'message': 'Failed to fetch logs'}), 500


@logs_bp.route('/api/logs/stats', methods=['GET'])
@token_required
def get_log_stats(current_user):
    """Get statistics about backend logs"""
    try:
        BackendLog = current_app.BackendLog
        Contact = current_app.Contact
        
        # Get user's contacts
        user_contacts = Contact.query.filter_by(user_id=current_user.id).all()
        user_contact_ids = [c.id for c in user_contacts]
        
        # Base query for user's logs
        base_query = BackendLog.query
        if user_contact_ids:
            base_query = base_query.filter(
                (BackendLog.contact_id.in_(user_contact_ids)) | 
                (BackendLog.contact_id == None) |
                (BackendLog.user_id == current_user.id)
            )
        else:
            base_query = base_query.filter(BackendLog.user_id == current_user.id)
        
        # Get stats for last 7 days
        since_date = datetime.utcnow() - timedelta(days=7)
        recent_query = base_query.filter(BackendLog.created_at >= since_date)
        
        # Count by category
        categories = {}
        for log in recent_query.all():
            categories[log.log_category] = categories.get(log.log_category, 0) + 1
        
        # Count by level
        levels = {}
        for log in recent_query.all():
            levels[log.log_level] = levels.get(log.log_level, 0) + 1
        
        # Total logs
        total_logs = base_query.count()
        recent_logs = recent_query.count()
        
        return jsonify({
            'total_logs': total_logs,
            'recent_logs_7days': recent_logs,
            'categories': categories,
            'levels': levels,
            'user_contacts_count': len(user_contacts)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching log stats: {str(e)}")
        return jsonify({'message': 'Failed to fetch log statistics'}), 500
