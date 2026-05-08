from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import jwt
from datetime import datetime
from sqlalchemy import func, desc

dashboard_bp = Blueprint('dashboard', __name__)


def token_required(f):
    @wraps(f)
    def dashboard_token_wrapper(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token,
                              current_app.config['SECRET_KEY'],
                              algorithms=["HS256"])
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

    return dashboard_token_wrapper


@dashboard_bp.route('/api/dashboard/stats', methods=['GET'])
@token_required
def get_dashboard_stats(current_user):
    """Optimized endpoint for dashboard statistics"""
    try:
        Contact = current_app.Contact
        Message = current_app.Message
        
        # Get total contacts count (single query)
        total_contacts = Contact.query.filter_by(user_id=current_user.id).count()
        
        # Get total messages count (single query)
        total_messages = Message.query.join(Contact).filter(
            Contact.user_id == current_user.id
        ).count()
        
        # Get top 5 contacts with message counts (optimized aggregation query)
        top_contacts_query = current_app.db.session.query(
            Contact.id,
            Contact.name,
            Contact.phone_number,
            func.count(Message.id).label('message_count'),
            func.max(Message.created_at).label('last_message')
        ).join(Message, Contact.id == Message.contact_id)\
         .filter(Contact.user_id == current_user.id)\
         .group_by(Contact.id, Contact.name, Contact.phone_number)\
         .order_by(desc('message_count'))\
         .limit(5)\
         .all()
        
        top_contacts = []
        for contact in top_contacts_query:
            top_contacts.append({
                'name': contact.name or contact.phone_number,
                'phone': contact.phone_number,
                'messageCount': contact.message_count,
                'lastMessage': contact.last_message.isoformat() if contact.last_message else None
            })
        
        response = jsonify({
            'totalContacts': total_contacts,
            'totalMessages': total_messages,
            'topContacts': top_contacts
        })
        # Allow caching for 30 seconds for sticky dashboard stats
        response.headers['Cache-Control'] = 'public, max-age=30'
        return response, 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {str(e)}")
        return jsonify({'message': 'Error fetching dashboard stats'}), 500
