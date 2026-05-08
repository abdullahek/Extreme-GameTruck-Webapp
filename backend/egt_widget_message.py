from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit
from datetime import datetime

egt_widget_message_bp = Blueprint('egt_widget_message', __name__)

@egt_widget_message_bp.route('/api/egt_widget_message', methods=['POST'])
def handle_egt_widget_message():
    """Handle EGT widget message endpoint that receives thread_id, message and response"""
    try:
        data = request.json

        # Get required parameters
        thread_id = data.get('thread_id')
        message = data.get('message')
        response = data.get('response')

        # Validate required parameters
        if not thread_id or not message or not response:
            return jsonify({
                'error': 'Missing required parameters',
                'required': ['thread_id', 'message', 'response']
            }), 400

        # Log the received data
        current_app.logger.info(f"EGT Widget Message received:")
        current_app.logger.info(f"Thread ID: {thread_id}")
        current_app.logger.info(f"Message: {message}")
        current_app.logger.info(f"Response: {response}")

        # Get database models
        Contact = current_app.Contact
        Message = current_app.Message
        User = current_app.User
        db = current_app.db

        # Check if thread_id already exists in contacts
        existing_contact = Contact.query.filter_by(thread_id=thread_id).first()

        print(f"\n=== DATABASE OPERATION: THREAD LOOKUP ===")
        print(f"Searching for existing contact with thread_id: {thread_id}")

        if existing_contact:
            # Use existing contact
            contact = existing_contact
            current_app.logger.info(f"Found existing contact for thread_id {thread_id}: Contact ID {contact.id}")
            print(f"FOUND EXISTING CONTACT:")
            print(f"  - Contact ID: {contact.id}")
            print(f"  - Contact Name: {contact.name}")
            print(f"  - Phone Number: {contact.phone_number}")
            print(f"  - User ID: {contact.user_id}")
            print(f"  - Thread ID: {contact.thread_id}")
        else:
            # Create new contact with thread_id
            # Get first user to assign the contact to (you can modify this logic as needed)
            first_user = User.query.first()
            if not first_user:
                current_app.logger.error("No users found in system")
                print("ERROR: No users found in system")
                return jsonify({
                    'error': 'No users found in system'
                }), 500

            # Create new contact with thread_id
            # For widget contacts, we already have the thread_id from the request
            # But let's verify it's valid by checking if it exists in our system
            contact = Contact(
                user_id=first_user.id,
                phone_number=f"widget_{thread_id[-8:]}", # Create a unique identifier for widget contacts
                name=f"Widget Contact {thread_id[-8:]}",
                thread_id=thread_id
            )
            db.session.add(contact)
            db.session.flush()  # Get the contact ID
            current_app.logger.info(f"Created new contact for thread_id {thread_id}: Contact ID {contact.id}")
            print(f"CREATED NEW CONTACT:")
            print(f"  - Contact ID: {contact.id}")
            print(f"  - Contact Name: {contact.name}")
            print(f"  - Phone Number: {contact.phone_number}")
            print(f"  - User ID: {contact.user_id}")
            print(f"  - Thread ID: {contact.thread_id}")

        # Save the incoming message (user's message)
        current_time = datetime.utcnow()
        incoming_message = Message(
            contact_id=contact.id,
            message_text=message,
            message_type='incoming',
            created_at=current_time
        )
        db.session.add(incoming_message)
        db.session.flush()  # Get the message ID

        print(f"\n=== DATABASE OPERATION: SAVING INCOMING MESSAGE ===")
        print(f"Incoming Message Details:")
        print(f"  - Contact ID: {contact.id}")
        print(f"  - Message Text: {message}")
        print(f"  - Message Type: incoming")
        print(f"  - Timestamp: {current_time}")

        # Save the AI response as outgoing message
        outgoing_message = Message(
            contact_id=contact.id,
            message_text=response,
            message_type='outgoing',
            ai_response=response,  # Store the AI response in the ai_response field as well
            created_at=current_time
        )
        db.session.add(outgoing_message)
        db.session.flush()  # Get the message ID

        print(f"\n=== DATABASE OPERATION: SAVING OUTGOING MESSAGE ===")
        print(f"Outgoing Message Details:")
        print(f"  - Contact ID: {contact.id}")
        print(f"  - Message Text: {response}")
        print(f"  - Message Type: outgoing")
        print(f"  - AI Response: {response}")
        print(f"  - Timestamp: {current_time}")

        # Update contact's last activity
        contact.updated_at = current_time

        print(f"\n=== DATABASE OPERATION: UPDATING CONTACT ===")
        print(f"Updated contact last activity to: {current_time}")

        # Commit all changes to database
        db.session.commit()

        # Emit WebSocket events for real-time updates
        try:
            from flask_socketio import emit

            # Emit for incoming message
            incoming_event = {
                'id': incoming_message.id,
                'text': message,
                'type': 'incoming',
                'timestamp': incoming_message.created_at.isoformat()
            }
            current_app.socketio.emit('new-message', {
                'phone': thread_id, 
                'message': incoming_event
            }, room=thread_id)

            # Emit for outgoing AI response
            outgoing_event = {
                'id': outgoing_message.id,
                'text': response,
                'type': 'ai-response',
                'timestamp': outgoing_message.created_at.isoformat()
            }
            current_app.socketio.emit('new-message', {
                'phone': thread_id, 
                'message': outgoing_event
            }, room=thread_id)

            print(f"WebSocket events emitted for room: {thread_id}")

        except Exception as ws_error:
            print(f"WebSocket emission error: {str(ws_error)}")

        # Verification - Let's check what we actually saved
        print(f"\n=== DATABASE VERIFICATION ===")
        contact_check = Contact.query.filter_by(thread_id=thread_id).first()
        if contact_check:
            messages_count = Message.query.filter_by(contact_id=contact_check.id).count()
            print(f"Verification successful:")
            print(f"  - Contact exists: {contact_check.name} (ID: {contact_check.id})")
            print(f"  - Total messages for this contact: {messages_count}")
        else:
            print("Verification failed: Contact not found")

        # Return success response
        return jsonify({
            'success': True,
            'message': 'EGT widget message saved successfully',
            'data': {
                'thread_id': thread_id,
                'contact_id': contact.id,
                'contact_name': contact.name,
                'original_message': message,
                'ai_response': response,
                'timestamp': current_time.isoformat(),
                'status': 'saved_to_database'
            }
        }), 200

    except Exception as e:
        # Rollback in case of error
        current_app.db.session.rollback()
        current_app.logger.error(f"Error processing EGT widget message: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500