
import json
from datetime import datetime
from flask import request, current_app


def truncate_string(value, max_length):
    """Safely truncate string to max length"""
    if value is None:
        return None
    str_value = str(value)
    if len(str_value) <= max_length:
        return str_value
    return str_value[:max_length-3] + "..."


def log_backend_activity(
    log_level="INFO",
    log_category="GENERAL",
    action="",
    description="",
    contact_id=None,
    user_id=None,
    phone_number=None,
    thread_id=None,
    request_data=None,
    response_data=None,
    error_details=None,
    duration_ms=None
):
    """
    Comprehensive backend logging function
    
    Args:
        log_level: 'INFO', 'ERROR', 'WARNING', 'DEBUG'
        log_category: 'SMS', 'AUTH', 'DATABASE', 'AI_RESPONSE', 'WEBHOOK', etc.
        action: Specific action being performed
        description: Detailed description of the activity
        contact_id: Associated contact ID if applicable
        user_id: Associated user ID if applicable
        phone_number: Phone number involved in the activity
        thread_id: AI thread ID if applicable
        request_data: Request data as dict (will be converted to JSON)
        response_data: Response data as dict (will be converted to JSON)
        error_details: Error details if any
        duration_ms: Duration in milliseconds
    """
    try:
        BackendLog = current_app.BackendLog
        db = current_app.db
        
        # Get request info if available
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            user_agent = request.headers.get('User-Agent')
        
        # Convert data to JSON strings with size limits
        request_json = None
        if request_data:
            try:
                request_json = json.dumps(request_data)
                # Truncate if too long (Text field limit is typically around 65535 chars)
                request_json = truncate_string(request_json, 10000)
            except (TypeError, ValueError):
                request_json = truncate_string(str(request_data), 10000)
        
        response_json = None
        if response_data:
            try:
                response_json = json.dumps(response_data)
                response_json = truncate_string(response_json, 10000)
            except (TypeError, ValueError):
                response_json = truncate_string(str(response_data), 10000)
        
        # Create log entry with truncated fields
        log_entry = BackendLog(
            contact_id=contact_id,
            user_id=truncate_string(user_id, 36),  # UUID length
            log_level=truncate_string(log_level, 10),
            log_category=truncate_string(log_category, 50),
            action=truncate_string(action, 100),
            description=truncate_string(description, 1000),  # Text field, but keep reasonable
            phone_number=truncate_string(phone_number, 20),
            thread_id=truncate_string(thread_id, 100),
            request_data=request_json,
            response_data=response_json,
            error_details=truncate_string(error_details, 5000),
            duration_ms=duration_ms,
            ip_address=truncate_string(ip_address, 45),  # IPv6 max length
            user_agent=truncate_string(user_agent, 500),
            created_at=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        # Also log to console for immediate visibility
        log_message = f"[{log_level}] [{log_category}] {action}: {description}"
        if contact_id:
            log_message += f" | Contact ID: {contact_id}"
        if phone_number:
            log_message += f" | Phone: {phone_number}"
        if thread_id:
            log_message += f" | Thread: {thread_id}"
        
        current_app.logger.info(log_message)
        
    except Exception as e:
        # Fallback logging if database logging fails
        current_app.logger.error(f"Failed to log backend activity: {str(e)}")
        current_app.logger.error(f"Original log: {log_level} - {log_category} - {action} - {description}")


def log_sms_activity(action, description, contact_id=None, phone_number=None, message_text=None, thread_id=None, error_details=None, duration_ms=None):
    """Specific logging function for SMS activities"""
    log_backend_activity(
        log_level="ERROR" if error_details else "INFO",
        log_category="SMS",
        action=action,
        description=description,
        contact_id=contact_id,
        phone_number=phone_number,
        thread_id=thread_id,
        request_data={"message_text": message_text} if message_text else None,
        error_details=error_details,
        duration_ms=duration_ms
    )


def log_ai_activity(action, description, contact_id=None, thread_id=None, request_message=None, ai_response=None, error_details=None, duration_ms=None):
    """Specific logging function for AI activities"""
    log_backend_activity(
        log_level="ERROR" if error_details else "INFO",
        log_category="AI_RESPONSE",
        action=action,
        description=description,
        contact_id=contact_id,
        thread_id=thread_id,
        request_data={"message": request_message} if request_message else None,
        response_data={"ai_response": ai_response} if ai_response else None,
        error_details=error_details,
        duration_ms=duration_ms
    )


def log_database_activity(action, description, contact_id=None, user_id=None, error_details=None):
    """Specific logging function for database activities"""
    log_backend_activity(
        log_level="ERROR" if error_details else "INFO",
        log_category="DATABASE",
        action=action,
        description=description,
        contact_id=contact_id,
        user_id=user_id,
        error_details=error_details
    )


def log_webhook_activity(action, description, phone_number=None, request_data=None, error_details=None):
    """Specific logging function for webhook activities"""
    log_backend_activity(
        log_level="ERROR" if error_details else "INFO",
        log_category="WEBHOOK",
        action=action,
        description=description,
        phone_number=phone_number,
        request_data=request_data,
        error_details=error_details
    )


def log_auth_activity(action, description, user_id=None, error_details=None):
    """Specific logging function for authentication activities"""
    log_backend_activity(
        log_level="ERROR" if error_details else "INFO",
        log_category="AUTH",
        action=action,
        description=description,
        user_id=user_id,
        error_details=error_details
    )
