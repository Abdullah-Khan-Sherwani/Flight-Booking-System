# Flight Booking System - Modularization Guide

## Overview

This document describes the modular architecture implemented for the Flask-based Flight Booking System. The original monolithic `app.py` (2,309 lines) has been split into 6 logical modules using Flask Blueprints.

## File Structure

```
Flight-Booking-System/
├── app.py                 # Original monolithic file (kept as backup)
├── app_modular.py         # New entry point with Blueprint registration
├── utils.py               # Shared utility functions
├── db.py                  # Database connection (unchanged)
├── config.py              # Configuration (unchanged)
├── ticket_generator.py    # Ticket generation (unchanged)
├── routes/
│   ├── __init__.py       # Package initialization
│   ├── auth.py           # Authentication routes (~250 lines)
│   ├── flights.py        # Flight search routes (~400 lines)
│   ├── booking.py        # Booking flow routes (~650 lines)
│   ├── management.py     # Booking management routes (~450 lines)
│   └── debug.py          # Debug routes (~100 lines)
└── templates/            # HTML templates (unchanged)
```

## Module Breakdown

### 1. `app_modular.py` - Entry Point (~55 lines)
The main Flask application file that:
- Creates the Flask app instance
- Sets the secret key for sessions
- Registers all Blueprint modules
- Defines error handlers (404, 500)

### 2. `utils.py` - Shared Utilities (~90 lines)
Contains helper functions used across multiple modules:
- `validate_password()` - Password strength validation
- `hash_password()` - SHA-256 password hashing
- `validate_cnic()` - CNIC format validation
- `generate_sequential_id()` - Unique ID generation
- `get_class_name()` - Travel class code mapping
- `clear_booking_session()` - Session cleanup
- `clear_reschedule_session()` - Reschedule session cleanup

### 3. `routes/auth.py` - Authentication (~250 lines)
Handles user authentication and account management:

| Route | Method | Function | Description |
|-------|--------|----------|-------------|
| `/` | GET | `home()` | Redirect to login/dashboard |
| `/login` | GET, POST | `login()` | User login |
| `/signup` | GET, POST | `signup()` | User registration |
| `/dashboard` | GET | `dashboard()` | Main dashboard |
| `/index` | GET | `index()` | Alternative dashboard |
| `/logout` | GET | `logout()` | Clear session |
| `/account-info` | GET | `account_info()` | User profile |
| `/contact` | GET | `contact()` | Contact page |
| `/destination` | GET | `destination()` | Destinations page |

### 4. `routes/flights.py` - Flight Search (~400 lines)
Handles flight search and pricing:

| Route | Method | Function | Description |
|-------|--------|----------|-------------|
| `/pricing` | GET, POST | `pricing()` | Flight pricing with filters |
| `/search-flights` | GET | `search_flights_get()` | Search from pricing page |
| `/search-flights` | POST | `search_flights()` | Main flight search |
| `/select-flight/<id>` | GET | `select_flight()` | Select outbound flight |
| `/return-flight-search` | GET, POST | `return_flight_search()` | Search return flights |
| `/select-return-flight/<id>` | GET | `select_return_flight()` | Select return flight |
| `/get-seat-status/<id>` | GET | `get_seat_status()` | AJAX seat availability |

### 5. `routes/booking.py` - Booking Flow (~650 lines)
Handles the complete booking process:

| Route | Method | Function | Description |
|-------|--------|----------|-------------|
| `/seat-selection` | GET | `seat_selection()` | Seat selection page |
| `/passenger-info` | GET, POST | `passenger_info()` | Passenger details form |
| `/process-booking` | POST | `process_booking()` | Create booking |
| `/booking-confirmation` | GET | `booking_confirmation()` | Confirmation page |
| `/download-tickets/<id>` | GET | `download_tickets()` | Download tickets ZIP |
| `/view-ticket/<id>` | GET | `view_ticket()` | View single ticket |

### 6. `routes/management.py` - Booking Management (~450 lines)
Handles booking modifications:

| Route | Method | Function | Description |
|-------|--------|----------|-------------|
| `/manage-bookings` | GET | `manage_bookings()` | Management landing |
| `/verify-booking` | POST | `verify_booking()` | Verify booking |
| `/process-booking-action` | POST | `process_booking_action()` | Cancel/reschedule |
| `/booking-actions` | GET | `booking_actions()` | Action selection |
| `/search-reschedule-flights` | POST | `search_reschedule_flights()` | Search for reschedule |
| `/select-reschedule-flight/<id>` | GET | `select_reschedule_flight()` | Select new flight |
| `/complete-reschedule` | POST | `complete_reschedule()` | Complete reschedule |

Helper functions:
- `cancel_reservations()` - Process cancellation
- `redirect_to_reschedule()` - Initialize reschedule flow

### 7. `routes/debug.py` - Debug Routes (~100 lines)
Development-only routes for debugging:

| Route | Method | Function | Description |
|-------|--------|----------|-------------|
| `/debug-schema` | GET | `debug_schema()` | View DB schema |
| `/debug-constraint` | GET | `debug_constraint()` | Debug constraints |
| `/debug-app-user` | GET | `debug_app_user()` | Debug user table |

**Note:** Remove or disable this module in production.

## How to Switch to Modular Version

### Option 1: Rename Files (Recommended)
```bash
# Backup original
mv app.py app_original.py

# Use modular version
mv app_modular.py app.py
```

### Option 2: Direct Run
```bash
python app_modular.py
```

## Key Design Decisions

### 1. No URL Prefixes
All blueprints are registered without URL prefixes to maintain backward compatibility with existing URLs and templates.

### 2. Session Sharing
All modules share the same Flask session object, allowing seamless data flow between:
- Flight search → Booking
- Booking → Management (reschedule)

### 3. Error Handlers
Centralized error handling in `app_modular.py`:
- 404 - Page not found
- 500 - Internal server error
- Generic exception handler

### 4. Debug Routes Separation
Debug routes are isolated in `routes/debug.py` for easy removal in production.

## Dependencies Between Modules

```
auth.py ─────────┐
                 │
flights.py ──────┼──→ booking.py ──→ management.py
                 │          │
utils.py ────────┴──────────┴─────────────────────→
                 │
db.py ───────────┴────────────────────────────────→
```

## Production Checklist

1. [ ] Remove `routes/debug.py` import and registration
2. [ ] Set a secure `app.secret_key`
3. [ ] Set `debug=False` in `app.run()`
4. [ ] Configure proper logging
5. [ ] Use environment variables for sensitive data

## Reverting to Original

To revert to the original monolithic version:
```bash
# If using Option 1
mv app.py app_modular.py
mv app_original.py app.py
```

The original `app.py` remains unchanged and fully functional.

## Testing

After switching to the modular version, test these critical flows:

1. **Authentication Flow**
   - [ ] Login with valid credentials
   - [ ] Signup new user
   - [ ] Logout

2. **Flight Search Flow**
   - [ ] Search one-way flights
   - [ ] Search round-trip flights
   - [ ] Filter by date/city

3. **Booking Flow**
   - [ ] Select flight → Seat selection → Passenger info → Process booking
   - [ ] Download tickets
   - [ ] View confirmation

4. **Management Flow**
   - [ ] Verify booking
   - [ ] Cancel reservation
   - [ ] Reschedule flight

## Line Count Summary

| Module | Lines | Percentage |
|--------|-------|------------|
| `app_modular.py` | 55 | 2.4% |
| `utils.py` | 90 | 3.9% |
| `routes/auth.py` | 250 | 10.8% |
| `routes/flights.py` | 400 | 17.3% |
| `routes/booking.py` | 650 | 28.2% |
| `routes/management.py` | 450 | 19.5% |
| `routes/debug.py` | 100 | 4.3% |
| `routes/__init__.py` | 10 | 0.4% |
| **Total** | **~2,005** | **86.8%** |

*Note: ~300 lines saved through code deduplication in utils.py*

## Benefits of Modularization

1. **Maintainability** - Easier to find and fix bugs
2. **Collaboration** - Multiple developers can work on different modules
3. **Testing** - Modules can be tested independently
4. **Readability** - Smaller files are easier to understand
5. **Scalability** - New features can be added as new modules
