from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import jwt
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import json
import threading
import time
from collections import defaultdict
from .logger_utils import log_sms_activity, log_ai_activity, log_database_activity, log_webhook_activity

sms_bp = Blueprint('sms', __name__)

# Global message queue to collect messages for each contact
message_queue = defaultdict(list)
# Track timers for each contact
contact_timers = {}
# Lock for thread safety
queue_lock = threading.Lock()


def token_required(f):

    @wraps(f)
    def sms_token_wrapper(*args, **kwargs):
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

    return sms_token_wrapper


def get_or_create_thread_id(contact, max_retries=5, initial_delay=2):
    """Get existing thread ID or create a new one for the contact with retry mechanism"""
    start_time = datetime.now()
    
    # Check if the contact already has a thread_id
    if hasattr(contact, 'thread_id') and contact.thread_id:
        log_ai_activity(
            action="THREAD_ID_RETRIEVED",
            description=f"Using existing thread ID for contact {contact.id}",
            contact_id=contact.id,
            thread_id=contact.thread_id,
            duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
        )
        return contact.thread_id

    # Initialize a new thread via API with retry mechanism
    for attempt in range(max_retries):
        attempt_start = datetime.now()
        delay = initial_delay * (2 ** attempt)  # Exponential backoff
        
        try:
            log_ai_activity(
                action="THREAD_CREATION_ATTEMPT",
                description=f"Attempting to create new thread for contact {contact.id} (attempt {attempt + 1}/{max_retries})",
                contact_id=contact.id
            )
            
            current_app.logger.info(f"🔄 Thread creation attempt {attempt + 1}/{max_retries} for contact {contact.id}")
            
            response = requests.post(
                "https://extreme-game-truck-graelonbrown.replit.app/thread",
                headers={"Content-Type": "application/json"},
                timeout=15)  # Increased timeout

            duration_ms = int((datetime.now() - attempt_start).total_seconds() * 1000)

            if response.status_code == 200:
                thread_data = response.json()
                thread_id = thread_data.get('thread_id')

                if not thread_id:
                    log_ai_activity(
                        action="THREAD_CREATION_FAILED",
                        description=f"Thread creation successful but thread_id missing in response (attempt {attempt + 1})",
                        contact_id=contact.id,
                        error_details="Missing thread_id in API response",
                        duration_ms=duration_ms
                    )
                    current_app.logger.error(f"❌ Thread creation attempt {attempt + 1} failed: Missing thread_id in response")
                    
                    if attempt < max_retries - 1:
                        current_app.logger.info(f"⏳ Retrying in {delay} seconds...")
                        time.sleep(delay)
                    continue

                # Store the thread ID with the contact
                try:
                    contact.thread_id = thread_id
                    current_app.db.session.commit()
                    
                    log_ai_activity(
                        action="THREAD_CREATED_SUCCESS",
                        description=f"Successfully created and stored new thread ID (attempt {attempt + 1})",
                        contact_id=contact.id,
                        thread_id=thread_id,
                        duration_ms=duration_ms
                    )
                    
                    log_database_activity(
                        action="CONTACT_THREAD_UPDATED",
                        description=f"Updated contact {contact.id} with new thread_id {thread_id}",
                        contact_id=contact.id
                    )
                    
                    current_app.logger.info(f"✅ Thread creation successful on attempt {attempt + 1}: {thread_id}")
                    return thread_id
                    
                except Exception as db_error:
                    current_app.logger.error(f"❌ Database error storing thread_id: {str(db_error)}")
                    current_app.db.session.rollback()
                    if attempt < max_retries - 1:
                        current_app.logger.info(f"⏳ Retrying in {delay} seconds...")
                        time.sleep(delay)
                    continue
                    
            else:
                log_ai_activity(
                    action="THREAD_CREATION_FAILED",
                    description=f"Failed to initialize thread - API returned {response.status_code} (attempt {attempt + 1})",
                    contact_id=contact.id,
                    error_details=f"Status: {response.status_code}, Response: {response.text}",
                    duration_ms=duration_ms
                )
                current_app.logger.error(f"❌ Thread creation attempt {attempt + 1} failed: API returned {response.status_code}")
                
                if attempt < max_retries - 1:
                    current_app.logger.info(f"⏳ Retrying in {delay} seconds...")
                    time.sleep(delay)
                continue
                
        except requests.exceptions.Timeout as e:
            duration_ms = int((datetime.now() - attempt_start).total_seconds() * 1000)
            log_ai_activity(
                action="THREAD_CREATION_TIMEOUT",
                description=f"Timeout occurred while creating thread (attempt {attempt + 1})",
                contact_id=contact.id,
                error_details=str(e),
                duration_ms=duration_ms
            )
            current_app.logger.error(f"❌ Thread creation attempt {attempt + 1} timeout: {str(e)}")
            
            if attempt < max_retries - 1:
                current_app.logger.info(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            continue
            
        except requests.exceptions.ConnectionError as e:
            duration_ms = int((datetime.now() - attempt_start).total_seconds() * 1000)
            log_ai_activity(
                action="THREAD_CREATION_CONNECTION_ERROR",
                description=f"Connection error occurred while creating thread (attempt {attempt + 1})",
                contact_id=contact.id,
                error_details=str(e),
                duration_ms=duration_ms
            )
            current_app.logger.error(f"❌ Thread creation attempt {attempt + 1} connection error: {str(e)}")
            
            if attempt < max_retries - 1:
                current_app.logger.info(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            continue
            
        except Exception as e:
            duration_ms = int((datetime.now() - attempt_start).total_seconds() * 1000)
            log_ai_activity(
                action="THREAD_CREATION_EXCEPTION",
                description=f"Exception occurred while creating thread (attempt {attempt + 1})",
                contact_id=contact.id,
                error_details=str(e),
                duration_ms=duration_ms
            )
            current_app.logger.error(f"❌ Thread creation attempt {attempt + 1} exception: {str(e)}")
            
            if attempt < max_retries - 1:
                current_app.logger.info(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            continue

    # All retry attempts failed
    total_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    log_ai_activity(
        action="THREAD_CREATION_EXHAUSTED",
        description=f"All {max_retries} thread creation attempts failed for contact {contact.id}",
        contact_id=contact.id,
        error_details=f"Exhausted all {max_retries} retry attempts",
        duration_ms=total_duration_ms
    )
    current_app.logger.error(f"❌ CRITICAL: All {max_retries} thread creation attempts failed for contact {contact.id}")
    return None


def get_ai_response(thread_id, message):
    """Send message to AI assistant and get response"""
    start_time = datetime.now()
    
    if not thread_id:
        log_ai_activity(
            action="AI_RESPONSE_FAILED",
            description="Cannot get AI response: No thread ID provided",
            error_details="Missing thread_id parameter"
        )
        return None

    try:
        request_payload = {"thread_id": thread_id, "query": message}

        log_ai_activity(
            action="AI_REQUEST_SENT",
            description=f"Sending message to AI chat endpoint",
            thread_id=thread_id,
            request_message=message
        )

        response = requests.post(
            "https://extreme-game-truck-graelonbrown.replit.app/chat",
            headers={"Content-Type": "application/json"},
            json=request_payload,
            timeout=30)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        if response.status_code == 200:
            response_data = response.json()
            ai_response = response_data.get('response')
            
            log_ai_activity(
                action="AI_RESPONSE_SUCCESS",
                description=f"Successfully received AI response ({len(ai_response) if ai_response else 0} characters)",
                thread_id=thread_id,
                request_message=message,
                ai_response=ai_response,
                duration_ms=duration_ms
            )
            
            return ai_response
        else:
            log_ai_activity(
                action="AI_RESPONSE_FAILED",
                description=f"AI chat endpoint returned error status {response.status_code}",
                thread_id=thread_id,
                request_message=message,
                error_details=f"Status: {response.status_code}, Response: {response.text}",
                duration_ms=duration_ms
            )
            return None
    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        log_ai_activity(
            action="AI_REQUEST_EXCEPTION",
            description=f"Exception occurred while getting AI response",
            thread_id=thread_id,
            request_message=message,
            error_details=str(e),
            duration_ms=duration_ms
        )
        return None


def break_text_into_chunks(text, max_length=490):
    """Break text into chunks of specified length, preserving word boundaries when possible"""
    if len(text) <= max_length:
        return [text]

    chunks = []
    words = text.split(' ')
    current_chunk = ""

    for word in words:
        # If adding this word would exceed the limit
        if len(current_chunk) + len(word) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                # Word is longer than max_length, split it
                while len(word) > max_length:
                    chunks.append(word[:max_length])
                    word = word[max_length:]
                current_chunk = word
        else:
            if current_chunk:
                current_chunk += " " + word
            else:
                current_chunk = word

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def send_sms_via_twilio(user_id, to_number, message_text):
    """Send SMS via Twilio using user's settings"""
    try:
        UserSettings = current_app.UserSettings
        settings = UserSettings.query.filter_by(user_id=user_id).first()

        if not settings or not settings.account_sid or not settings.account_token or not settings.sms_number:
            current_app.logger.error(
                f"❌ ERROR: Twilio credentials not configured for user {user_id}")
            return False

        # Send SMS via Twilio
        twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.account_sid}/Messages.json"
        twilio_data = {
            'From': settings.sms_number,
            'To': to_number,
            'Body': message_text
        }

        response = requests.post(twilio_url,
                                 data=twilio_data,
                                 auth=HTTPBasicAuth(settings.account_sid,
                                                    settings.account_token),
                                 timeout=10)

        if response.status_code == 201:
            current_app.logger.info(f"✅ SMS sent successfully to {to_number}")
            return True
        else:
            current_app.logger.error(
                f"❌ ERROR: Failed to send SMS to {to_number}. Status Code: {response.status_code}. Response: {response.text}"
            )
            return False

    except Exception as e:
        current_app.logger.error(f"❌ EXCEPTION: Error sending SMS to {to_number}: {str(e)}")
        return False


def process_queued_messages(contact_id, from_number):
    """Process all queued messages for a contact after 30-second wait"""
    current_app.logger.info(f"🚀 === PROCESSING QUEUED MESSAGES START ===")
    current_app.logger.info(f"Contact ID: {contact_id}")
    current_app.logger.info(f"From Number: {from_number}")

    try:
        with queue_lock:
            # Get all queued messages for this contact
            queued_messages = message_queue.get(contact_id, [])
            if not queued_messages:
                current_app.logger.warning(f"⚠️ NO QUEUED MESSAGES for contact {contact_id}")
                return

            # Clear the queue for this contact
            del message_queue[contact_id]
            # Remove the timer reference
            if contact_id in contact_timers:
                del contact_timers[contact_id]

        current_app.logger.info(f"📋 PROCESSING {len(queued_messages)} QUEUED MESSAGES:")
        for i, msg in enumerate(queued_messages):
            current_app.logger.info(f"   Message {i+1}: '{msg['body']}' (ID: {msg.get('message_id')})")

        # Combine all messages into a single message
        combined_message = " ".join([msg['body'] for msg in queued_messages])
        current_app.logger.info(f"📝 COMBINED MESSAGE ({len(combined_message)} chars): '{combined_message}'")

        # Get the contact and thread information
        Contact = current_app.Contact
        contact = Contact.query.get(contact_id)

        if not contact:
            current_app.logger.error(f"❌ CRITICAL ERROR: Contact {contact_id} not found in database")
            return

        current_app.logger.info(f"👤 CONTACT FOUND: {contact.name} (ID: {contact.id}, Phone: {contact.phone_number})")
        current_app.logger.info(f"🧵 CURRENT THREAD ID: {contact.thread_id}")

        # Get or create thread ID for AI interaction with enhanced retry
        thread_id = get_or_create_thread_id(contact)

        if not thread_id:
            current_app.logger.error(f"❌ CRITICAL ERROR: Failed to get/create thread ID for contact {contact_id} after all retry attempts")
            current_app.logger.error(f"   Contact details: Name={contact.name}, Phone={contact.phone_number}")
            current_app.logger.error(f"   This contact will NOT receive an AI response")
            
            # Log this critical failure for monitoring
            log_ai_activity(
                action="THREAD_CREATION_CRITICAL_FAILURE",
                description=f"Contact {contact_id} will not receive AI response due to thread creation failure",
                contact_id=contact_id,
                error_details="All thread creation retry attempts exhausted"
            )
            return

        current_app.logger.info(f"✅ THREAD ID READY: {thread_id}")

        # Send combined message to /chat endpoint for AI processing
        ai_response = get_ai_response(thread_id, combined_message)

        # Only proceed if we got a valid AI response
        if not ai_response:
            current_app.logger.error(f"❌ CRITICAL ERROR: No AI response received for contact {contact_id}")
            current_app.logger.error(f"   Thread ID: {thread_id}")
            current_app.logger.error(f"   Combined Message: '{combined_message}'")
            current_app.logger.error(f"   This contact will NOT receive any reply")
            return

        current_app.logger.info(f"✅ AI RESPONSE RECEIVED ({len(ai_response)} chars): '{ai_response[:100]}{'...' if len(ai_response) > 100 else ''}'")

        # Break AI response into 490-character chunks
        response_chunks = break_text_into_chunks(ai_response, 490)
        current_app.logger.info(
            f"📝 Breaking AI response into {len(response_chunks)} chunks")

        # Send each chunk as a separate message
        all_chunks_sent = True
        user_id = contact.user_id

        for i, chunk in enumerate(response_chunks):
            # Create outgoing message record for each chunk
            chunk_message = current_app.Message(
                contact_id=contact.id,
                message_text=chunk,
                message_type='outgoing',
                ai_response=chunk,  # Store AI response
                created_at=datetime.utcnow())
            current_app.db.session.add(chunk_message)

            # Send chunk via Twilio
            chunk_sent = send_sms_via_twilio(user_id, from_number, chunk)

            if chunk_sent:
                current_app.logger.info(
                    f"✅ AI response chunk {i+1}/{len(response_chunks)} sent to {from_number}: '{chunk[:50]}{'...' if len(chunk) > 50 else ''}'"
                )
            else:
                current_app.logger.error(
                    f"❌ ERROR: Failed to send AI response chunk {i+1}/{len(response_chunks)} to {from_number}"
                )
                all_chunks_sent = False

            # Small delay between messages to avoid rate limiting
            time.sleep(2)

        if all_chunks_sent:
            current_app.logger.info(
                f"✅ All {len(response_chunks)} AI response chunks sent successfully to {from_number}"
            )
        else:
            current_app.logger.error(
                f"❌ ERROR: Some AI response chunks failed to send to {from_number}"
            )

        # Commit all outgoing message records
        try:
            current_app.db.session.commit()
            current_app.logger.info(
                f"💾 All outgoing AI response messages saved to database for contact {contact_id}"
            )
        except Exception as db_error:
            current_app.logger.error(
                f"❌ CRITICAL ERROR: Failed to save outgoing messages to database for contact {contact_id}: {str(db_error)}"
            )
            current_app.db.session.rollback()

    except Exception as e:
        current_app.logger.error(
            f"❌ UNHANDLED EXCEPTION: Error processing queued messages for contact {contact_id}: {str(e)}"
        )
        current_app.db.session.rollback()
    finally:
        current_app.logger.info(f"🏁 === PROCESSING QUEUED MESSAGES END ===")


def start_message_timer(contact_id, from_number):
    """Start a 30-second timer for message processing"""
    current_app.logger.info(
        f"⏳ Starting 30-second timer for contact {contact_id} (from {from_number})")

    # Get the current app instance to use in the timer thread
    app = current_app._get_current_object()

    def timer_callback():
        with app.app_context():
            app.logger.info(
                f"⏰ 30-second timer expired for contact {contact_id}, processing messages..."
            )
            process_queued_messages(contact_id, from_number)

    # Create and start timer
    timer = threading.Timer(30.0, timer_callback)  # 30 seconds
    timer.start()

    return timer


def find_contact_by_phone(phone_number):
    """Find contact by phone number with flexible matching"""
    Contact = current_app.Contact

    # Normalize to digits only
    normalized_digits = ''.join(ch for ch in phone_number if ch.isdigit())
    suffix = normalized_digits[-10:] if len(
        normalized_digits) >= 10 else normalized_digits

    current_app.logger.info(
        f"🔎 Searching for contact by phone: original='{phone_number}', normalized='{normalized_digits}', suffix='{suffix}'"
    )

    matching_contacts = []

    # 1. Try exact match first
    exact_match = Contact.query.filter_by(phone_number=phone_number).first()
    if exact_match:
        current_app.logger.info(f"   Found exact match: Contact ID {exact_match.id}")
        matching_contacts.append(exact_match)

    # 2. Try with normalized number
    if normalized_digits != phone_number:
        normalized_match = Contact.query.filter_by(
            phone_number=normalized_digits).first()
        if normalized_match and normalized_match not in matching_contacts:
            current_app.logger.info(f"   Found normalized match: Contact ID {normalized_match.id}")
            matching_contacts.append(normalized_match)

    # 3. Try with last 10 digits for US numbers
    if len(suffix) == 10:
        suffix_matches = Contact.query.filter(
            Contact.phone_number.endswith(suffix)).all()
        for match in suffix_matches:
            if match not in matching_contacts:
                current_app.logger.info(f"   Found suffix match: Contact ID {match.id}")
                matching_contacts.append(match)
    
    # 4. Try to find by thread_id (for widget contacts)
    if not matching_contacts:
        thread_match = Contact.query.filter_by(thread_id=phone_number).first()
        if thread_match:
            current_app.logger.info(f"   Found thread_id match: Contact ID {thread_match.id}")
            matching_contacts.append(thread_match)

    if matching_contacts:
        contact_ids_info = [f"ID {c.id} ({c.name or 'No Name'})" for c in matching_contacts]
        current_app.logger.info(
            f"ℹ️ Found {len(matching_contacts)} potential matching contacts: {', '.join(contact_ids_info)}"
        )

        # Use most recently updated contact if multiple matches
        if len(matching_contacts) > 1:
            Message = current_app.Message
            # Sort by last message time to prioritize active conversations
            matching_contacts.sort(key=lambda c: c.updated_at if c.updated_at else c.created_at, reverse=True)
            
            selected_contact = matching_contacts[0]
            current_app.logger.info(
                f"✅ Selected contact {selected_contact.id} ({selected_contact.name or 'No Name'}) based on recency."
            )
            return selected_contact
        else:
            selected_contact = matching_contacts[0]
            current_app.logger.info(
                f"✅ Selected contact {selected_contact.id} ({selected_contact.name or 'No Name'}) as the only match."
            )
            return selected_contact

    current_app.logger.info(f"   No matching contacts found for phone number '{phone_number}'")
    return None


@sms_bp.route('/api/sms/webhook', methods=['POST', 'GET'])
def handle_incoming_sms():
    """Handle incoming SMS from Twilio webhook"""
    start_time = datetime.now()
    
    try:
        # Log webhook activity with safe data handling
        safe_headers = {}
        safe_form_data = {}
        
        try:
            # Safely extract headers (limit to important ones)
            important_headers = ['Content-Type', 'User-Agent', 'X-Forwarded-For']
            for header in important_headers:
                if header in request.headers:
                    safe_headers[header] = request.headers[header][:200]  # Truncate long headers
            
            # Safely extract form data
            for key, value in request.form.items():
                safe_form_data[key] = str(value)[:500] if value else None  # Truncate long values
            
            log_webhook_activity(
                action="WEBHOOK_RECEIVED",
                description=f"SMS webhook called with method {request.method}",
                request_data={
                    "method": request.method,
                    "headers": safe_headers,
                    "form_data": safe_form_data,
                    "args": dict(request.args)
                }
            )
        except Exception as log_error:
            current_app.logger.error(f"Failed to log webhook activity: {str(log_error)}")
            # Continue processing even if logging fails

        # Handle GET requests (for Twilio validation)
        if request.method == 'GET':
            log_webhook_activity(
                action="WEBHOOK_VALIDATION",
                description="GET request received - Twilio validation"
            )
            return "<Response></Response>", 200

        # Get Twilio message data
        from_number = request.form.get('From')
        body = request.form.get('Body')
        to_number = request.form.get('To')
        message_sid = request.form.get('MessageSid')

        try:
            log_sms_activity(
                action="SMS_RECEIVED",
                description=f"Incoming SMS from {from_number}: {body[:50]}{'...' if len(body) > 50 else ''}",
                phone_number=from_number,
                message_text=body
            )
        except Exception as log_error:
            current_app.logger.error(f"Failed to log SMS activity: {str(log_error)}")
            # Continue processing even if logging fails

        if not from_number or not body:
            log_webhook_activity(
                action="WEBHOOK_VALIDATION_FAILED",
                description="Missing required fields in webhook data",
                error_details="Missing From or Body fields"
            )
            return "<Response></Response>", 400

        # Find contact by phone number
        Contact = current_app.Contact
        Message = current_app.Message
        User = current_app.User
        db = current_app.db

        contact = find_contact_by_phone(from_number)

        if contact:
            # Found existing contact
            user_id = contact.user_id
            current_app.logger.info(
                f"👤 Found matching contact: ID {contact.id}, Name: {contact.name}, Phone: {contact.phone_number}"
            )
        else:
            # Create new contact for unknown number
            current_app.logger.info(
                f"❓ Received SMS from unknown number {from_number}. Creating new contact."
            )

            # Find first user to assign the contact to
            first_user = User.query.first()
            if not first_user:
                current_app.logger.error("❌ ERROR: No users found in the system. Cannot assign new contact.")
                return "<Response></Response>", 500

            contact = Contact(user_id=first_user.id,
                              phone_number=from_number,
                              name=f"Contact {from_number[-4:]}")
            db.session.add(contact)
            db.session.flush()  # Get the contact ID
            user_id = first_user.id
            current_app.logger.info(
                f"✅ Created new contact: ID {contact.id}, Name: {contact.name}, User ID: {user_id}"
            )

        # Save incoming message to database immediately
        current_time = datetime.utcnow()
        incoming_message = Message(contact_id=contact.id,
                                   message_text=body,
                                   message_type='incoming',
                                   created_at=current_time)
        db.session.add(incoming_message)

        # Update contact's last activity
        contact.updated_at = current_time

        # Commit the incoming message to database immediately
        try:
            db.session.commit()
            current_app.logger.info(
                f"💾 Incoming message saved: Contact ID {contact.id}, Message: '{body[:50]}{'...' if len(body) > 50 else ''}'"
            )
        except Exception as db_error:
            current_app.logger.error(
                f"❌ ERROR: Failed to save incoming message to database: {str(db_error)}"
            )
            db.session.rollback()
            return "<Response></Response>", 500

        # Handle message queuing with 30-second wait logic
        with queue_lock:
            # Add message to queue for collective processing
            message_queue[contact.id].append({
                'body': body,
                'timestamp': current_time,
                'from_number': from_number,
                'message_id': incoming_message.id  # Track the database record
            })

            current_app.logger.info(
                f"➕ Added message to processing queue for Contact ID {contact.id}. Queue size: {len(message_queue[contact.id])}"
            )

            # Check if timer already exists for this contact
            if contact.id in contact_timers:
                # Timer already running, just add to queue
                current_app.logger.info(
                    f"ℹ️ Timer already running for Contact ID {contact.id}, message added to existing queue."
                )
            else:
                # Start new timer for this contact
                timer = start_message_timer(contact.id, from_number)
                contact_timers[contact.id] = timer
                current_app.logger.info(
                    f"▶️ Started new 30-second timer for Contact ID {contact.id}."
                )

        current_app.logger.info(f"✅ SMS webhook processing completed for {from_number}")
        return "<Response></Response>", 200

    except Exception as e:
        current_app.logger.error(f"❌ UNHANDLED EXCEPTION in webhook: {str(e)}")
        current_app.db.session.rollback()
        return "<Response></Response>", 500


@sms_bp.route('/api/messages', methods=['GET'])
@token_required
def get_messages(current_user):
    """Get messages for the current user with optional pagination"""
    try:
        db = current_app.db
        Contact = current_app.Contact
        Message = current_app.Message

        # Get pagination parameters
        limit = request.args.get('limit', type=int, default=50)  # Default 50 conversations
        offset = request.args.get('offset', type=int, default=0)
        
        # Get all contacts for the user
        contacts = Contact.query.filter_by(user_id=current_user.id).all()
        contact_ids = [contact.id for contact in contacts]

        if not contact_ids:
            current_app.logger.info(f"User {current_user.id} has no contacts.")
            response = jsonify({'conversations': []})
            response.headers['Cache-Control'] = 'private, max-age=30'
            return response, 200

        current_app.logger.info(f"Fetching messages for {len(contact_ids)} contacts of user {current_user.id} (limit: {limit}, offset: {offset}).")

        # Get messages with increased limit to ensure all conversation messages are fetched
        # limit * 200 ensures even contacts with hundreds of messages are fully loaded
        messages = Message.query.filter(Message.contact_id.in_(contact_ids))\
                              .order_by(Message.created_at.desc())\
                              .limit(limit * 200)\
                              .all()

        # Group messages by contact
        conversations = {}
        for message in messages:
            contact = next((c for c in contacts if c.id == message.contact_id),
                           None)
            if not contact:
                continue # Should not happen if contact_ids are correctly filtered

            # Use thread_id as identifier for widget contacts, phone_number for SMS contacts
            contact_identifier = contact.thread_id if contact.phone_number.startswith(
                'widget_') else contact.phone_number

            if contact_identifier not in conversations:
                # Determine contact type and display name
                if contact.phone_number.startswith('widget_'):
                    contact_display_name = contact.name or f"Widget Contact {contact.thread_id[-8:] if contact.thread_id else 'Unknown'}"
                    contact_phone_display = f"Widget Chat ({contact.thread_id[-8:] if contact.thread_id else 'Unknown'})"
                    contact_type = 'widget'
                else:
                    contact_display_name = contact.name or f"Contact {contact.phone_number[-4:]}"
                    contact_phone_display = contact.phone_number
                    contact_type = 'sms'

                conversations[contact_identifier] = {
                    'contact_name': contact_display_name,
                    'contact_phone': contact_phone_display,
                    'thread_id': contact.thread_id,
                    'contact_type': contact_type,
                    'last_message_time': message.created_at.isoformat(),
                    'messages': []
                }

            conversations[contact_identifier]['messages'].append({
                'id': message.id,
                'text': message.message_text,
                'type': message.message_type,
                'timestamp': message.created_at.isoformat()
            })

        # Convert to list and sort by last message time
        conversation_list = list(conversations.values())
        conversation_list.sort(key=lambda x: x['last_message_time'],
                               reverse=True)

        current_app.logger.info(f"Successfully fetched and grouped messages for {len(conversation_list)} conversations.")
        
        response = jsonify({'conversations': conversation_list})
        response.headers['Cache-Control'] = 'private, max-age=30'
        return response, 200

    except Exception as e:
        current_app.logger.error(f"❌ ERROR fetching messages: {str(e)}")
        return jsonify({'message': 'Failed to fetch messages'}), 500


@sms_bp.route('/api/contacts/preview', methods=['GET'])
@token_required
def get_contacts_preview(current_user):
    """Get lightweight contact preview with only last message (optimized for progressive loading)"""
    try:
        db = current_app.db
        Contact = current_app.Contact
        Message = current_app.Message
        
        # Get pagination parameters
        limit = request.args.get('limit', type=int, default=20)
        offset = request.args.get('offset', type=int, default=0)
        
        # Get total count of contacts with messages
        total_contacts = db.session.query(Contact.id)\
            .join(Message, Contact.id == Message.contact_id)\
            .filter(Contact.user_id == current_user.id)\
            .distinct()\
            .count()
        
        if total_contacts == 0:
            current_app.logger.info(f"User {current_user.id} has no contacts with messages.")
            return jsonify({'contacts': [], 'total': 0, 'offset': offset, 'limit': limit}), 200
        
        # Get contacts with their last message timestamp for sorting
        contacts_with_last_message = db.session.query(
            Contact.id,
            db.func.max(Message.created_at).label('last_message_time')
        ).join(Message, Contact.id == Message.contact_id)\
         .filter(Contact.user_id == current_user.id)\
         .group_by(Contact.id)\
         .order_by(db.func.max(Message.created_at).desc())\
         .limit(limit)\
         .offset(offset)\
         .all()
        
        current_app.logger.info(f"Fetching preview for batch: offset={offset}, limit={limit}, total={total_contacts}")
        
        contact_previews = []
        
        for contact_id, last_msg_time in contacts_with_last_message:
            contact = Contact.query.get(contact_id)
            
            # Get only the last message for this contact
            last_message = Message.query.filter_by(contact_id=contact.id)\
                                       .order_by(Message.created_at.desc())\
                                       .first()
            
            if not last_message:
                continue
            
            # Get message count for this contact
            message_count = Message.query.filter_by(contact_id=contact.id).count()
            
            # Determine contact type and display info
            if contact.phone_number.startswith('widget_'):
                contact_display_name = contact.name or f"Widget Contact {contact.thread_id[-8:] if contact.thread_id else 'Unknown'}"
                contact_phone_display = f"Widget Chat ({contact.thread_id[-8:] if contact.thread_id else 'Unknown'})"
                contact_type = 'widget'
                contact_id = contact.thread_id
            else:
                contact_display_name = contact.name or f"Contact {contact.phone_number[-4:]}"
                contact_phone_display = contact.phone_number
                contact_type = 'sms'
                contact_id = contact.phone_number
            
            contact_previews.append({
                'contact_name': contact_display_name,
                'contact_phone': contact_phone_display,
                'contact_id': contact_id,
                'thread_id': contact.thread_id,
                'contact_type': contact_type,
                'last_message': {
                    'text': last_message.message_text,
                    'type': last_message.message_type,
                    'timestamp': last_message.created_at.isoformat()
                },
                'last_message_time': last_message.created_at.isoformat(),
                'message_count': message_count
            })
        
        current_app.logger.info(f"Successfully fetched preview batch: {len(contact_previews)} contacts (offset={offset}, total={total_contacts})")
        
        response = jsonify({
            'contacts': contact_previews,
            'total': total_contacts,
            'offset': offset,
            'limit': limit,
            'hasMore': (offset + len(contact_previews)) < total_contacts
        })
        response.headers['Cache-Control'] = 'private, max-age=30'
        return response, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ ERROR fetching contact previews: {str(e)}")
        return jsonify({'message': 'Failed to fetch contact previews'}), 500


@sms_bp.route('/api/messages/<path:contact_phone>', methods=['GET'])
@token_required
def get_contact_messages(current_user, contact_phone):
    """Get all messages for a specific contact (on-demand loading)"""
    try:
        db = current_app.db
        Contact = current_app.Contact
        Message = current_app.Message
        
        current_app.logger.info(f"Fetching messages for contact {contact_phone} of user {current_user.id}")
        
        # Find contact by phone or thread_id
        contact = None
        
        # Try to find by phone number first
        contact = Contact.query.filter_by(
            user_id=current_user.id,
            phone_number=contact_phone
        ).first()
        
        # If not found, try to find by thread_id (for widget contacts)
        if not contact:
            contact = Contact.query.filter_by(
                user_id=current_user.id,
                thread_id=contact_phone
            ).first()
        
        if not contact:
            current_app.logger.warning(f"Contact {contact_phone} not found for user {current_user.id}")
            return jsonify({'message': 'Contact not found'}), 404
        
        # Get all messages for this contact
        messages = Message.query.filter_by(contact_id=contact.id)\
                               .order_by(Message.created_at.asc())\
                               .all()
        
        message_list = [{
            'id': msg.id,
            'text': msg.message_text,
            'type': msg.message_type,
            'timestamp': msg.created_at.isoformat()
        } for msg in messages]
        
        current_app.logger.info(f"Successfully fetched {len(message_list)} messages for contact {contact_phone}")
        
        response = jsonify({
            'contact_phone': contact_phone,
            'messages': message_list
        })
        response.headers['Cache-Control'] = 'private, max-age=30'
        return response, 200
        
    except Exception as e:
        current_app.logger.error(f"❌ ERROR fetching messages for contact {contact_phone}: {str(e)}")
        return jsonify({'message': 'Failed to fetch contact messages'}), 500


@sms_bp.route('/api/messages/send', methods=['POST'])
@token_required
def send_message(current_user):
    """Send a message to a contact"""
    try:
        data = request.json
        phone_number = data.get('phone_number')
        message_text = data.get('message')

        if not phone_number or not message_text:
            current_app.logger.error("❌ ERROR: Phone number and message text are required for sending.")
            return jsonify(
                {'message': 'Phone number and message are required'}), 400

        current_app.logger.info(f"Attempting to send manual message to {phone_number}: '{message_text[:50]}{'...' if len(message_text) > 50 else ''}'")

        # Find or create contact
        db = current_app.db
        Contact = current_app.Contact
        Message = current_app.Message

        contact = find_contact_by_phone(phone_number)

        if not contact:
            current_app.logger.info(f"Contact {phone_number} not found, creating new contact for user {current_user.id}.")
            contact = Contact(user_id=current_user.id,
                              phone_number=phone_number,
                              name=f"Contact {phone_number[-4:]}")
            db.session.add(contact)
            db.session.flush() # To get the contact.id immediately if needed later

        # Break message into 490-character chunks if needed
        message_chunks = break_text_into_chunks(message_text, 490)
        current_app.logger.info(
            f"Breaking manual message into {len(message_chunks)} chunks.")

        # Send each chunk as a separate message
        all_chunks_sent = True
        for i, chunk in enumerate(message_chunks):
            # Send chunk via Twilio
            chunk_sent = send_sms_via_twilio(current_user.id, phone_number, chunk)

            if chunk_sent:
                # Create outgoing message record
                send_time = datetime.utcnow()
                outgoing_message = Message(contact_id=contact.id,
                                           message_text=chunk,
                                           message_type='outgoing',
                                           created_at=send_time)
                db.session.add(outgoing_message)
                # Commit each message to ensure it's saved even if subsequent ones fail
                try:
                    db.session.commit()
                    current_app.logger.info(
                        f"✅ Manual message chunk {i+1}/{len(message_chunks)} saved and sent to {phone_number}: '{chunk[:50]}{'...' if len(chunk) > 50 else ''}'"
                    )
                except Exception as db_commit_error:
                    current_app.logger.error(f"❌ ERROR committing manual message chunk {i+1}: {str(db_commit_error)}")
                    db.session.rollback()
                    all_chunks_sent = False
                    # Optionally break here if even saving fails
            else:
                current_app.logger.error(
                    f"❌ ERROR: Failed to send manual message chunk {i+1}/{len(message_chunks)} to {phone_number}"
                )
                all_chunks_sent = False

            # Small delay between messages to avoid rate limiting
            time.sleep(2)

        if all_chunks_sent:
            current_app.logger.info(f"👍 All manual message chunks sent successfully to {phone_number}.")
            return jsonify({
                'message':
                f'Message sent successfully in {len(message_chunks)} part(s)'
            }), 200
        else:
            current_app.logger.warning(f"⚠️ Some manual message chunks failed to send to {phone_number}.")
            return jsonify({'message': 'Failed to send some message parts'}), 500
    except Exception as e:
        current_app.logger.error(f"❌ UNHANDLED EXCEPTION sending manual message: {str(e)}")
        return jsonify({'message': 'Failed to send message'}), 500