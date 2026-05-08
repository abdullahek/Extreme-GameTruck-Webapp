
from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import jwt
from datetime import datetime
import requests
import base64
from requests.auth import HTTPBasicAuth

settings_bp = Blueprint('settings', __name__)

def token_required(f):
    @wraps(f)
    def settings_token_wrapper(*args, **kwargs):
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
    return settings_token_wrapper

@settings_bp.route('/api/settings', methods=['GET'])
@token_required
def get_settings(current_user):
    try:
        UserSettings = current_app.UserSettings
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()

        if not settings:
            return jsonify({
                'account_sid': '',
                'account_token': '',
                'sms_number': '',
                'is_number_verified': False
            }), 200

        # Mask account token for security
        masked_token = ''
        if settings.account_token:
            if len(settings.account_token) > 4:
                masked_token = settings.account_token[:2] + '*' * (len(settings.account_token) - 4) + settings.account_token[-2:]
            else:
                masked_token = '*' * len(settings.account_token)

        return jsonify({
            'account_sid': settings.account_sid or '',
            'account_token': masked_token,
            'sms_number': settings.sms_number or '',
            'is_number_verified': settings.is_number_verified
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching settings: {str(e)}")
        return jsonify({'message': 'Failed to fetch settings'}), 500

@settings_bp.route('/api/settings', methods=['POST'])
@token_required
def save_settings(current_user):
    try:
        UserSettings = current_app.UserSettings
        db = current_app.db
        data = request.json

        settings = UserSettings.query.filter_by(user_id=current_user.id).first()

        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.session.add(settings)

        # Update settings
        old_number = settings.sms_number
        settings.account_sid = data.get('account_sid', '')
        
        # Only update token if a new one is provided (not masked)
        if data.get('account_token') and '*' not in data.get('account_token', ''):
            settings.account_token = data.get('account_token', '')
        
        settings.sms_number = data.get('sms_number', '')

        # Reset verification if phone number changed
        if old_number != settings.sms_number:
            settings.is_number_verified = False

        settings.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'message': 'Settings saved successfully!',
            'is_number_verified': settings.is_number_verified
        }), 200

    except Exception as e:
        db = current_app.db
        db.session.rollback()
        current_app.logger.error(f"Error saving settings: {str(e)}")
        return jsonify({'message': 'Failed to save settings'}), 500

@settings_bp.route('/api/settings/verify-number', methods=['POST'])
@token_required
def verify_number(current_user):
    try:
        data = request.json
        
        # Get credentials and phone number from frontend request
        account_sid = data.get('account_sid', '').strip()
        account_token = data.get('account_token', '').strip()
        sms_number = data.get('sms_number', '').strip()

        if not account_sid or not account_token or not sms_number:
            return jsonify({'message': 'Account SID, Account Token, and Phone Number are required'}), 400

        # Don't allow masked tokens - user must provide real token
        if '*' in account_token:
            return jsonify({'message': 'Please enter your actual Account Token (not masked)'}), 400

        # Check if placeholder or invalid number
        if sms_number.startswith('Eg.') or len(sms_number) < 8:
            return jsonify({'message': 'Invalid phone number provided'}), 400

        try:
            # Clean phone number (remove any formatting)
            phone_number = sms_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if not phone_number.startswith('+'):
                if phone_number.startswith('1') and len(phone_number) == 11:
                    phone_number = '+' + phone_number
                elif len(phone_number) == 10:
                    phone_number = '+1' + phone_number
                else:
                    phone_number = '+' + phone_number

            # Make request to Twilio Lookup API v2
            url = f"https://lookups.twilio.com/v2/PhoneNumbers/{phone_number}"
            
            print(f"\n=== TWILIO LOOKUP API REQUEST ===")
            print(f"URL: {url}")
            print(f"Account SID: {account_sid}")
            print(f"Phone Number: {phone_number}")
            
            response = requests.get(url, auth=HTTPBasicAuth(account_sid, account_token), timeout=10)

            print(f"\n=== TWILIO LOOKUP API RESPONSE ===")
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                response_data = response.json()
                print(f"Response Body: {response_data}")
                
                # Enhanced logging of response fields
                if response_data.get('valid', False):
                    print(f"\n=== PHONE NUMBER VERIFICATION SUCCESS ===")
                    print(f"Valid: {response_data.get('valid')}")
                    print(f"Phone Number: {response_data.get('phone_number')}")
                    print(f"Country Code: {response_data.get('country_code')}")
                    print(f"Calling Country Code: {response_data.get('calling_country_code')}")
                    
                    # Log additional fields if present
                    if 'national_format' in response_data:
                        print(f"National Format: {response_data.get('national_format')}")
                    if 'line_type_intelligence' in response_data:
                        print(f"Line Type: {response_data.get('line_type_intelligence')}")
                    if 'caller_name' in response_data:
                        print(f"Caller Name: {response_data.get('caller_name')}")
                    if 'validation_errors' in response_data:
                        print(f"Validation Errors: {response_data.get('validation_errors')}")

                    # Update the verification status in the database
                    UserSettings = current_app.UserSettings
                    db = current_app.db
                    
                    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
                    if settings:
                        settings.is_number_verified = True
                        settings.sms_number = response_data.get('phone_number', phone_number)
                        settings.updated_at = datetime.utcnow()
                        db.session.commit()
                        print(f"Database updated: Number verified for user {current_user.id}")

                    # Safely get line_type_intelligence
                    line_type_info = response_data.get('line_type_intelligence') or {}
                    line_type = line_type_info.get('type', '') if isinstance(line_type_info, dict) else ''

                    return jsonify({
                        'message': 'Number verified successfully!',
                        'formatted_number': response_data.get('phone_number', phone_number),
                        'country_code': response_data.get('country_code', ''),
                        'calling_country_code': response_data.get('calling_country_code', ''),
                        'national_format': response_data.get('national_format', ''),
                        'line_type': line_type,
                        'valid': True,
                        'full_response': response_data  # Include full response for debugging
                    }), 200
                else:
                    print(f"Phone number marked as invalid by Twilio")
                    return jsonify({
                        'message': 'Invalid phone number according to Twilio',
                        'valid': False,
                        'validation_errors': response_data.get('validation_errors', [])
                    }), 400

            elif response.status_code == 401:
                error_data = response.json() if response.content else {}
                print(f"Authentication Error: {error_data}")
                current_app.logger.error(f"Twilio authentication failed: {error_data}")
                return jsonify({'message': 'Invalid Twilio credentials. Please check your Account SID and Auth Token.'}), 401
                
            elif response.status_code == 404:
                print(f"Phone number not found: {phone_number}")
                return jsonify({'message': 'Phone number not found or invalid format'}), 400
                
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get('message', f'Twilio API error: {response.status_code}')
                print(f"Twilio API Error: Status {response.status_code}, Body: {error_data}")
                current_app.logger.error(f"Twilio API error: {error_data}")
                return jsonify({'message': error_message}), 500

        except requests.RequestException as e:
            print(f"Network Error: {str(e)}")
            current_app.logger.error(f"Request error: {str(e)}")
            return jsonify({'message': 'Failed to connect to Twilio API - Network error'}), 500
        except Exception as e:
            print(f"Verification Error: {str(e)}")
            current_app.logger.error(f"Verification error: {str(e)}")
            return jsonify({'message': 'Phone number verification failed'}), 500

    except Exception as e:
        print(f"General Error: {str(e)}")
        current_app.logger.error(f"General error in verify_number: {str(e)}")
        return jsonify({'message': 'Verification failed'}), 500

@settings_bp.route('/api/settings/test-twilio', methods=['POST'])
@token_required
def test_twilio_connection(current_user):
    try:
        data = request.json
        
        # Get credentials from frontend request
        account_sid = data.get('account_sid', '').strip()
        account_token = data.get('account_token', '').strip()

        if not account_sid or not account_token:
            return jsonify({'message': 'Account SID and Account Token are required'}), 400

        try:
            # Test connection by making a simple API call
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"
            
            print(f"\n=== TWILIO CONNECTION TEST ===")
            print(f"URL: {url}")
            print(f"Account SID: {account_sid}")
            
            response = requests.get(url, auth=HTTPBasicAuth(account_sid, account_token), timeout=10)
            
            print(f"Test Response Status: {response.status_code}")

            if response.status_code == 200:
                response_data = response.json()
                print(f"Connection Test Response: {response_data}")
                return jsonify({
                    'message': 'Twilio connection successful!',
                    'account_name': response_data.get('friendly_name', 'Unknown'),
                    'account_status': response_data.get('status', 'Unknown')
                }), 200
            elif response.status_code == 401:
                print("Authentication failed in connection test")
                return jsonify({'message': 'Invalid Twilio credentials'}), 401
            else:
                print(f"Connection test failed with status: {response.status_code}")
                return jsonify({'message': f'Twilio connection failed: {response.status_code}'}), 500

        except requests.RequestException as e:
            print(f"Connection test network error: {str(e)}")
            current_app.logger.error(f"Connection test error: {str(e)}")
            return jsonify({'message': 'Failed to connect to Twilio API'}), 500

    except Exception as e:
        print(f"Connection test general error: {str(e)}")
        current_app.logger.error(f"Test connection error: {str(e)}")
        return jsonify({'message': 'Test connection failed'}), 500
