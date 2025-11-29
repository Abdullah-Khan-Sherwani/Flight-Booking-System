# utils.py
# Shared utility functions for the Flight Booking System

import hashlib
import re
from datetime import datetime


def validate_password(password):
    """Validate password meets requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"


def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_cnic(cnic):
    """Validate CNIC format (XXXXX-XXXXXXX-X)"""
    if not cnic:
        return False
    pattern = r'^\d{5}-\d{7}-\d{1}$'
    return re.match(pattern, cnic) is not None


def generate_sequential_id(prefix, table_name, id_column, cursor):
    """Generate a sequential ID that doesn't exist in the database"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    base_id = f"{prefix}{timestamp}"
    test_id = base_id
    counter = 1
    
    # Check if the base ID exists
    cursor.execute(f"SELECT 1 FROM {table_name} WHERE {id_column} = :id", id=test_id)
    while cursor.fetchone():
        # If exists, try with counter suffix
        test_id = f"{base_id}_{counter}"
        counter += 1
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE {id_column} = :id", id=test_id)
    
    print(f"DEBUG - Generated {prefix} ID: {test_id}")
    return test_id


def get_class_name(class_code):
    """Map travel class codes to full names"""
    class_names = {
        'ECO': 'Economy',
        'BUS': 'Business', 
        'FIR': 'First Class'
    }
    return class_names.get(class_code, class_code)


def clear_booking_session(session):
    """Clear all booking-related session data"""
    keys_to_clear = [
        'selected_outbound_seats', 'selected_return_seats',
        'selected_outbound_flight', 'selected_return_flight',
        'search_travel_class', 'search_passengers', 'search_trip_type',
        'travel_class', 'passengers', 'trip_type'
    ]
    for key in keys_to_clear:
        session.pop(key, None)


def clear_reschedule_session(session):
    """Helper function to clear all reschedule and booking session data"""
    keys_to_clear = [
        'reschedule_reservation_id', 'reschedule_new_flight',
        'reschedule_context', 'reschedule_original_booking', 'is_reschedule',
        'selected_outbound_seats', 'selected_return_seats',
        'selected_outbound_flight', 'selected_return_flight',
        'search_travel_class', 'search_passengers', 'search_trip_type',
        'travel_class', 'passengers', 'trip_type'
    ]
    for key in keys_to_clear:
        session.pop(key, None)
