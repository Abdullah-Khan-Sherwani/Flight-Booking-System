# app.py
"""
IAT Airlines Flight Booking System - Main Application

This application uses the following Oracle database objects from database-3NF.sql:

=== SEQUENCES (Auto-generated IDs) ===
- Passenger_Seq: Generates unique Passenger_ID values
- Reservation_Seq: Generates ticket numbers in format IAT-YYYYMMDD-NNNNNN
- Booking_Seq: Used by Generate_PNR function for booking IDs

=== FUNCTIONS ===
- Generate_PNR(): Generates random 6-character alphanumeric booking ID (used by TRG_Generate_Booking_PNR)
- FN_Get_Infant_Type(booking_id, instance_id, passenger_id): Determines LAP_INFANT vs SEATED_INFANT
- FN_Get_Infant_Price(instance_id, infant_type, class_id): Calculates infant pricing (0 or 50%)
- FN_Calculate_Refund(instance_id, price_charged): Calculates refund based on hours until departure

=== STORED PROCEDURES ===
- USP_Make_Reservation: Smart booking with auto-seat assignment (available but using direct inserts)
- USP_Delete_User_Account: Cascading delete for user account and all related data
- USP_Cancel_Reservation: Cancel reservation with automatic refund calculation

=== TRIGGERS (Automatically fired) ===
- TRG_Generate_Booking_PNR: Auto-generates 6-char booking ID on INSERT into Booking
- TRG_Validate_Seat_Exists: Validates seat exists on aircraft before reservation
- TRG_Infant_Booking_Rules: Enforces infant booking rules and auto-calculates prices
- TRG_Auto_Cancel_Booking: Updates Booking.Booking_Status when all reservations cancelled
- TRG_Auto_Log_Booking_Cancellation: Logs to Cancellation_Log when booking cancelled
- TRG_Auto_Reciprocal_Family: Creates reciprocal family relationship on ACCEPT

=== VIEWS ===
- View_Flight_Availability: Shows total capacity, booked seats, and remaining seats per flight
- View_Booking_Infant_Summary: Summarizes bookings with adult/lap-infant/seated-infant counts
- View_Past_Passengers: Returns passengers previously booked by a lead user with trip history
"""

from flask import Flask, render_template, request, redirect, session, jsonify, url_for, send_file
from db import get_connection
from datetime import datetime, timedelta
import json
import re
import os
import zipfile
from io import BytesIO
from ticket_generator import TicketGenerator
import hashlib
import secrets

# Import Oracle driver for stored procedure calls
try:
    import oracledb
except ImportError:
    import cx_Oracle as oracledb

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for sessions

# Password validation function
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

# Hash password function
def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


@app.route('/')
def home():
    # Allow both logged-in users and guests to access the main page
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if user exists and password matches
            cursor.execute("""
                SELECT User_ID, Email, Password_Hash, Phone_Number 
                FROM App_User 
                WHERE Email = :email
            """, email=email)
            
            user = cursor.fetchone()
            
            if user and user[2] == hash_password(password):
                # Login successful
                session['user_id'] = user[0]
                session['user_email'] = user[1]
                session['user_phone'] = user[3]
                
                # Get user's first name for display
                cursor.execute("""
                    SELECT First_Name FROM Passenger 
                    WHERE Linked_User_ID = :user_id
                """, user_id=user[0])
                
                passenger = cursor.fetchone()
                if passenger:
                    session['user_first_name'] = passenger[0]
                else:
                    # Fall back to email prefix if no passenger profile exists
                    session['user_first_name'] = user[1].split('@')[0].capitalize()
                
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error="Invalid email or password")
                
        except Exception as e:
            print("Login error:", e)
            return render_template('login.html', error="Login failed. Please try again.")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone_number = request.form.get('phone_number')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        title = request.form.get('title', 'MR')
        
        print(f"DEBUG - Signup attempt for email: {email}")

        # Validate passwords match
        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match")
        
        # Validate password strength
        is_valid, message = validate_password(password)
        if not is_valid:
            return render_template('signup.html', error=message)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if email already exists
            cursor.execute("SELECT User_ID FROM App_User WHERE LOWER(Email) = LOWER(:email)", email=email)
            if cursor.fetchone():
                return render_template('signup.html', error="Email already exists. Please use a different email or try logging in.")
            
            # Get next available User_ID manually (workaround for identity issues)
            cursor.execute("SELECT COALESCE(MAX(User_ID), 0) + 1 FROM App_User")
            next_user_id = cursor.fetchone()[0]
            
            print(f"DEBUG - Next User_ID: {next_user_id}")
            
            # Create user account with explicit User_ID
            password_hash = hash_password(password)
            
            cursor.execute("""
                INSERT INTO App_User (User_ID, Email, Password_Hash, Phone_Number)
                VALUES (:user_id, :email, :password_hash, :phone_number)
            """, 
            user_id=next_user_id,
            email=email, 
            password_hash=password_hash, 
            phone_number=phone_number)
            
            print(f"DEBUG - User account created with ID: {next_user_id}")
            
            # Create passenger profile linked to user
            cursor.execute("""
                INSERT INTO Passenger 
                (Linked_User_ID, First_Name, Last_Name, Date_Of_Birth, Gender, Title)
                VALUES (:user_id, :first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :title)
            """, 
            user_id=next_user_id,
            first_name=first_name,
            last_name=last_name,
            dob=date_of_birth,
            gender=gender,
            title=title)
            
            conn.commit()
            print(f"DEBUG - Signup successful for user: {next_user_id}")
            
            # Auto-login after signup
            session['user_id'] = next_user_id
            session['user_email'] = email
            session['user_phone'] = phone_number
            session['user_first_name'] = first_name
            
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            conn.rollback()
            print(f"SIGNUP ERROR: {e}")
            print(f"Error type: {type(e).__name__}")
            
            # More specific error handling
            if "unique constraint" in str(e).lower():
                if "SYS_C009170" in str(e):
                    return render_template('signup.html', error="System error: User ID conflict. Please try again with a different email.")
                else:
                    return render_template('signup.html', error="This email address is already registered.")
            elif "ORA-00001" in str(e):
                return render_template('signup.html', error="Duplicate entry detected. Please try again with a different email.")
            else:
                return render_template('signup.html', error=f"Registration failed: {str(e)}")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('signup.html')


@app.route('/guest-booking')
def guest_booking():
    """Redirect guest users to the main booking page"""
    # Clear any existing user session to ensure guest mode
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_phone', None)
    session.pop('user_first_name', None)
    
    # Set a flag to indicate guest booking
    session['is_guest'] = True
    
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    # Allow both logged-in users and guests to access dashboard
    if 'user_id' not in session and not session.get('is_guest'):
        return redirect(url_for('login'))
    return render_template('index.html')

# Update the home route to redirect to dashboard if logged in
@app.route('/index')
def index():
    # No login required - accessible to both guests and logged-in users
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/my-trips')
def my_trips():
    """Display user's travel history page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('my_trips.html')

@app.route('/account-info')
def account_info():
    """Display account information page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get user account details
        cursor.execute("""
            SELECT u.User_ID, u.Email, u.Phone_Number, u.Created_At,
                   p.First_Name, p.Last_Name, p.Date_Of_Birth, p.Gender, 
                   p.Title, p.Passport_Num
            FROM App_User u
            LEFT JOIN Passenger p ON u.User_ID = p.Linked_User_ID
            WHERE u.User_ID = :user_id
        """, user_id=session['user_id'])
        
        user_data = cursor.fetchone()
        
        if not user_data:
            return render_template('error.html', error="User account not found")
        
        # Get booking history count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Booking 
            WHERE Lead_User_ID = :user_id
        """, user_id=session['user_id'])
        booking_count = cursor.fetchone()[0]
        
        # Get upcoming flights (count distinct flight instances, not reservations)
        cursor.execute("""
            SELECT COUNT(DISTINCT fi.Instance_ID) 
            FROM Reservation r
            JOIN Booking b ON r.Booking_ID = b.Booking_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            WHERE b.Lead_User_ID = :user_id
            AND fi.Departure_Time > SYSTIMESTAMP
            AND b.Booking_Status = 'CONFIRMED'
        """, user_id=session['user_id'])
        upcoming_flights = cursor.fetchone()[0]
        
        # Format user data for template
        account_info = {
            'user_id': user_data[0],
            'email': user_data[1],
            'phone_number': user_data[2],
            'created_at': user_data[3].strftime('%B %d, %Y') if user_data[3] else 'N/A',
            'first_name': user_data[4],
            'last_name': user_data[5],
            'date_of_birth': user_data[6].strftime('%B %d, %Y') if user_data[6] else 'N/A',
            'gender': user_data[7],
            'title': user_data[8],
            'passport_number': user_data[9] or 'Not provided',
            'booking_count': booking_count,
            'upcoming_flights': upcoming_flights
        }
        
        return render_template('account_info.html', account_info=account_info)
        
    except Exception as e:
        print("Error loading account info:", e)
        return render_template('error.html', error="Error loading account information")
    finally:
        cursor.close()
        conn.close()

@app.route('/api/delete-account', methods=['POST'])
def delete_account():
    """
    Permanently delete user account and all associated data.
    Uses the USP_Delete_User_Account stored procedure for cascading delete.
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    
    # Get confirmation from request
    data = request.get_json()
    if not data or not data.get('confirm'):
        return jsonify({'success': False, 'error': 'Deletion not confirmed'}), 400
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Call the stored procedure for cascading delete
        rows_deleted = cursor.var(int)
        cursor.callproc('USP_Delete_User_Account', [user_id, rows_deleted])
        
        # Clear session after successful deletion
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Account deleted successfully',
            'rows_deleted': rows_deleted.getvalue()
        })
        
    except Exception as e:
        conn.rollback()
        error_msg = str(e)
        print(f"Error deleting account: {error_msg}")
        
        # Handle specific Oracle errors
        if 'ORA-20100' in error_msg:
            return jsonify({'success': False, 'error': 'User account not found'}), 404
        
        return jsonify({'success': False, 'error': 'Failed to delete account. Please try again.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/destination')
def destination():
    return render_template('destination.html')

@app.route('/pricing', methods=['GET', 'POST'])
def pricing():
    """Display flight pricing with filtering options"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get filter parameters
        departure_city = request.form.get('departure_city') or request.args.get('departure_city', '')
        arrival_city = request.form.get('arrival_city') or request.args.get('arrival_city', '')
        travel_date = request.form.get('travel_date') or request.args.get('travel_date', '')
        
        # Get all available cities for dropdowns
        cursor.execute("""
            SELECT DISTINCT a.Airport_ID, c.City_Name, a.Airport_Name
            FROM Airport a
            JOIN Zip_Master z ON a.Zipcode = z.Zipcode
            JOIN City c ON z.City_ID = c.City_ID
            ORDER BY c.City_Name
        """)
        cities = cursor.fetchall()
        
        # Build query for flight pricing
        query = """
            SELECT 
                fi.Instance_ID,
                fr.Source_Airport,
                fr.Dest_Airport,
                TO_CHAR(fi.Departure_Time, 'YYYY-MM-DD HH24:MI') as Departure_Time,
                TO_CHAR(fi.Arrival_Time, 'YYYY-MM-DD HH24:MI') as Arrival_Time,
                a1.Airport_Name as Source_Airport_Name,
                a2.Airport_Name as Dest_Airport_Name,
                c1.City_Name as Source_City,
                c2.City_Name as Dest_City,
                fi.Model_ID,
                -- Economy Price
                (SELECT Base_Price FROM Route_Pricing 
                 WHERE Route_ID = fr.Route_ID AND Class_ID = 'ECO'
                 AND SYSDATE BETWEEN Valid_From AND Valid_To
                 AND ROWNUM = 1) as Eco_Price,
                -- Business Price
                (SELECT Base_Price FROM Route_Pricing 
                 WHERE Route_ID = fr.Route_ID AND Class_ID = 'BUS'
                 AND SYSDATE BETWEEN Valid_From AND Valid_To
                 AND ROWNUM = 1) as Bus_Price,
                -- First Class Price
                (SELECT Base_Price FROM Route_Pricing 
                 WHERE Route_ID = fr.Route_ID AND Class_ID = 'FIR'
                 AND SYSDATE BETWEEN Valid_From AND Valid_To
                 AND ROWNUM = 1) as First_Price,
                -- Available seats by class
                (SELECT COUNT(*) FROM Aircraft_Seat_Map asm
                 JOIN Aircraft_Row_Class arc ON asm.Model_ID = arc.Model_ID AND asm.Row_Number = arc.Row_Number
                 WHERE asm.Model_ID = fi.Model_ID AND arc.Class_ID = 'ECO') - 
                (SELECT COUNT(*) FROM Reservation r 
                 WHERE r.Instance_ID = fi.Instance_ID 
                 AND EXISTS (SELECT 1 FROM Aircraft_Row_Class arc2 
                           WHERE arc2.Model_ID = fi.Model_ID 
                           AND arc2.Row_Number = r.Row_Number 
                           AND arc2.Class_ID = 'ECO')) as Eco_Seats_Available,
                (SELECT COUNT(*) FROM Aircraft_Seat_Map asm
                 JOIN Aircraft_Row_Class arc ON asm.Model_ID = arc.Model_ID AND asm.Row_Number = arc.Row_Number
                 WHERE asm.Model_ID = fi.Model_ID AND arc.Class_ID = 'BUS') - 
                (SELECT COUNT(*) FROM Reservation r 
                 WHERE r.Instance_ID = fi.Instance_ID 
                 AND EXISTS (SELECT 1 FROM Aircraft_Row_Class arc2 
                           WHERE arc2.Model_ID = fi.Model_ID 
                           AND arc2.Row_Number = r.Row_Number 
                           AND arc2.Class_ID = 'BUS')) as Bus_Seats_Available,
                (SELECT COUNT(*) FROM Aircraft_Seat_Map asm
                 JOIN Aircraft_Row_Class arc ON asm.Model_ID = arc.Model_ID AND asm.Row_Number = arc.Row_Number
                 WHERE asm.Model_ID = fi.Model_ID AND arc.Class_ID = 'FIR') - 
                (SELECT COUNT(*) FROM Reservation r 
                 WHERE r.Instance_ID = fi.Instance_ID 
                 AND EXISTS (SELECT 1 FROM Aircraft_Row_Class arc2 
                           WHERE arc2.Model_ID = fi.Model_ID 
                           AND arc2.Row_Number = r.Row_Number 
                           AND arc2.Class_ID = 'FIR')) as First_Seats_Available
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            WHERE fi.Flight_Status = 'SCHEDULED'
            AND fi.Departure_Time >= SYSTIMESTAMP
        """
        
        params = {}
        
        # Add filters if provided
        if departure_city:
            query += " AND fr.Source_Airport = :departure_city"
            params['departure_city'] = departure_city
            
        if arrival_city:
            query += " AND fr.Dest_Airport = :arrival_city"
            params['arrival_city'] = arrival_city
            
        if travel_date:
            query += " AND TRUNC(fi.Departure_Time) = TO_DATE(:travel_date, 'YYYY-MM-DD')"
            params['travel_date'] = travel_date
        
        query += " ORDER BY fi.Departure_Time, c1.City_Name, c2.City_Name"
        
        cursor.execute(query, **params)
        flights = cursor.fetchall()
        
        # Format flight data for template
        flight_data = []
        for flight in flights:
            flight_info = {
                'instance_id': flight[0],
                'source_airport': flight[1],
                'dest_airport': flight[2],
                'departure_time': flight[3],
                'arrival_time': flight[4],
                'source_airport_name': flight[5],
                'dest_airport_name': flight[6],
                'source_city': flight[7],
                'dest_city': flight[8],
                'model_id': flight[9],
                'pricing': {
                    'ECO': flight[10] or 'N/A',
                    'BUS': flight[11] or 'N/A', 
                    'FIR': flight[12] or 'N/A'
                },
                'seats_available': {
                    'ECO': flight[13] or 0,
                    'BUS': flight[14] or 0,
                    'FIR': flight[15] or 0
                }
            }
            flight_data.append(flight_info)
        
        return render_template('pricing.html',
                            flights=flight_data,
                            cities=cities,
                            filters={
                                'departure_city': departure_city,
                                'arrival_city': arrival_city,
                                'travel_date': travel_date
                            })
        
    except Exception as e:
        print("Error loading pricing:", e)
        return render_template('error.html', error="Error loading flight pricing")
    finally:
        cursor.close()
        conn.close()

@app.route('/search-flights', methods=['GET'])
def search_flights_get():
    """Handle GET requests for flight search (from pricing page)"""
    departure_city = request.args.get('departure_city')
    arrival_city = request.args.get('arrival_city')
    departure_date = request.args.get('departure_date')
    
    if not all([departure_city, arrival_city, departure_date]):
        return render_template("search_results.html", flights=[], error="Please provide all search parameters")
    
    # Set default values for other parameters
    travel_class = 'ECO'
    passengers = '1'
    trip_type = 'one_way'
    
    print(f"GET Search: {departure_city} to {arrival_city} on {departure_date}")

    # Store search criteria in session for later use
    session['search_travel_class'] = travel_class
    session['search_passengers'] = passengers
    session['search_trip_type'] = trip_type

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get city names using new schema
        cursor.execute("""
            SELECT a.Airport_Name, c.City_Name 
            FROM Airport a
            JOIN Zip_Master z ON a.Zipcode = z.Zipcode
            JOIN City c ON z.City_ID = c.City_ID
            WHERE a.Airport_ID = :dept
        """, dept=departure_city)
        departure_info = cursor.fetchone()
        departure_city_name = departure_info[1] if departure_info else departure_city
        
        cursor.execute("""
            SELECT a.Airport_Name, c.City_Name 
            FROM Airport a
            JOIN Zip_Master z ON a.Zipcode = z.Zipcode
            JOIN City c ON z.City_ID = c.City_ID
            WHERE a.Airport_ID = :arr
        """, arr=arrival_city)
        arrival_info = cursor.fetchone()
        arrival_city_name = arrival_info[1] if arrival_info else arrival_city
        
        # Map travel class codes to full names
        class_names = {
            'ECO': 'Economy',
            'BUS': 'Business', 
            'FIR': 'First Class'
        }
        travel_class_name = class_names.get(travel_class, travel_class)

        # Get flights using View_Flight_Availability for efficient seat availability
        query = """
            SELECT fi.Instance_ID,
                   fr.Source_Airport,
                   fr.Dest_Airport,
                   TO_CHAR(fi.Departure_Time, 'YYYY-MM-DD HH24:MI'),
                   TO_CHAR(fi.Arrival_Time, 'YYYY-MM-DD HH24:MI'),
                   fi.Model_ID,
                   a1.Airport_Name AS Source_Airport_Name,
                   a2.Airport_Name AS Dest_Airport_Name,
                   c1.City_Name AS Source_City,
                   c2.City_Name AS Dest_City,
                   vfa.Seats_Remaining
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN View_Flight_Availability vfa ON fi.Instance_ID = vfa.Instance_ID
            WHERE fr.Source_Airport = :src
              AND fr.Dest_Airport = :dest
              AND TRUNC(fi.Departure_Time) = TO_DATE(:dep_date, 'YYYY-MM-DD')
              AND fi.Flight_Status = 'SCHEDULED'
        """
        cursor.execute(query, src=departure_city, dest=arrival_city, dep_date=departure_date)
        flights = cursor.fetchall()

        context = {
            "flights": flights,
            "search_criteria": {
                "departure_city": departure_city_name,
                "arrival_city": arrival_city_name,
                "date": departure_date,
                "travel_class": travel_class_name,
                "passengers": passengers,
                "trip_type": trip_type
            }
        }

        return render_template("search_results.html", **context)

    except Exception as e:
        print("Error while searching flights:", e)
        return render_template("search_results.html", flights=[], error="No flights found or invalid input")

    finally:
        cursor.close()
        conn.close()

@app.route('/search-flights', methods=['POST'])
def search_flights():
    # No login check - allow guests to search flights
    departure_city = request.form.get('departure_city')
    arrival_city = request.form.get('arrival_city')
    departure_date = request.form.get('departure_date')
    travel_class = request.form.get('travel_class')
    trip_type = request.form.get('trip_type', 'one_way')

    print(f"Searching {trip_type} flights: {departure_city} to {arrival_city} on {departure_date}")

    # Store search criteria in session for later use
    session['search_travel_class'] = travel_class
    session['search_trip_type'] = trip_type
    # Note: passengers is no longer stored here

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get city names using new schema
        cursor.execute("""
            SELECT a.Airport_Name, c.City_Name 
            FROM Airport a
            JOIN Zip_Master z ON a.Zipcode = z.Zipcode
            JOIN City c ON z.City_ID = c.City_ID
            WHERE a.Airport_ID = :dept
        """, dept=departure_city)
        departure_info = cursor.fetchone()
        departure_city_name = departure_info[1] if departure_info else departure_city
        
        cursor.execute("""
            SELECT a.Airport_Name, c.City_Name 
            FROM Airport a
            JOIN Zip_Master z ON a.Zipcode = z.Zipcode
            JOIN City c ON z.City_ID = c.City_ID
            WHERE a.Airport_ID = :arr
        """, arr=arrival_city)
        arrival_info = cursor.fetchone()
        arrival_city_name = arrival_info[1] if arrival_info else arrival_city
        
        # Map travel class codes to full names
        class_names = {
            'ECO': 'Economy',
            'BUS': 'Business', 
            'FIR': 'First Class'
        }
        travel_class_name = class_names.get(travel_class, travel_class)

        # Get flights using View_Flight_Availability for efficient seat availability
        query = """
            SELECT fi.Instance_ID,
                   fr.Source_Airport,
                   fr.Dest_Airport,
                   TO_CHAR(fi.Departure_Time, 'YYYY-MM-DD HH24:MI'),
                   TO_CHAR(fi.Arrival_Time, 'YYYY-MM-DD HH24:MI'),
                   fi.Model_ID,
                   a1.Airport_Name AS Source_Airport_Name,
                   a2.Airport_Name AS Dest_Airport_Name,
                   c1.City_Name AS Source_City,
                   c2.City_Name AS Dest_City,
                   vfa.Seats_Remaining
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN View_Flight_Availability vfa ON fi.Instance_ID = vfa.Instance_ID
            WHERE fr.Source_Airport = :src
              AND fr.Dest_Airport = :dest
              AND TRUNC(fi.Departure_Time) = TO_DATE(:dep_date, 'YYYY-MM-DD')
              AND fi.Flight_Status = 'SCHEDULED'
        """
        cursor.execute(query, src=departure_city, dest=arrival_city, dep_date=departure_date)
        flights = cursor.fetchall()

        context = {
            "flights": flights,
            "search_criteria": {
                "departure_city": departure_city_name,
                "arrival_city": arrival_city_name,
                "date": departure_date,
                "travel_class": travel_class_name,
                "trip_type": trip_type
            }
        }

        return render_template("search_results.html", **context)

    except Exception as e:
        print("Error while searching flights:", e)
        return render_template("search_results.html", flights=[], error="No flights found or invalid input")

    finally:
        cursor.close()
        conn.close()

@app.route('/select-flight/<flight_id>')
def select_flight(flight_id):
    # No login check - allow guests to select flights
    
    # Check if this is a reschedule operation - redirect to reschedule flow
    reschedule_context = session.get('reschedule_context')
    if reschedule_context or session.get('reschedule_reservation_ids'):
        return redirect(url_for('select_reschedule_flight', flight_id=flight_id))
    
    trip_type = request.args.get('trip_type') or session.get('search_trip_type', 'one_way')
    travel_class = request.args.get('travel_class') or session.get('search_travel_class', 'ECO')
    
    # Store flight selection in session
    session['selected_outbound_flight'] = flight_id
    session['trip_type'] = trip_type
    session['travel_class'] = travel_class
    
    print(f"DEBUG - Setting session travel_class: {travel_class}")
    print(f"DEBUG - Setting session trip_type: {trip_type}")
    
    # Redirect to passenger info for normal booking
    if session['trip_type'] == 'round_trip':
        return redirect('/return-flight-search')
    else:
        return redirect('/passenger-info')

@app.route('/return-flight-search', methods=['GET', 'POST'])
def return_flight_search():
    if request.method == 'POST':
        return_date = request.form.get('return_date')
        duration = request.form.get('duration')
        
        # Store return date in session
        session['return_date'] = return_date
        session['duration'] = duration
        
        # Get the original outbound flight to find return route
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT fr.Source_Airport, fr.Dest_Airport 
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=session['selected_outbound_flight'])
            
            flight_data = cursor.fetchone()
            if not flight_data:
                return render_template("return_flight_results.html", flights=[], error="Original flight not found")
                
            return_departure = flight_data[1]  # Destination becomes source for return
            return_arrival = flight_data[0]    # Source becomes destination for return
            
            print(f"Searching return flights: {return_departure} to {return_arrival} on {return_date}")
            
            # Search for return flights using View_Flight_Availability
            query = """
                SELECT fi.Instance_ID,
                       fr.Source_Airport,
                       fr.Dest_Airport,
                       TO_CHAR(fi.Departure_Time, 'YYYY-MM-DD HH24:MI'),
                       TO_CHAR(fi.Arrival_Time, 'YYYY-MM-DD HH24:MI'),
                       fi.Model_ID,
                       a1.Airport_Name AS Source_Airport_Name,
                       a2.Airport_Name AS Dest_Airport_Name,
                       c1.City_Name AS Source_City,
                       c2.City_Name AS Dest_City,
                       vfa.Seats_Remaining
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                JOIN City c1 ON zm1.City_ID = c1.City_ID
                JOIN City c2 ON zm2.City_ID = c2.City_ID
                JOIN View_Flight_Availability vfa ON fi.Instance_ID = vfa.Instance_ID
                WHERE fr.Source_Airport = :src
                  AND fr.Dest_Airport = :dest
                  AND TRUNC(fi.Departure_Time) = TO_DATE(:dep_date, 'YYYY-MM-DD')
                  AND fi.Flight_Status = 'SCHEDULED'
            """
            cursor.execute(query, src=return_departure, dest=return_arrival, dep_date=return_date)
            return_flights = cursor.fetchall()
            
            print(f"Found {len(return_flights)} return flights")
            
            return render_template("return_flight_results.html", 
                                 flights=return_flights,
                                 search_criteria={
                                     'date': return_date,
                                     'duration': duration
                                 })
            
        except Exception as e:
            print("Error searching return flights:", e)
            return render_template("return_flight_results.html", flights=[], error="No return flights found")
        
        finally:
            cursor.close()
            conn.close()
    
    else:
        # GET request - show return flight search form
        return render_template("return_flight_search.html")

@app.route('/seat-selection')
def seat_selection():
    # No login check - allow guests to select seats
    # Check if this is a reschedule operation
    reschedule_reservation_id = session.get('reschedule_reservation_id')
    is_reschedule = session.get('is_reschedule', False)
    
    if reschedule_reservation_id or is_reschedule:
        # This is a reschedule flow - use the reschedule flight
        flight_id = session.get('reschedule_new_flight') or session.get('selected_outbound_flight')
        if not flight_id:
            return render_template('error.html', error="Reschedule flight not found")
        
        # Use pre-filled data from select_reschedule_flight
        # Travel class, passengers, and passenger_data are already set
        travel_class = session.get('travel_class', session.get('reschedule_travel_class', 'ECO'))
        passengers = session.get('passengers', len(session.get('reschedule_passenger_data', [])))
        
        session['trip_type'] = 'one_way'
        session['selected_outbound_flight'] = flight_id
        session['is_reschedule'] = True
    else:
        # Normal booking flow
        flight_id = session.get('selected_outbound_flight')
        if not flight_id:
            return render_template('error.html', error="No flight selected")
    
    return_flight_id = session.get('selected_return_flight')
    passengers = int(session.get('passengers', 1))
    travel_class = session.get('travel_class', 'ECO')
    trip_type = session.get('trip_type', 'one_way')
    
    print(f"DEBUG - travel_class from session: {travel_class}")
    print(f"DEBUG - passengers: {passengers}")
    print(f"DEBUG - trip_type: {trip_type}")
    print(f"DEBUG - Reschedule mode: {reschedule_reservation_id is not None or is_reschedule}")
    print(f"DEBUG - Flight ID: {flight_id}")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get outbound flight details using new schema - UPDATED
        cursor.execute("""
            SELECT fi.Instance_ID, fi.Model_ID, 
                   c1.City_Name, c2.City_Name,
                   TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            WHERE fi.Instance_ID = :flight_id
        """, flight_id=flight_id)
        
        outbound_flight = cursor.fetchone()
        
        if not outbound_flight:
            return render_template('error.html', error="Outbound flight not found")
        
        return_flight = None
        if return_flight_id:
            cursor.execute("""
                SELECT fi.Instance_ID, fi.Model_ID, 
                       c1.City_Name, c2.City_Name,
                       TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                JOIN City c1 ON zm1.City_ID = c1.City_ID
                JOIN City c2 ON zm2.City_ID = c2.City_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=return_flight_id)
            return_flight = cursor.fetchone()
            
            if not return_flight:
                return render_template('error.html', error="Return flight not found")
        
        # Get available seats for outbound flight using new schema - UPDATED
        cursor.execute("""
            SELECT asm.Row_Number, asm.Seat_Letter, arc.Class_ID,
                   CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
            FROM Aircraft_Seat_Map asm
            JOIN Aircraft_Row_Class arc ON asm.Model_ID = arc.Model_ID AND asm.Row_Number = arc.Row_Number
            LEFT JOIN Reservation r ON asm.Model_ID = :model_id 
                AND asm.Row_Number = r.Row_Number 
                AND asm.Seat_Letter = r.Seat_Letter
                AND r.Instance_ID = :flight_id
            WHERE asm.Model_ID = :model_id
            AND arc.Class_ID = :travel_class
            ORDER BY asm.Row_Number, asm.Seat_Letter
        """, model_id=outbound_flight[1], flight_id=flight_id, travel_class=travel_class)
        
        outbound_seats = cursor.fetchall()
        
        # Get ALL booked seats for outbound flight (regardless of class) for the seat map
        cursor.execute("""
            SELECT r.Row_Number, r.Seat_Letter
            FROM Reservation r
            WHERE r.Instance_ID = :flight_id
            AND r.Booking_ID != COALESCE(:reschedule_booking_id, '0')  -- Exclude the booking being rescheduled
        """, flight_id=flight_id, reschedule_booking_id=session.get('reschedule_original_booking'))

        booked_outbound_seats = [f"{row[0]}{row[1]}" for row in cursor.fetchall()]
        print(f"DEBUG - Booked outbound seats (excluding reschedule): {booked_outbound_seats}")
        
        return_seats = []
        booked_return_seats = []
        
        if return_flight_id and return_flight:
            cursor.execute("""
                SELECT asm.Row_Number, asm.Seat_Letter, arc.Class_ID,
                       CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
                FROM Aircraft_Seat_Map asm
                JOIN Aircraft_Row_Class arc ON asm.Model_ID = arc.Model_ID AND asm.Row_Number = arc.Row_Number
                LEFT JOIN Reservation r ON asm.Model_ID = :model_id 
                    AND asm.Row_Number = r.Row_Number 
                    AND asm.Seat_Letter = r.Seat_Letter
                    AND r.Instance_ID = :flight_id
                WHERE asm.Model_ID = :model_id
                AND arc.Class_ID = :travel_class
                ORDER BY asm.Row_Number, asm.Seat_Letter
            """, model_id=return_flight[1], flight_id=return_flight_id, travel_class=travel_class)
            
            return_seats = cursor.fetchall()
            
            # Get ALL booked seats for return flight
            cursor.execute("""
                SELECT r.Row_Number, r.Seat_Letter
                FROM Reservation r
                WHERE r.Instance_ID = :flight_id
            """, flight_id=return_flight_id)
            
            booked_return_seats = [f"{row[0]}{row[1]}" for row in cursor.fetchall()]
            print(f"DEBUG - Booked return seats: {booked_return_seats}")
        
        # Ensure travel_class is one of the expected values
        if travel_class not in ['ECO', 'BUS', 'FIR']:
            travel_class = 'ECO'
        
        # Get passenger_data from session for infant detection
        passenger_data = session.get('passenger_data', [])
        print(f"DEBUG - Passenger data for seat selection: {passenger_data}")
        
        return render_template('seat_selection.html',
                            outbound_flight=outbound_flight,
                            return_flight=return_flight,
                            outbound_seats=outbound_seats,
                            return_seats=return_seats,
                            booked_outbound_seats=booked_outbound_seats,
                            booked_return_seats=booked_return_seats,
                            passengers=passengers,
                            passenger_data=passenger_data,
                            travel_class=travel_class,
                            trip_type=trip_type,
                            is_reschedule=reschedule_reservation_id is not None)
        
    except Exception as e:
        print("Error in seat selection:", e)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error="Error loading seat selection")
        
    finally:
        cursor.close()
        conn.close()

@app.route('/get-seat-status/<flight_id>')
def get_seat_status(flight_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT asm.Row_Number || asm.Seat_Letter as seat_id,
                   CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
            FROM Flight_Instance fi
            JOIN Aircraft_Seat_Map asm ON fi.Model_ID = asm.Model_ID
            LEFT JOIN Reservation r ON asm.Model_ID = fi.Model_ID 
                AND asm.Row_Number = r.Row_Number 
                AND asm.Seat_Letter = r.Seat_Letter
                AND r.Instance_ID = :flight_id
            WHERE fi.Instance_ID = :flight_id
            ORDER BY asm.Row_Number, asm.Seat_Letter
        """, flight_id=flight_id)
        
        seats = cursor.fetchall()
        seat_data = {seat[0]: seat[1] for seat in seats}
        
        return jsonify(seat_data)
        
    except Exception as e:
        print("Error getting seat status:", e)
        return jsonify({})
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# API: Member Lookup by User ID and Date of Birth
# =============================================================================
@app.route('/api/member-lookup', methods=['POST'])
def api_member_lookup():
    """
    Look up a registered user's passenger profile by User ID and Date of Birth.
    This allows autofilling passenger details for a booking.
    
    Input JSON: { "userId": 123, "dateOfBirth": "2004-12-04" }
    
    Returns:
    - 200 with passenger data if found and DOB matches
    - 404 if no user/passenger found or DOB doesn't match
    - 400 if invalid input
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Invalid request. JSON body required.'}), 400
    
    user_id = data.get('userId')
    date_of_birth = data.get('dateOfBirth')
    
    # Validate user_id
    if not user_id:
        return jsonify({'error': 'User ID is required.'}), 400
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'User ID must be a valid number.'}), 400
    
    # Validate date_of_birth format
    if not date_of_birth:
        return jsonify({'error': 'Date of Birth is required.'}), 400
    
    try:
        # Validate date format (YYYY-MM-DD)
        from datetime import datetime
        datetime.strptime(date_of_birth, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # First check if the App_User exists
        cursor.execute("""
            SELECT User_ID, Email FROM App_User WHERE User_ID = :user_id
        """, user_id=user_id)
        
        app_user = cursor.fetchone()
        
        if not app_user:
            return jsonify({'error': 'No member found with this User ID.'}), 404
        
        # Look up passenger profile linked to this user
        cursor.execute("""
            SELECT 
                p.Passenger_ID,
                p.Title,
                p.First_Name,
                p.Last_Name,
                p.Gender,
                TO_CHAR(p.Date_Of_Birth, 'YYYY-MM-DD') AS Date_Of_Birth,
                p.Passport_Num
            FROM Passenger p
            WHERE p.Linked_User_ID = :user_id
        """, user_id=user_id)
        
        passenger = cursor.fetchone()
        
        if not passenger:
            return jsonify({'error': 'No passenger profile found for this User ID.'}), 404
        
        # Verify date of birth matches (security check)
        stored_dob = passenger[5]  # Date_Of_Birth from query
        if stored_dob != date_of_birth:
            return jsonify({'error': 'User ID or Date of Birth does not match. Please verify your details.'}), 404
        
        # Success - return passenger details
        return jsonify({
            'success': True,
            'passengerId': passenger[0],
            'title': passenger[1],
            'firstName': passenger[2],
            'lastName': passenger[3],
            'gender': passenger[4],
            'dateOfBirth': passenger[5],
            'passportNum': passenger[6],
            'message': f'Member found: {passenger[2]} {passenger[3]}'
        })
        
    except Exception as e:
        print(f"Error in member lookup: {e}")
        return jsonify({'error': 'An error occurred while looking up the member.'}), 500
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# API: Get My Profile (For "Add Myself" feature)
# =============================================================================
@app.route('/api/my-profile')
def api_my_profile():
    """
    Get the logged-in user's passenger profile details.
    Used by "Add Myself" button to auto-fill passenger form.
    Returns the user's linked passenger profile if it exists,
    otherwise returns basic info from App_User table.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # First, check if user has a linked passenger profile
        cursor.execute("""
            SELECT 
                p.Passenger_ID,
                p.Title,
                p.First_Name,
                p.Last_Name,
                p.Gender,
                TO_CHAR(p.Date_Of_Birth, 'YYYY-MM-DD') AS Date_Of_Birth,
                p.Passport_Num
            FROM Passenger p
            WHERE p.Linked_User_ID = :user_id
        """, user_id=user_id)
        
        passenger = cursor.fetchone()
        
        if passenger:
            # User has an existing passenger profile
            return jsonify({
                'hasProfile': True,
                'passengerId': passenger[0],
                'title': passenger[1],
                'firstName': passenger[2],
                'lastName': passenger[3],
                'gender': passenger[4],
                'dateOfBirth': passenger[5],
                'passportNum': passenger[6]
            })
        else:
            # No passenger profile yet - return basic user info
            cursor.execute("""
                SELECT Email, Phone_Number
                FROM App_User
                WHERE User_ID = :user_id
            """, user_id=user_id)
            
            user_info = cursor.fetchone()
            
            return jsonify({
                'hasProfile': False,
                'passengerId': None,
                'email': user_info[0] if user_info else None,
                'phone': user_info[1] if user_info else None
            })
            
    except Exception as e:
        print(f"Error getting user profile: {e}")
        return jsonify({'error': 'Failed to load profile'}), 500
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# API: Past Passengers (Add from past bookings feature)
# =============================================================================
@app.route('/api/past-passengers')
def api_past_passengers():
    """
    Get passengers previously booked by the current logged-in user.
    Uses View_Past_Passengers for efficient querying.
    Excludes the user's own passenger profile (Linked_User_ID = current user).
    Returns JSON with passenger details and recent trip history.
    """
    # Authentication check
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Query past passengers using View_Past_Passengers
        # The view filters only bookings by logged-in users and provides all needed data
        cursor.execute("""
            SELECT DISTINCT
                Passenger_ID,
                Title,
                First_Name,
                Last_Name,
                Gender,
                TO_CHAR(Date_Of_Birth, 'YYYY-MM-DD') AS Date_Of_Birth,
                Passport_Num,
                Linked_User_ID,
                Is_Registered_User
            FROM View_Past_Passengers
            WHERE Lead_User_ID = :user_id
              AND (Linked_User_ID IS NULL OR Linked_User_ID != :user_id)
            ORDER BY First_Name, Last_Name
        """, user_id=user_id)
        
        passengers_raw = cursor.fetchall()
        
        if not passengers_raw:
            return jsonify([])
        
        # Build response with trip history for each passenger
        passengers = []
        for pax in passengers_raw:
            passenger_id = pax[0]
            
            # Get recent trips for this passenger using View_Past_Passengers
            cursor.execute("""
                SELECT 
                    Booking_ID,
                    Reservation_ID,
                    Instance_ID,
                    Source_Airport,
                    Dest_Airport,
                    Departure_Airport_Name AS From_Airport,
                    Arrival_Airport_Name AS To_Airport,
                    TO_CHAR(Departure_Time, 'YYYY-MM-DD"T"HH24:MI:SS') AS Departure_Time,
                    TO_CHAR(Arrival_Time, 'YYYY-MM-DD"T"HH24:MI:SS') AS Arrival_Time,
                    Row_Number,
                    Seat_Letter,
                    Ticket_Status,
                    Price_Charged,
                    Passenger_Type
                FROM View_Past_Passengers
                WHERE Passenger_ID = :passenger_id
                  AND Lead_User_ID = :user_id
                ORDER BY Departure_Time DESC
                FETCH FIRST 5 ROWS ONLY
            """, passenger_id=passenger_id, user_id=user_id)
            
            trips_raw = cursor.fetchall()
            
            recent_trips = []
            for trip in trips_raw:
                seat_number = None
                if trip[9] and trip[10]:
                    seat_number = f"{trip[9]}{trip[10]}"
                elif trip[13] == 'LAP_INFANT':
                    seat_number = "Lap (No Seat)"
                
                recent_trips.append({
                    'bookingId': trip[0],
                    'reservationId': trip[1],
                    'flightNumber': trip[2],  # Instance_ID as flight number
                    'fromCity': trip[3],      # Airport code
                    'toCity': trip[4],        # Airport code
                    'fromAirport': trip[5],   # Full airport name
                    'toAirport': trip[6],     # Full airport name
                    'departureTime': trip[7],
                    'arrivalTime': trip[8],
                    'rowNumber': trip[9],
                    'seatLetter': trip[10],
                    'seatNumber': seat_number,
                    'ticketStatus': trip[11],
                    'priceCharged': float(trip[12]) if trip[12] else 0,
                    'passengerType': trip[13]
                })
            
            passengers.append({
                'passengerId': pax[0],
                'title': pax[1],
                'firstName': pax[2],
                'lastName': pax[3],
                'gender': pax[4],
                'dateOfBirth': pax[5],
                'passportNum': pax[6] or '',
                'linkedUserId': pax[7],
                'isRegisteredUser': bool(pax[8]),
                'recentTrips': recent_trips
            })
        
        return jsonify(passengers)
        
    except Exception as e:
        print(f"Error fetching past passengers: {e}")
        return jsonify({'error': 'Failed to fetch past passengers'}), 500
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# API: Family Management Endpoints
# =============================================================================

@app.route('/api/family/invite', methods=['POST'])
def api_family_invite():
    """
    Send a family invitation to another registered user.
    Input: { "familyEmail": "user@example.com", "relationship": "SPOUSE" }
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    family_email = data.get('familyEmail', '').strip().lower()
    relationship = data.get('relationship', '').strip().upper()
    
    if not family_email:
        return jsonify({'error': 'Family member email is required'}), 400
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Look up the family user by email
        cursor.execute("""
            SELECT User_ID, Email FROM App_User WHERE LOWER(Email) = :email
        """, email=family_email)
        
        family_user = cursor.fetchone()
        
        if not family_user:
            return jsonify({'error': 'No user found with that email address'}), 404
        
        family_user_id = family_user[0]
        
        # Cannot add yourself as family
        if family_user_id == user_id:
            return jsonify({'error': 'You cannot add yourself as a family member'}), 400
        
        # Check if relationship already exists
        cursor.execute("""
            SELECT Status FROM User_Family 
            WHERE User_ID = :user_id AND Family_User_ID = :family_id
        """, user_id=user_id, family_id=family_user_id)
        
        existing = cursor.fetchone()
        
        if existing:
            if existing[0] == 'ACCEPTED':
                return jsonify({'error': 'This user is already in your family'}), 400
            elif existing[0] == 'PENDING':
                return jsonify({'error': 'A pending invitation already exists for this user'}), 400
            elif existing[0] == 'REJECTED':
                # Update rejected to pending (re-invite)
                cursor.execute("""
                    UPDATE User_Family 
                    SET Status = 'PENDING', 
                        Relationship = :relationship,
                        Created_At = SYSTIMESTAMP
                    WHERE User_ID = :user_id AND Family_User_ID = :family_id
                """, user_id=user_id, family_id=family_user_id, 
                    relationship=relationship if relationship else None)
                conn.commit()
                return jsonify({
                    'success': True, 
                    'message': 'Family invitation re-sent successfully'
                })
        
        # Check if the other user already sent us an invitation
        cursor.execute("""
            SELECT Status FROM User_Family 
            WHERE User_ID = :family_id AND Family_User_ID = :user_id
        """, user_id=user_id, family_id=family_user_id)
        
        reverse_existing = cursor.fetchone()
        
        if reverse_existing and reverse_existing[0] == 'PENDING':
            return jsonify({
                'error': 'This user has already sent you a family request. Check your pending requests.',
                'hasPendingRequest': True
            }), 400
        
        # Insert new invitation
        cursor.execute("""
            INSERT INTO User_Family (User_ID, Family_User_ID, Relationship, Status, Created_At)
            VALUES (:user_id, :family_id, :relationship, 'PENDING', SYSTIMESTAMP)
        """, user_id=user_id, family_id=family_user_id, 
            relationship=relationship if relationship else None)
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Family invitation sent to {family_email}'
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Error sending family invite: {e}")
        return jsonify({'error': 'Failed to send invitation'}), 500
        
    finally:
        cursor.close()
        conn.close()


@app.route('/api/family/respond', methods=['POST'])
def api_family_respond():
    """
    Accept or reject a family invitation.
    Input: { "requestingUserId": 123, "action": "ACCEPT" } or "REJECT"
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    requesting_user_id = data.get('requestingUserId')
    action = data.get('action', '').upper()
    
    if not requesting_user_id:
        return jsonify({'error': 'Requesting user ID is required'}), 400
    
    if action not in ['ACCEPT', 'REJECT']:
        return jsonify({'error': 'Action must be ACCEPT or REJECT'}), 400
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verify a pending request exists from requesting_user_id to current user
        cursor.execute("""
            SELECT Status, Relationship FROM User_Family 
            WHERE User_ID = :requesting_id AND Family_User_ID = :user_id
        """, requesting_id=requesting_user_id, user_id=user_id)
        
        request_row = cursor.fetchone()
        
        if not request_row:
            return jsonify({'error': 'No family request found from this user'}), 404
        
        if request_row[0] != 'PENDING':
            return jsonify({'error': f'This request has already been {request_row[0].lower()}'}), 400
        
        relationship = request_row[1]
        
        if action == 'REJECT':
            # Update status to rejected
            cursor.execute("""
                UPDATE User_Family 
                SET Status = 'REJECTED'
                WHERE User_ID = :requesting_id AND Family_User_ID = :user_id
            """, requesting_id=requesting_user_id, user_id=user_id)
            conn.commit()
            return jsonify({'success': True, 'message': 'Family request rejected'})
        
        # ACCEPT: Update the original row - trigger handles reciprocal automatically
        # TRG_Auto_Reciprocal_Family will create/update the reciprocal relationship
        cursor.execute("""
            UPDATE User_Family 
            SET Status = 'ACCEPTED'
            WHERE User_ID = :requesting_id AND Family_User_ID = :user_id
        """, requesting_id=requesting_user_id, user_id=user_id)
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Family request accepted!'})
        
    except Exception as e:
        conn.rollback()
        print(f"Error responding to family request: {e}")
        return jsonify({'error': 'Failed to respond to request'}), 500
        
    finally:
        cursor.close()
        conn.close()


@app.route('/api/family')
def api_family_list():
    """
    Get all accepted family members for the logged-in user.
    Also includes their passenger profile info if available.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get accepted family members with their App_User info and Passenger profile
        cursor.execute("""
            SELECT 
                uf.Family_User_ID,
                au.Email,
                uf.Relationship,
                uf.Created_At,
                p.Passenger_ID,
                p.Title,
                p.First_Name,
                p.Last_Name,
                p.Gender,
                TO_CHAR(p.Date_Of_Birth, 'YYYY-MM-DD') AS Date_Of_Birth,
                p.Passport_Num
            FROM User_Family uf
            JOIN App_User au ON uf.Family_User_ID = au.User_ID
            LEFT JOIN Passenger p ON p.Linked_User_ID = uf.Family_User_ID
            WHERE uf.User_ID = :user_id
              AND uf.Status = 'ACCEPTED'
            ORDER BY p.First_Name, p.Last_Name, au.Email
        """, user_id=user_id)
        
        family_raw = cursor.fetchall()
        
        family_members = []
        for member in family_raw:
            has_profile = member[4] is not None
            
            family_members.append({
                'userId': member[0],
                'email': member[1],
                'relationship': member[2],
                'addedAt': member[3].strftime('%Y-%m-%d') if member[3] else None,
                'hasPassengerProfile': has_profile,
                'passengerId': member[4],
                'passenger': {
                    'title': member[5],
                    'firstName': member[6],
                    'lastName': member[7],
                    'gender': member[8],
                    'dateOfBirth': member[9],
                    'passportNum': member[10]
                } if has_profile else None
            })
        
        return jsonify(family_members)
        
    except Exception as e:
        print(f"Error fetching family list: {e}")
        return jsonify({'error': 'Failed to fetch family members'}), 500
        
    finally:
        cursor.close()
        conn.close()


@app.route('/api/family/pending')
def api_family_pending():
    """
    Get pending family requests for the logged-in user.
    Returns both incoming (requests from others) and outgoing (requests sent).
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get incoming pending requests (others inviting current user)
        cursor.execute("""
            SELECT 
                uf.User_ID AS requesting_user_id,
                au.Email,
                uf.Relationship,
                uf.Created_At,
                p.First_Name,
                p.Last_Name
            FROM User_Family uf
            JOIN App_User au ON uf.User_ID = au.User_ID
            LEFT JOIN Passenger p ON p.Linked_User_ID = uf.User_ID
            WHERE uf.Family_User_ID = :user_id
              AND uf.Status = 'PENDING'
            ORDER BY uf.Created_At DESC
        """, user_id=user_id)
        
        incoming_raw = cursor.fetchall()
        
        incoming = []
        for req in incoming_raw:
            name = f"{req[4]} {req[5]}" if req[4] and req[5] else req[1].split('@')[0]
            incoming.append({
                'requestingUserId': req[0],
                'email': req[1],
                'name': name,
                'relationship': req[2],
                'createdAt': req[3].strftime('%Y-%m-%d %H:%M') if req[3] else None
            })
        
        # Get outgoing pending requests (current user inviting others)
        cursor.execute("""
            SELECT 
                uf.Family_User_ID,
                au.Email,
                uf.Relationship,
                uf.Created_At,
                p.First_Name,
                p.Last_Name
            FROM User_Family uf
            JOIN App_User au ON uf.Family_User_ID = au.User_ID
            LEFT JOIN Passenger p ON p.Linked_User_ID = uf.Family_User_ID
            WHERE uf.User_ID = :user_id
              AND uf.Status = 'PENDING'
            ORDER BY uf.Created_At DESC
        """, user_id=user_id)
        
        outgoing_raw = cursor.fetchall()
        
        outgoing = []
        for req in outgoing_raw:
            name = f"{req[4]} {req[5]}" if req[4] and req[5] else req[1].split('@')[0]
            outgoing.append({
                'invitedUserId': req[0],
                'email': req[1],
                'name': name,
                'relationship': req[2],
                'createdAt': req[3].strftime('%Y-%m-%d %H:%M') if req[3] else None
            })
        
        return jsonify({
            'incoming': incoming,
            'outgoing': outgoing
        })
        
    except Exception as e:
        print(f"Error fetching pending requests: {e}")
        return jsonify({'error': 'Failed to fetch pending requests'}), 500
        
    finally:
        cursor.close()
        conn.close()


@app.route('/api/family/remove', methods=['POST'])
def api_family_remove():
    """
    Remove a family member (both directions of the relationship).
    Input: { "familyUserId": 123 }
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    family_user_id = data.get('familyUserId')
    
    if not family_user_id:
        return jsonify({'error': 'Family user ID is required'}), 400
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Delete both directions of the relationship
        cursor.execute("""
            DELETE FROM User_Family 
            WHERE (User_ID = :user_id AND Family_User_ID = :family_id)
               OR (User_ID = :family_id AND Family_User_ID = :user_id)
        """, user_id=user_id, family_id=family_user_id)
        
        rows_deleted = cursor.rowcount
        conn.commit()
        
        if rows_deleted == 0:
            return jsonify({'error': 'No family relationship found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Family member removed successfully'
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Error removing family member: {e}")
        return jsonify({'error': 'Failed to remove family member'}), 500
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# API: Booking Summary with Infant Breakdown (uses View_Booking_Infant_Summary)
# =============================================================================

@app.route('/api/bookings/<booking_id>/summary')
def api_booking_summary(booking_id):
    """
    Get booking summary with infant breakdown using View_Booking_Infant_Summary.
    Returns:
    - Adult count, Lap infant count, Seated infant count
    - Total price and paid amount breakdown
    - Flight details for each flight in the booking
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Use View_Booking_Infant_Summary for efficient infant breakdown
        cursor.execute("""
            SELECT 
                Booking_ID,
                Contact_Email,
                Instance_ID,
                Adult_Count,
                Lap_Infant_Count,
                Seated_Infant_Count,
                Total_Price,
                Paid_Amount
            FROM View_Booking_Infant_Summary
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        summaries = cursor.fetchall()
        
        if not summaries:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Build response with summary per flight
        flights = []
        total_adults = 0
        total_lap_infants = 0
        total_seated_infants = 0
        grand_total = 0
        
        for summary in summaries:
            flights.append({
                'instanceId': summary[2],
                'adultCount': summary[3],
                'lapInfantCount': summary[4],
                'seatedInfantCount': summary[5],
                'totalPrice': float(summary[6]) if summary[6] else 0,
                'paidAmount': float(summary[7]) if summary[7] else 0
            })
            total_adults += summary[3] or 0
            total_lap_infants += summary[4] or 0
            total_seated_infants += summary[5] or 0
            grand_total += float(summary[6]) if summary[6] else 0
        
        return jsonify({
            'bookingId': booking_id,
            'contactEmail': summaries[0][1],
            'summary': {
                'totalAdults': total_adults,
                'totalLapInfants': total_lap_infants,
                'totalSeatedInfants': total_seated_infants,
                'totalPassengers': total_adults + total_lap_infants + total_seated_infants,
                'grandTotal': grand_total
            },
            'flights': flights
        })
        
    except Exception as e:
        print(f"Error getting booking summary: {e}")
        return jsonify({'error': 'Failed to get booking summary'}), 500
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# API: Booking History (My Trips) with Family-aware Classification
# =============================================================================

@app.route('/api/bookings/history')
def api_booking_history():
    """
    Get booking history for the logged-in user.
    Returns all trips where this user was a passenger (based on Passenger.Linked_User_ID).
    Includes family-aware 'bookedBy' classification:
    - SELF: user was the lead user (Lead_User_ID = current user)
    - FAMILY: lead user is an accepted family member
    - OTHER: some other user made the booking
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized. Please log in.'}), 401
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # First, find the user's passenger profile
        cursor.execute("""
            SELECT Passenger_ID FROM Passenger WHERE Linked_User_ID = :user_id
        """, user_id=user_id)
        
        pax_row = cursor.fetchone()
        
        if not pax_row:
            # User has no passenger profile, return empty list
            return jsonify([])
        
        passenger_id = pax_row[0]
        
        # Get all reservations for this passenger
        cursor.execute("""
            SELECT 
                r.Reservation_ID,
                r.Booking_ID,
                b.Booking_Date,
                b.Lead_User_ID,
                b.Booking_Status,
                r.Instance_ID,
                fi.Departure_Time,
                fi.Arrival_Time,
                fi.Flight_Status,
                fr.Source_Airport,
                fr.Dest_Airport,
                dep_apt.Airport_Name AS Dep_Airport_Name,
                arr_apt.Airport_Name AS Arr_Airport_Name,
                dep_city.City_Name AS From_City,
                arr_city.City_Name AS To_City,
                r.Row_Number,
                r.Seat_Letter,
                r.Price_Charged,
                r.Ticket_Status,
                r.Passenger_Type,
                lead_user.Email AS Lead_Email,
                lead_pax.First_Name AS Lead_First_Name,
                lead_pax.Last_Name AS Lead_Last_Name
            FROM Reservation r
            JOIN Booking b ON r.Booking_ID = b.Booking_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport dep_apt ON fr.Source_Airport = dep_apt.Airport_ID
            JOIN Airport arr_apt ON fr.Dest_Airport = arr_apt.Airport_ID
            JOIN Zip_Master dep_zip ON dep_apt.Zipcode = dep_zip.Zipcode
            JOIN Zip_Master arr_zip ON arr_apt.Zipcode = arr_zip.Zipcode
            JOIN City dep_city ON dep_zip.City_ID = dep_city.City_ID
            JOIN City arr_city ON arr_zip.City_ID = arr_city.City_ID
            LEFT JOIN App_User lead_user ON b.Lead_User_ID = lead_user.User_ID
            LEFT JOIN Passenger lead_pax ON lead_pax.Linked_User_ID = b.Lead_User_ID
            WHERE r.Passenger_ID = :passenger_id
            ORDER BY fi.Departure_Time DESC
        """, passenger_id=passenger_id)
        
        reservations_raw = cursor.fetchall()
        
        # Get all accepted family user IDs for quick lookup
        cursor.execute("""
            SELECT Family_User_ID FROM User_Family
            WHERE User_ID = :user_id AND Status = 'ACCEPTED'
        """, user_id=user_id)
        
        family_ids = {row[0] for row in cursor.fetchall()}
        
        # Build the response
        history = []
        for res in reservations_raw:
            lead_user_id = res[3]
            
            # Determine bookedBy classification
            if lead_user_id == user_id:
                booked_by = 'SELF'
                lead_user_info = None
            elif lead_user_id in family_ids:
                booked_by = 'FAMILY'
                lead_name = f"{res[21]} {res[22]}" if res[21] and res[22] else res[20].split('@')[0] if res[20] else 'Unknown'
                lead_user_info = {
                    'userId': lead_user_id,
                    'email': res[20],
                    'name': lead_name
                }
            else:
                booked_by = 'OTHER'
                lead_user_info = {
                    'userId': lead_user_id,
                    'email': res[20] if res[20] else None
                } if lead_user_id else None
            
            # Format seat
            seat = None
            if res[15] and res[16]:
                seat = f"{res[15]}{res[16]}"
            elif res[19] == 'LAP_INFANT':
                seat = "Lap (No Seat)"
            
            history.append({
                'reservationId': res[0],
                'bookingId': res[1],
                'bookingDate': res[2].strftime('%Y-%m-%d') if res[2] else None,
                'bookingStatus': res[4],
                'flightNumber': res[5],  # Instance_ID
                'departureTime': res[6].strftime('%Y-%m-%dT%H:%M:%S') if res[6] else None,
                'arrivalTime': res[7].strftime('%Y-%m-%dT%H:%M:%S') if res[7] else None,
                'flightStatus': res[8],
                'fromAirportCode': res[9],
                'toAirportCode': res[10],
                'fromAirport': res[11],
                'toAirport': res[12],
                'fromCity': res[13],
                'toCity': res[14],
                'rowNumber': res[15],
                'seatLetter': res[16],
                'seat': seat,
                'priceCharged': float(res[17]) if res[17] else 0,
                'ticketStatus': res[18],
                'passengerType': res[19],
                'bookedBy': booked_by,
                'leadUser': lead_user_info
            })
        
        return jsonify(history)
        
    except Exception as e:
        print(f"Error fetching booking history: {e}")
        return jsonify({'error': 'Failed to fetch booking history'}), 500
        
    finally:
        cursor.close()
        conn.close()


@app.route('/select-return-flight/<flight_id>')
def select_return_flight(flight_id):
    session['selected_return_flight'] = flight_id
    # After selecting return flight, go to passenger info (not seat selection)
    return redirect('/passenger-info')

@app.route('/passenger-info', methods=['GET', 'POST'])
def passenger_info():
    if request.method == 'GET':
        # GET request - show passenger information form
        flight_id = session.get('selected_outbound_flight')
        if not flight_id:
            return redirect('/')
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Get flight details
            cursor.execute("""
                SELECT fi.Instance_ID, fi.Model_ID, 
                       c1.City_Name, c2.City_Name,
                       TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                JOIN City c1 ON zm1.City_ID = c1.City_ID
                JOIN City c2 ON zm2.City_ID = c2.City_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=flight_id)
            outbound_flight = cursor.fetchone()
            
            return_flight_id = session.get('selected_return_flight')
            return_flight = None
            if return_flight_id:
                cursor.execute("""
                    SELECT fi.Instance_ID, fi.Model_ID, 
                           c1.City_Name, c2.City_Name,
                           TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
                    FROM Flight_Instance fi
                    JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                    JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                    JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                    JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                    JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                    JOIN City c1 ON zm1.City_ID = c1.City_ID
                    JOIN City c2 ON zm2.City_ID = c2.City_ID
                    WHERE fi.Instance_ID = :flight_id
                """, flight_id=return_flight_id)
                return_flight = cursor.fetchone()
            
            # For guest users, these will be empty - they'll fill them in the form
            user_email = session.get('user_email', '')
            user_phone = session.get('user_phone', '')
            
            return render_template('passenger_info.html',
                                outbound_flight=outbound_flight,
                                return_flight=return_flight,
                                travel_class=session.get('travel_class', 'ECO'),
                                trip_type=session.get('trip_type', 'one_way'),
                                user_email=user_email,
                                user_phone=user_phone,
                                is_guest=not session.get('user_id'))
            
        except Exception as e:
            print("Error in passenger info:", e)
            return render_template('error.html', error="Error loading passenger information")
            
        finally:
            cursor.close()
            conn.close()
    
    else:
        # POST request - process passenger information and redirect to seat selection
        try:
            # Get passenger count and data from form
            passenger_count = int(request.form.get('passenger_count', 1))
            passenger_data = []
            
            # Get contact information
            contact_email = request.form.get('contact_email')
            contact_phone = request.form.get('contact_phone')
            
            print(f"DEBUG - Passenger Count: {passenger_count}")
            print(f"DEBUG - Contact Email: {contact_email}")
            print(f"DEBUG - Contact Phone: {contact_phone}")
            
            # Validate contact information
            if not contact_email or not contact_phone:
                return render_template('error.html', error="Contact email and phone are required")
            
            # Store contact info in session
            session['contact_email'] = contact_email
            session['contact_phone'] = contact_phone
            
            # Collect passenger data
            for i in range(passenger_count):
                # Check for "is_self" flag (user clicked "Add Myself")
                is_self = request.form.get(f'is_self_{i}') == 'true'
                # Check for existing passenger ID (from "Add from Past Bookings" or "Add Myself" with existing profile)
                existing_passenger_id = request.form.get(f'existing_passenger_id_{i}')
                
                passenger_data.append({
                    'first_name': request.form.get(f'first_name_{i}'),
                    'last_name': request.form.get(f'last_name_{i}'),
                    'date_of_birth': request.form.get(f'date_of_birth_{i}'),
                    'gender': request.form.get(f'gender_{i}'),
                    'passport_number': request.form.get(f'passport_number_{i}', ''),
                    'title': request.form.get(f'title_{i}', 'MR'),
                    'is_self': is_self,  # True if user clicked "Add Myself"
                    'existing_passenger_id': int(existing_passenger_id) if existing_passenger_id else None
                })
                
                print(f"DEBUG - Passenger {i}: is_self={is_self}, existing_id={existing_passenger_id}")
            
            # Validate all passenger data
            for i, passenger in enumerate(passenger_data):
                if not all([passenger['first_name'], passenger['last_name'], passenger['date_of_birth'], passenger['gender']]):
                    return render_template('error.html', error=f"Please fill all required fields for passenger {i+1}")
            
            # Check for duplicate passengers (same passenger ID or same name + DOB)
            seen_passenger_ids = set()
            seen_name_dob = set()
            
            for i, passenger in enumerate(passenger_data):
                # Check by existing passenger ID
                if passenger['existing_passenger_id']:
                    if passenger['existing_passenger_id'] in seen_passenger_ids:
                        return render_template('error.html', 
                            error=f"Duplicate passenger detected: {passenger['first_name']} {passenger['last_name']} appears multiple times. Each passenger can only be booked once per reservation.")
                    seen_passenger_ids.add(passenger['existing_passenger_id'])
                
                # Check by name + date of birth combination
                name_dob_key = f"{passenger['first_name'].lower()}|{passenger['last_name'].lower()}|{passenger['date_of_birth']}"
                if name_dob_key in seen_name_dob:
                    return render_template('error.html', 
                        error=f"Duplicate passenger detected: {passenger['first_name']} {passenger['last_name']} with DOB {passenger['date_of_birth']} appears multiple times. Each passenger can only be booked once per reservation.")
                seen_name_dob.add(name_dob_key)
            
            # Store passenger data and count in session
            session['passenger_data'] = passenger_data
            session['passengers'] = passenger_count
            
            print(f"DEBUG - Stored {passenger_count} passengers in session")
            
            # For round trip, check if return flight is selected
            if session.get('trip_type') == 'round_trip' and not session.get('selected_return_flight'):
                return redirect('/return-flight-search')
            else:
                return redirect('/seat-selection')
                
        except Exception as e:
            print("Error processing passenger info:", e)
            return render_template('error.html', error="Error processing passenger information")

def validate_cnic(cnic):
    """Validate CNIC format (XXXXX-XXXXXXX-X)"""
    if not cnic:
        return False
    pattern = r'^\d{5}-\d{7}-\d{1}$'
    return re.match(pattern, cnic) is not None

@app.route('/process-booking', methods=['POST'])
def process_booking():
    try:
        # Get passenger data from session (not from form)
        passenger_data = session.get('passenger_data', [])
        passengers = len(passenger_data)
        
        if passengers == 0:
            return render_template('error.html', error="No passenger data found. Please start over.")
        
        # Get contact information from session
        contact_email = session.get('contact_email')
        contact_phone = session.get('contact_phone')
        
        print(f"DEBUG - Contact Email: {contact_email}")
        print(f"DEBUG - Contact Phone: {contact_phone}")
        print(f"DEBUG - Processing {passengers} passengers from session")
        
        # Validate contact information
        if not contact_email or not contact_phone:
            return render_template('error.html', error="Contact email and phone are required")
        
        # Get seat selections and other data
        selected_outbound_seats = request.form.getlist('selected_outbound_seats')
        selected_return_seats = request.form.getlist('selected_return_seats')
        outbound_flight_id = session.get('selected_outbound_flight')
        return_flight_id = session.get('selected_return_flight')
        trip_type = session.get('trip_type', 'one_way')
        travel_class = session.get('travel_class', 'ECO')
        
        # Get user ID if logged in, otherwise None for guest
        lead_user_id = session.get('user_id')
        
        print(f"DEBUG - Lead User ID: {lead_user_id} (None = guest booking)")
        print(f"DEBUG - Outbound flight: {outbound_flight_id}")
        print(f"DEBUG - Return flight: {return_flight_id}")
        print(f"DEBUG - Selected outbound seats: {selected_outbound_seats}")
        print(f"DEBUG - Selected return seats: {selected_return_seats}")
        
        # Count infants and adults
        infant_count = sum(1 for p in passenger_data if p.get('title') == 'INF')
        adult_count = passengers - infant_count
        
        # Calculate lap infants (free, no seat) vs seated infants (need seat, 50% price)
        # Rule: First infant per adult gets lap (free), extra infants need seats
        lap_infant_count = min(infant_count, adult_count)  # Max 1 lap infant per adult
        seated_infant_count = infant_count - lap_infant_count  # Extra infants need seats
        
        # Passengers needing seats = adults + seated infants
        passengers_needing_seats = adult_count + seated_infant_count
        
        print(f"DEBUG - Infant breakdown: {lap_infant_count} lap (free), {seated_infant_count} seated (50% price)")
        print(f"DEBUG - Passengers needing seats: {passengers_needing_seats}")
        
        # Count actual seats selected (excluding "INFANT" placeholder)
        actual_outbound_seats = [s for s in selected_outbound_seats if s != 'INFANT']
        actual_return_seats = [s for s in selected_return_seats if s != 'INFANT']
        
        # Validate seat selection matches passengers needing seats
        if len(actual_outbound_seats) != passengers_needing_seats:
            return render_template('error.html', error=f"Please select exactly {passengers_needing_seats} outbound seat(s) ({adult_count} adults + {seated_infant_count} seated infants)")
        
        if trip_type == 'round_trip' and len(actual_return_seats) != passengers_needing_seats:
            return render_template('error.html', error=f"Please select exactly {passengers_needing_seats} return seat(s) ({adult_count} adults + {seated_infant_count} seated infants)")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Generate base timestamp for IDs
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            total_amount = 0
            
            # Function to generate Reservation ID using Oracle SEQUENCE (thread-safe, no race conditions)
            def generate_reservation_id(cursor):
                """Generate a unique Reservation ID using Oracle SEQUENCE.
                Format: IAT-YYYYMMDD-NNNNNN (e.g., IAT-20251204-100001)
                - IAT = Airline code
                - YYYYMMDD = Current date  
                - NNNNNN = 6-digit sequence number (100001-999999, cycles)
                """
                cursor.execute("""
                    SELECT 'IAT-' || TO_CHAR(SYSDATE, 'YYYYMMDD') || '-' || LPAD(Reservation_Seq.NEXTVAL, 6, '0') 
                    FROM DUAL
                """)
                res_id = cursor.fetchone()[0]
                print(f"DEBUG - Generated Reservation ID: {res_id}")
                return res_id
            
            # Legacy function for Payment ID (still uses timestamp-based)
            def generate_sequential_id(prefix, table_name, id_column, cursor):
                base_id = f"{prefix}{timestamp}"
                test_id = base_id
                counter = 1
                
                cursor.execute(f"SELECT 1 FROM {table_name} WHERE {id_column} = :id", id=test_id)
                while cursor.fetchone():
                    test_id = f"{base_id}_{counter}"
                    counter += 1
                    cursor.execute(f"SELECT 1 FROM {table_name} WHERE {id_column} = :id", id=test_id)
                
                print(f"DEBUG - Generated {prefix} ID: {test_id}")
                return test_id

            # Get flight details for pricing
            cursor.execute("""
                SELECT fi.Model_ID, fr.Route_ID 
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=outbound_flight_id)
            flight_info = cursor.fetchone()
            model_id = flight_info[0]
            route_id = flight_info[1]
            
            # Calculate total amount (same logic as before)
            cursor.execute("""
                SELECT Base_Price FROM Route_Pricing 
                WHERE Route_ID = :route_id 
                AND Class_ID = :class_id
                AND SYSDATE BETWEEN Valid_From AND Valid_To
            """, route_id=route_id, class_id=travel_class)
            
            pricing_result = cursor.fetchone()
            if pricing_result:
                base_price = pricing_result[0]
                # Calculate total: adults pay full, lap infants FREE, seated infants 50%
                total_amount = (base_price * adult_count) + (base_price * 0.5 * seated_infant_count)
            else:
                default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                base_price = default_costs.get(travel_class, 100)
                total_amount = (base_price * adult_count) + (base_price * 0.5 * seated_infant_count)
            
            print(f"DEBUG - Pricing: {adult_count} adults @ {base_price}, {lap_infant_count} lap infants @ FREE, {seated_infant_count} seated infants @ {base_price * 0.5}")
            
            # Add return flight cost if applicable
            if return_flight_id:
                cursor.execute("""
                    SELECT fr.Route_ID 
                    FROM Flight_Instance fi
                    JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                    WHERE fi.Instance_ID = :flight_id
                """, flight_id=return_flight_id)
                return_route_info = cursor.fetchone()
                return_route_id = return_route_info[0]
                
                cursor.execute("""
                    SELECT Base_Price FROM Route_Pricing 
                    WHERE Route_ID = :route_id 
                    AND Class_ID = :class_id
                    AND SYSDATE BETWEEN Valid_From AND Valid_To
                """, route_id=return_route_id, class_id=travel_class)
                
                return_pricing_result = cursor.fetchone()
                if return_pricing_result:
                    return_base_price = return_pricing_result[0]
                    # Return: adults full, lap infants FREE, seated infants 50%
                    total_amount += (return_base_price * adult_count) + (return_base_price * 0.5 * seated_infant_count)
                else:
                    default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                    return_base_price = default_costs.get(travel_class, 100)
                    total_amount += (return_base_price * adult_count) + (return_base_price * 0.5 * seated_infant_count)
            
            print(f"DEBUG - Total amount: {total_amount}")
            
            # Create booking - UPDATED to handle guest users (Lead_User_ID can be NULL)
            print(f"DEBUG - Creating booking with contact: {contact_email}, {contact_phone}")
            if lead_user_id:
                # Logged-in user
                cursor.execute("""
                    INSERT INTO Booking 
                    (Lead_User_ID, Booking_Date, Booking_Status, Contact_Email, Emergency_Phone)
                    VALUES (:user_id, SYSTIMESTAMP, 'CONFIRMED', :email, :phone)
                """, 
                user_id=lead_user_id,
                email=contact_email,
                phone=contact_phone)
            else:
                # Guest user - Lead_User_ID will be NULL
                cursor.execute("""
                    INSERT INTO Booking 
                    (Booking_Date, Booking_Status, Contact_Email, Emergency_Phone)
                    VALUES (SYSTIMESTAMP, 'CONFIRMED', :email, :phone)
                """, 
                email=contact_email,
                phone=contact_phone)
            
            # Get the auto-generated booking ID
            cursor.execute("SELECT Booking_ID FROM Booking WHERE Contact_Email = :email AND Emergency_Phone = :phone ORDER BY Booking_Date DESC FETCH FIRST 1 ROW ONLY", 
                         email=contact_email, phone=contact_phone)
            booking_result = cursor.fetchone()
            booking_id = booking_result[0]
            print(f"DEBUG - Generated Booking ID: {booking_id}")
            
            # =================================================================
            # Insert passengers with proper is_self and existing_passenger_id handling
            # IMPORTANT: If user modifies auto-filled details, create NEW passenger
            # to avoid corrupting stored profiles (own or family members')
            # =================================================================
            
            def details_match(stored, submitted):
                """Compare stored passenger data with submitted form data.
                Returns True if key identity fields match (allowing passport updates)."""
                # stored = (Passenger_ID, Title, First_Name, Last_Name, Gender, DOB_str, Passport)
                # Check key identity fields - name, gender, DOB must match exactly
                name_match = (stored[2].upper() == submitted['first_name'].upper() and 
                             stored[3].upper() == submitted['last_name'].upper())
                gender_match = stored[4].upper() == submitted['gender'].upper()
                # DOB comparison - stored is 'YYYY-MM-DD' string
                dob_match = stored[5] == submitted['date_of_birth']
                
                return name_match and gender_match and dob_match
            
            passenger_ids = []
            for i, passenger in enumerate(passenger_data):
                print(f"DEBUG - Processing passenger {i}: {passenger['first_name']} {passenger['last_name']} (Title: {passenger['title']})")
                
                # Get the flags from passenger data
                is_self = passenger.get('is_self', False)
                existing_passenger_id = passenger.get('existing_passenger_id')
                is_infant = passenger.get('title') == 'INF'
                
                print(f"DEBUG - is_self={is_self}, existing_id={existing_passenger_id}, is_infant={is_infant}")
                
                # CASE 1: existing_passenger_id provided (from "Add from Past Bookings" or "Add Myself")
                # Check if details were MODIFIED - if so, create NEW passenger instead of updating
                if existing_passenger_id:
                    # Fetch the stored passenger details to compare
                    cursor.execute("""
                        SELECT Passenger_ID, Title, First_Name, Last_Name, Gender, 
                               TO_CHAR(Date_Of_Birth, 'YYYY-MM-DD'), Passport_Num
                        FROM Passenger WHERE Passenger_ID = :pid
                    """, pid=existing_passenger_id)
                    stored_data = cursor.fetchone()
                    
                    if stored_data and details_match(stored_data, passenger):
                        # Details UNCHANGED - safe to reuse existing passenger
                        passenger_id = existing_passenger_id
                        print(f"DEBUG - Details unchanged, reusing existing passenger ID: {passenger_id}")
                        
                        # Only update passport if it changed (minor update allowed)
                        if stored_data[6] != passenger['passport_number']:
                            cursor.execute("""
                                UPDATE Passenger SET Passport_Num = :passport
                                WHERE Passenger_ID = :pid
                            """, passport=passenger['passport_number'], pid=passenger_id)
                            print(f"DEBUG - Updated passport for passenger {passenger_id}")
                        
                        passenger_ids.append(passenger_id)
                    else:
                        # Details MODIFIED - create NEW passenger to avoid corrupting stored profile
                        print(f"DEBUG - Details modified from stored profile, creating NEW passenger")
                        cursor.execute("""
                            INSERT INTO Passenger 
                            (First_Name, Last_Name, Date_Of_Birth, Gender, Passport_Num, Title)
                            VALUES (:first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :passport, :title)
                        """, 
                        first_name=passenger['first_name'],
                        last_name=passenger['last_name'],
                        dob=passenger['date_of_birth'],
                        gender=passenger['gender'],
                        passport=passenger['passport_number'],
                        title=passenger['title'])
                        
                        # Get the new passenger ID
                        cursor.execute("""
                            SELECT Passenger_ID FROM Passenger 
                            WHERE First_Name = :first_name 
                            AND Last_Name = :last_name 
                            AND Date_Of_Birth = TO_DATE(:dob, 'YYYY-MM-DD')
                            ORDER BY Passenger_ID DESC
                            FETCH FIRST 1 ROW ONLY
                        """, 
                        first_name=passenger['first_name'], 
                        last_name=passenger['last_name'], 
                        dob=passenger['date_of_birth'])
                        new_passenger = cursor.fetchone()
                        passenger_ids.append(new_passenger[0])
                        print(f"DEBUG - Created new passenger ID: {new_passenger[0]} (original was {existing_passenger_id})")
                    
                # CASE 2: User clicked "Add Myself" but doesn't have existing profile
                # AND the passenger is NOT an infant (infants should never be linked to users)
                elif is_self and lead_user_id and not is_infant:
                    # Check if user already has a linked passenger profile
                    cursor.execute("""
                        SELECT Passenger_ID, Title, First_Name, Last_Name, Gender,
                               TO_CHAR(Date_Of_Birth, 'YYYY-MM-DD'), Passport_Num
                        FROM Passenger WHERE Linked_User_ID = :user_id
                    """, user_id=lead_user_id)
                    existing_linked = cursor.fetchone()
                    
                    if existing_linked:
                        # User has a profile - check if details match
                        if details_match(existing_linked, passenger):
                            # Details match - reuse existing profile
                            passenger_id = existing_linked[0]
                            print(f"DEBUG - Details match linked profile, reusing passenger ID: {passenger_id}")
                            
                            # Only update passport if changed
                            if existing_linked[6] != passenger['passport_number']:
                                cursor.execute("""
                                    UPDATE Passenger SET Passport_Num = :passport
                                    WHERE Passenger_ID = :pid
                                """, passport=passenger['passport_number'], pid=passenger_id)
                            
                            passenger_ids.append(passenger_id)
                        else:
                            # Details modified - create NEW unlinked passenger
                            print(f"DEBUG - Details modified from linked profile, creating NEW passenger")
                            cursor.execute("""
                                INSERT INTO Passenger 
                                (First_Name, Last_Name, Date_Of_Birth, Gender, Passport_Num, Title)
                                VALUES (:first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :passport, :title)
                            """, 
                            first_name=passenger['first_name'],
                            last_name=passenger['last_name'],
                            dob=passenger['date_of_birth'],
                            gender=passenger['gender'],
                            passport=passenger['passport_number'],
                            title=passenger['title'])
                            
                            cursor.execute("""
                                SELECT Passenger_ID FROM Passenger 
                                WHERE First_Name = :first_name 
                                AND Last_Name = :last_name 
                                AND Date_Of_Birth = TO_DATE(:dob, 'YYYY-MM-DD')
                                ORDER BY Passenger_ID DESC
                                FETCH FIRST 1 ROW ONLY
                            """, 
                            first_name=passenger['first_name'], 
                            last_name=passenger['last_name'], 
                            dob=passenger['date_of_birth'])
                            new_passenger = cursor.fetchone()
                            passenger_ids.append(new_passenger[0])
                            print(f"DEBUG - Created new passenger ID: {new_passenger[0]}")
                    else:
                        # Create new profile linked to user
                        print(f"DEBUG - Creating NEW passenger profile linked to user {lead_user_id}")
                        cursor.execute("""
                            INSERT INTO Passenger 
                            (Linked_User_ID, First_Name, Last_Name, Date_Of_Birth, Gender, Passport_Num, Title)
                            VALUES (:user_id, :first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :passport, :title)
                        """, 
                        user_id=lead_user_id,
                        first_name=passenger['first_name'],
                        last_name=passenger['last_name'],
                        dob=passenger['date_of_birth'],
                        gender=passenger['gender'],
                        passport=passenger['passport_number'],
                        title=passenger['title'])
                        
                        # Get the generated passenger ID
                        cursor.execute("SELECT Passenger_ID FROM Passenger WHERE Linked_User_ID = :user_id", user_id=lead_user_id)
                        passenger_result = cursor.fetchone()
                        passenger_ids.append(passenger_result[0])
                        print(f"DEBUG - Created linked passenger ID: {passenger_result[0]}")
                        
                # CASE 3: Guest passenger, additional passenger, or infant
                # These should NEVER have Linked_User_ID set
                else:
                    print(f"DEBUG - Creating guest/additional passenger: {passenger['first_name']} {passenger['last_name']}")
                    cursor.execute("""
                        INSERT INTO Passenger 
                        (First_Name, Last_Name, Date_Of_Birth, Gender, Passport_Num, Title)
                        VALUES (:first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :passport, :title)
                    """, 
                    first_name=passenger['first_name'],
                    last_name=passenger['last_name'],
                    dob=passenger['date_of_birth'],
                    gender=passenger['gender'],
                    passport=passenger['passport_number'],
                    title=passenger['title'])
                    
                    # Get the generated passenger ID
                    cursor.execute("""
                        SELECT Passenger_ID FROM Passenger 
                        WHERE First_Name = :first_name 
                        AND Last_Name = :last_name 
                        AND Date_Of_Birth = TO_DATE(:dob, 'YYYY-MM-DD')
                        ORDER BY Passenger_ID DESC
                        FETCH FIRST 1 ROW ONLY
                    """, 
                    first_name=passenger['first_name'], 
                    last_name=passenger['last_name'], 
                    dob=passenger['date_of_birth'])
                    passenger_result = cursor.fetchone()
                    passenger_ids.append(passenger_result[0])
                    print(f"DEBUG - Created guest passenger ID: {passenger_result[0]}")
            
            # =================================================================
            # Create reservations for outbound flight
            # Uses FN_Get_Infant_Type for database-side infant type determination
            # SQL triggers handle price calculation automatically
            # =================================================================
            # Track seat index for passengers needing seats (adults + seated infants)
            seat_index = 0
            actual_outbound_seats = [s for s in selected_outbound_seats if s != 'INFANT']
            
            for i, passenger in enumerate(passenger_data):
                passenger_id = passenger_ids[i]
                is_infant = passenger.get('title') == 'INF'
                
                res_id = generate_reservation_id(cursor)
                
                if is_infant:
                    # Use FN_Get_Infant_Type to determine LAP_INFANT vs SEATED_INFANT
                    # This function uses database logic: 1 lap infant per adult, extras need seats
                    cursor.execute("""
                        SELECT FN_Get_Infant_Type(:booking_id, :instance_id, :passenger_id) FROM DUAL
                    """, booking_id=booking_id, instance_id=outbound_flight_id, passenger_id=passenger_id)
                    passenger_type = cursor.fetchone()[0]
                    
                    print(f"DEBUG - FN_Get_Infant_Type returned: {passenger_type} for passenger {passenger_id}")
                    
                    if passenger_type == 'LAP_INFANT':
                        # LAP_INFANT: free, no seat - SQL trigger TRG_Infant_Booking_Rules sets Price_Charged = 0
                        print(f"DEBUG - Creating outbound LAP_INFANT reservation: {res_id} (trigger sets price to FREE)")
                        
                        cursor.execute("""
                            INSERT INTO Reservation 
                            (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Passenger_Type)
                            VALUES (:res_id, :booking_id, :passenger_id, :instance_id, NULL, NULL, 0, :pax_type)
                        """, 
                        res_id=res_id,
                        booking_id=booking_id,
                        passenger_id=passenger_id,
                        instance_id=outbound_flight_id,
                        pax_type=passenger_type)
                    elif passenger_type == 'SEATED_INFANT':
                        # SEATED_INFANT: SQL trigger TRG_Infant_Booking_Rules auto-calculates 50% of base price
                        if seat_index >= len(actual_outbound_seats):
                            print(f"ERROR - Not enough seats for seated infant {i}")
                            continue
                        
                        seat_simple = actual_outbound_seats[seat_index]
                        seat_index += 1
                        
                        # Parse seat information
                        row_match = re.search(r'\d+', seat_simple)
                        letter_match = re.search(r'[A-Z]', seat_simple)
                        
                        if not row_match or not letter_match:
                            print(f"ERROR - Invalid seat format: {seat_simple}")
                            continue
                        
                        row_num = int(row_match.group())
                        seat_letter = letter_match.group()
                        
                        # Use FN_Get_Infant_Price to get the 50% price
                        cursor.execute("""
                            SELECT FN_Get_Infant_Price(:instance_id, 'SEATED_INFANT', :class_id) FROM DUAL
                        """, instance_id=outbound_flight_id, class_id=travel_class)
                        infant_price = cursor.fetchone()[0] or 0
                        
                        print(f"DEBUG - Creating outbound SEATED_INFANT reservation: {res_id} for seat {row_num}{seat_letter} (FN_Get_Infant_Price returned: {infant_price})")
                        
                        # Pass calculated price - trigger will also verify/recalculate if needed
                        cursor.execute("""
                            INSERT INTO Reservation 
                            (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Passenger_Type)
                            VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price, :pax_type)
                        """, 
                        res_id=res_id,
                        booking_id=booking_id,
                        passenger_id=passenger_id,
                        instance_id=outbound_flight_id,
                        row_num=row_num,
                        seat_letter=seat_letter,
                        price=infant_price,
                        pax_type=passenger_type)
                else:
                    # ADULT: Regular passenger, full price, needs seat
                    passenger_type = 'ADULT'
                    
                    if seat_index >= len(actual_outbound_seats):
                        print(f"ERROR - Not enough seats for passenger {i}")
                        continue
                    
                    seat_simple = actual_outbound_seats[seat_index]
                    seat_index += 1
                    
                    # Parse seat information
                    row_match = re.search(r'\d+', seat_simple)
                    letter_match = re.search(r'[A-Z]', seat_simple)
                    
                    if not row_match or not letter_match:
                        print(f"ERROR - Invalid seat format: {seat_simple}")
                        continue
                    
                    row_num = int(row_match.group())
                    seat_letter = letter_match.group()
                    
                    # Verify seat exists in aircraft model (TRG_Validate_Seat_Exists trigger also validates this)
                    cursor.execute("""
                        SELECT 1 FROM Aircraft_Seat_Map 
                        WHERE Model_ID = :model_id 
                        AND Row_Number = :row_num 
                        AND Seat_Letter = :seat_letter
                    """, model_id=model_id, row_num=row_num, seat_letter=seat_letter)
                    
                    if not cursor.fetchone():
                        print(f"ERROR - Seat {seat_simple} not found in aircraft model {model_id}")
                        continue
                    
                    # Get seat price
                    cursor.execute("""
                        SELECT Base_Price FROM Route_Pricing 
                        WHERE Route_ID = :route_id 
                        AND Class_ID = :class_id
                        AND SYSDATE BETWEEN Valid_From AND Valid_To
                    """, route_id=route_id, class_id=travel_class)
                    
                    seat_price_result = cursor.fetchone()
                    seat_price = seat_price_result[0] if seat_price_result else base_price
                    
                    print(f"DEBUG - Creating outbound ADULT reservation {i}: {res_id} for seat {row_num}{seat_letter}")
                    
                    cursor.execute("""
                        INSERT INTO Reservation 
                        (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Passenger_Type)
                        VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price, :pax_type)
                    """, 
                    res_id=res_id,
                    booking_id=booking_id,
                    passenger_id=passenger_id,
                    instance_id=outbound_flight_id,
                    row_num=row_num,
                    seat_letter=seat_letter,
                    price=seat_price,
                    pax_type=passenger_type)
            
            # Create reservations for return flight if applicable
            # Uses FN_Get_Infant_Type for database-side infant type determination
            if return_flight_id:
                cursor.execute("""
                    SELECT fi.Model_ID, fr.Route_ID 
                    FROM Flight_Instance fi
                    JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                    WHERE fi.Instance_ID = :flight_id
                """, flight_id=return_flight_id)
                return_flight_info = cursor.fetchone()
                return_model_id = return_flight_info[0]
                return_route_id = return_flight_info[1]
                
                # Get return base price
                cursor.execute("""
                    SELECT Base_Price FROM Route_Pricing 
                    WHERE Route_ID = :route_id 
                    AND Class_ID = :class_id
                    AND SYSDATE BETWEEN Valid_From AND Valid_To
                """, route_id=return_route_id, class_id=travel_class)
                return_pricing = cursor.fetchone()
                return_base_price = return_pricing[0] if return_pricing else base_price
                
                # Track seat index for passengers needing seats (adults + seated infants)
                return_seat_index = 0
                actual_return_seats = [s for s in selected_return_seats if s != 'INFANT']
                
                for i, passenger in enumerate(passenger_data):
                    passenger_id = passenger_ids[i]
                    is_infant = passenger.get('title') == 'INF'
                    
                    res_id = generate_reservation_id(cursor)
                    
                    if is_infant:
                        # Use FN_Get_Infant_Type to determine LAP_INFANT vs SEATED_INFANT for return flight
                        cursor.execute("""
                            SELECT FN_Get_Infant_Type(:booking_id, :instance_id, :passenger_id) FROM DUAL
                        """, booking_id=booking_id, instance_id=return_flight_id, passenger_id=passenger_id)
                        passenger_type = cursor.fetchone()[0]
                        
                        print(f"DEBUG - FN_Get_Infant_Type for return flight returned: {passenger_type} for passenger {passenger_id}")
                        
                        if passenger_type == 'LAP_INFANT':
                            # LAP_INFANT: free, no seat - SQL trigger TRG_Infant_Booking_Rules sets Price_Charged = 0
                            print(f"DEBUG - Creating return LAP_INFANT reservation: {res_id} (trigger sets price to FREE)")
                            
                            cursor.execute("""
                                INSERT INTO Reservation 
                                (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Passenger_Type)
                                VALUES (:res_id, :booking_id, :passenger_id, :instance_id, NULL, NULL, 0, :pax_type)
                            """, 
                            res_id=res_id,
                            booking_id=booking_id,
                            passenger_id=passenger_id,
                            instance_id=return_flight_id,
                            pax_type=passenger_type)
                        elif passenger_type == 'SEATED_INFANT':
                            # SEATED_INFANT: Use FN_Get_Infant_Price to get 50% price
                            if return_seat_index >= len(actual_return_seats):
                                print(f"ERROR - Not enough return seats for seated infant {i}")
                                continue
                            
                            seat_simple = actual_return_seats[return_seat_index]
                            return_seat_index += 1
                            
                            # Parse seat information
                            row_match = re.search(r'\d+', seat_simple)
                            letter_match = re.search(r'[A-Z]', seat_simple)
                            
                            if not row_match or not letter_match:
                                print(f"ERROR - Invalid return seat format: {seat_simple}")
                                continue
                            
                            row_num = int(row_match.group())
                            seat_letter = letter_match.group()
                            
                            # Use FN_Get_Infant_Price to calculate 50% price
                            cursor.execute("""
                                SELECT FN_Get_Infant_Price(:instance_id, 'SEATED_INFANT', :class_id) FROM DUAL
                            """, instance_id=return_flight_id, class_id=travel_class)
                            infant_price = cursor.fetchone()[0] or 0
                            
                            print(f"DEBUG - Creating return SEATED_INFANT reservation: {res_id} for seat {row_num}{seat_letter} (FN_Get_Infant_Price returned: {infant_price})")
                            
                            cursor.execute("""
                                INSERT INTO Reservation 
                                (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Passenger_Type)
                                VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price, :pax_type)
                            """, 
                            res_id=res_id,
                            booking_id=booking_id,
                            passenger_id=passenger_id,
                            instance_id=return_flight_id,
                            row_num=row_num,
                            seat_letter=seat_letter,
                            price=infant_price,
                            pax_type=passenger_type)
                    else:
                        # ADULT: Regular passenger, full price, needs seat
                        passenger_type = 'ADULT'
                        
                        if return_seat_index >= len(actual_return_seats):
                            print(f"ERROR - Not enough return seats for passenger {i}")
                            continue
                        
                        seat_simple = actual_return_seats[return_seat_index]
                        return_seat_index += 1
                        
                        # Parse seat information
                        row_match = re.search(r'\d+', seat_simple)
                        letter_match = re.search(r'[A-Z]', seat_simple)
                        
                        if not row_match or not letter_match:
                            print(f"ERROR - Invalid return seat format: {seat_simple}")
                            continue
                        
                        row_num = int(row_match.group())
                        seat_letter = letter_match.group()
                        
                        # Verify seat exists in return aircraft model
                        cursor.execute("""
                            SELECT 1 FROM Aircraft_Seat_Map 
                            WHERE Model_ID = :model_id 
                            AND Row_Number = :row_num 
                            AND Seat_Letter = :seat_letter
                        """, model_id=return_model_id, row_num=row_num, seat_letter=seat_letter)
                        
                        if not cursor.fetchone():
                            print(f"ERROR - Return seat {seat_simple} not found in aircraft model {return_model_id}")
                            continue
                        
                        # Get return seat price
                        cursor.execute("""
                            SELECT Base_Price FROM Route_Pricing 
                            WHERE Route_ID = :route_id 
                            AND Class_ID = :class_id
                            AND SYSDATE BETWEEN Valid_From AND Valid_To
                        """, route_id=return_route_id, class_id=travel_class)
                        
                        return_seat_price_result = cursor.fetchone()
                        return_seat_price = return_seat_price_result[0] if return_seat_price_result else return_base_price
                        
                        print(f"DEBUG - Creating return ADULT reservation {i}: {res_id} for seat {row_num}{seat_letter}")
                        
                        cursor.execute("""
                            INSERT INTO Reservation 
                            (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Passenger_Type)
                            VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price, :pax_type)
                        """, 
                        res_id=res_id,
                        booking_id=booking_id,
                        passenger_id=passenger_id,
                        instance_id=return_flight_id,
                        row_num=row_num,
                        seat_letter=seat_letter,
                        price=return_seat_price,
                        pax_type=passenger_type)
            
            # Get actual total from database (prices set by SQL trigger)
            cursor.execute("""
                SELECT NVL(SUM(Price_Charged), 0) FROM Reservation WHERE Booking_ID = :booking_id
            """, booking_id=booking_id)
            actual_total = cursor.fetchone()[0]
            print(f"DEBUG - Actual total from database (trigger-calculated): {actual_total}")
            
            # Create initial payment record with actual total from trigger
            payment_id = generate_sequential_id("PAY", "Payment", "Payment_ID", cursor)
            cursor.execute("""
                INSERT INTO Payment 
                (Payment_ID, Booking_ID, Amount_Paid, Payment_Date, Payment_Method)
                VALUES (:payment_id, :booking_id, :amount, SYSTIMESTAMP, 'CREDIT_CARD')
            """,
            payment_id=payment_id,
            booking_id=booking_id,
            amount=actual_total)
            
            conn.commit()
            print(f"DEBUG - All database operations completed successfully!")
            
            # Clear session data
            session.pop('passenger_data', None)
            session.pop('contact_email', None)
            session.pop('contact_phone', None)
            session.pop('selected_outbound_seats', None)
            session.pop('selected_return_seats', None)
            session.pop('selected_outbound_flight', None)
            session.pop('selected_return_flight', None)
            session.pop('search_travel_class', None)
            session.pop('search_trip_type', None)
            session.pop('travel_class', None)
            session.pop('passengers', None)
            session.pop('trip_type', None)
            
            return redirect(url_for('booking_confirmation', 
                        booking_id=booking_id, 
                        passenger_count=passengers,
                        total_amount=actual_total,
                        auto_download='true'))
            
        except Exception as e:
            conn.rollback()
            print("Database error during booking:", e)
            print("Error type:", type(e).__name__)
            
            error_msg = f"Booking failed: {str(e)}"
            if "unique constraint" in str(e):
                error_msg += ". This usually means the booking reference already exists. Please try again."
            elif "parent key not found" in str(e):
                error_msg += ". This usually means a seat or passenger reference is invalid."
            return render_template('error.html', error=error_msg)
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print("Booking processing error:", e)
        return render_template('error.html', error="Booking processing failed.")
    

@app.route('/download-tickets/<booking_id>')
def download_tickets(booking_id):
    """Download all tickets for a booking as a ZIP file"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # First, get the original departure airport for this booking
        cursor.execute("""
            SELECT fr.Source_Airport
            FROM Booking b
            JOIN Reservation r ON b.Booking_ID = r.Booking_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            WHERE b.Booking_ID = :booking_id
            AND ROWNUM = 1
        """, booking_id=booking_id)
        
        original_departure_result = cursor.fetchone()
        original_departure = original_departure_result[0] if original_departure_result else 'KHI'
        
        print(f"DEBUG - Original departure for booking {booking_id}: {original_departure}")
        
        # Get booking and passenger details - SEPARATE OUTBOUND AND RETURN
        cursor.execute("""
            SELECT 
                b.Booking_ID, 
                p.Passenger_ID, p.First_Name, p.Last_Name, p.Title,
                r.Reservation_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                fi.Instance_ID, fi.Model_ID,
                TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI'),
                TO_CHAR(fi.Arrival_Time, 'DD-MON-YYYY HH24:MI'),
                a1.Airport_Name, a2.Airport_Name,
                c1.City_Name, c2.City_Name,
                arc.Class_ID,
                fr.Source_Airport, fr.Dest_Airport,
                -- Determine if this is outbound or return
                CASE 
                    WHEN fr.Source_Airport = :original_departure THEN 'OUTBOUND'
                    ELSE 'RETURN'
                END as Flight_Type
            FROM Booking b
            JOIN Reservation r ON b.Booking_ID = r.Booking_ID
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND r.Row_Number = arc.Row_Number
            WHERE b.Booking_ID = :booking_id
            ORDER BY fi.Departure_Time, p.Last_Name
        """, booking_id=booking_id, original_departure=original_departure)
        
        booking_data = cursor.fetchall()
        
        if not booking_data:
            return render_template('error.html', error="Booking not found")
        
        # Organize data by flight type
        outbound_data = []
        return_data = []
        
        for row in booking_data:
            reservation = {
                'booking_id': row[0],
                'passenger_id': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'title': row[4],
                'reservation_id': row[5],
                'row_number': row[6],
                'seat_letter': row[7],
                'seat_cost': float(row[8]),
                'instance_id': row[9],
                'model_id': row[10],
                'departure_time': row[11],
                'arrival_time': row[12],
                'departure_airport': row[13],
                'arrival_airport': row[14],
                'departure_city': row[15],
                'arrival_city': row[16],
                'travel_class': row[17],
                'source_airport': row[18],
                'dest_airport': row[19],
                'flight_type': row[20],  # This tells us if it's OUTBOUND or RETURN
                'seat_number': f"{row[6]}{row[7]}",
                'flight_date': row[11].split(' ')[0] if row[11] else 'N/A'
            }
            
            print(f"DEBUG - Reservation {reservation['reservation_id']}: {reservation['departure_city']} to {reservation['arrival_city']} - Type: {reservation['flight_type']}")
            
            if row[20] == 'OUTBOUND':
                outbound_data.append(reservation)
            else:
                return_data.append(reservation)
        
        print(f"DEBUG - Outbound flights: {len(outbound_data)}, Return flights: {len(return_data)}")
        
        # Generate tickets for outbound flights
        ticket_gen = TicketGenerator()
        all_tickets = []
        
        # Process outbound flights
        if outbound_data:
            outbound_booking_data = {
                'booking_id': outbound_data[0]['booking_id'],
                'passengers': outbound_data,
                'outbound_flight_number': outbound_data[0]['instance_id'],
                'departure_city': outbound_data[0]['departure_city'],
                'arrival_city': outbound_data[0]['arrival_city'],
                'departure_time': outbound_data[0]['departure_time'],
                'arrival_time': outbound_data[0]['arrival_time'],
                'flight_date': outbound_data[0]['flight_date'],
                'travel_class': outbound_data[0]['travel_class'],
                'aircraft_type': outbound_data[0]['model_id'],
                'flight_type': 'OUTBOUND'
            }
            outbound_tickets = ticket_gen.generate_all_tickets(outbound_booking_data, "temp_tickets")
            all_tickets.extend(outbound_tickets)
            print(f"DEBUG - Generated {len(outbound_tickets)} outbound tickets")
        
        # Process return flights  
        if return_data:
            return_booking_data = {
                'booking_id': return_data[0]['booking_id'],
                'passengers': return_data,
                'return_flight_number': return_data[0]['instance_id'],
                'return_departure_city': return_data[0]['departure_city'],
                'return_arrival_city': return_data[0]['arrival_city'],
                'return_departure_time': return_data[0]['departure_time'],
                'return_arrival_time': return_data[0]['arrival_time'],
                'return_flight_date': return_data[0]['flight_date'],
                'travel_class': return_data[0]['travel_class'],
                'return_aircraft_type': return_data[0]['model_id'],
                'flight_type': 'RETURN'
            }
            return_tickets = ticket_gen.generate_all_tickets(return_booking_data, "temp_tickets")
            all_tickets.extend(return_tickets)
            print(f"DEBUG - Generated {len(return_tickets)} return tickets")
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for ticket_file in all_tickets:
                zipf.write(ticket_file, os.path.basename(ticket_file))
        
        zip_buffer.seek(0)
        
        # Clean up temporary files
        for ticket_file in all_tickets:
            try:
                os.remove(ticket_file)
            except:
                pass
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'tickets_{booking_id}.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        print("Error generating tickets:", e)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error="Error generating tickets")
    
    finally:
        cursor.close()
        conn.close()

@app.route('/view-ticket/<reservation_id>')
def view_ticket(reservation_id):
    """View a single ticket"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT r.Reservation_ID, r.Booking_ID, r.Passenger_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title,
                   fi.Instance_ID, fi.Model_ID,
                   TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI'),
                   TO_CHAR(fi.Arrival_Time, 'DD-MON-YYYY HH24:MI'),
                   a1.Airport_Name, a2.Airport_Name,
                   c1.City_Name, c2.City_Name,
                   arc.Class_ID
            FROM Reservation r
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND r.Row_Number = arc.Row_Number
            WHERE r.Reservation_ID = :reservation_id
        """, reservation_id=reservation_id)
        
        ticket_data = cursor.fetchone()
        
        if not ticket_data:
            return render_template('error.html', error="Ticket not found")
        
        # Prepare data for ticket template
        context = {
            'reservation_id': ticket_data[0],
            'booking_id': ticket_data[1],
            'passenger_id': ticket_data[2],
            'row_number': ticket_data[3],
            'seat_letter': ticket_data[4],
            'seat_cost': float(ticket_data[5]),
            'passenger_name': f"{ticket_data[6]} {ticket_data[7]}",
            'title': ticket_data[8],
            'seat_number': f"{ticket_data[3]}{ticket_data[4]}",
            'flight_number': ticket_data[9],
            'aircraft_type': ticket_data[10],
            'departure_time': ticket_data[11],
            'arrival_time': ticket_data[12],
            'departure_airport': ticket_data[13],
            'arrival_airport': ticket_data[14],
            'departure_city': ticket_data[15],
            'arrival_city': ticket_data[16],
            'travel_class': ticket_data[17],
            'flight_date': ticket_data[11].split(' ')[0],
            'ticket_id': f"TKT{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }
        
        return render_template('ticket_template.html', **context)
        
    except Exception as e:
        print("Error viewing ticket:", e)
        return render_template('error.html', error="Error loading ticket")
    
    finally:
        cursor.close()
        conn.close()

@app.route('/booking-confirmation')
def booking_confirmation():
    """Display booking confirmation page and trigger automatic download"""
    booking_id = request.args.get('booking_id')
    passenger_count = request.args.get('passenger_count')
    total_amount = request.args.get('total_amount')
    auto_download = request.args.get('auto_download', 'true')  # Default to true for first visit
    
    if not booking_id:
        return render_template('error.html', error="Booking confirmation data missing")
    
    # Store booking info in session for auto-download detection
    session['last_booking_id'] = booking_id
    session['auto_download'] = auto_download == 'true'
    
    return render_template('booking_confirmation.html', 
                          booking_id=booking_id,
                          passenger_count=passenger_count,
                          total_amount=total_amount,
                          auto_download=auto_download == 'true')

@app.route('/manage-bookings')
def manage_bookings():
    return render_template('manage_bookings.html')

@app.route('/verify-booking', methods=['POST'])
def verify_booking():
    booking_id = request.form.get('booking_id')
    email = request.form.get('email')
    action_type = request.form.get('action_type')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verify booking exists and email matches - UPDATED
        cursor.execute("""
            SELECT b.Booking_ID, b.Booking_Status, b.Contact_Email, b.Emergency_Phone
            FROM Booking b
            WHERE b.Booking_ID = :booking_id 
            AND (b.Contact_Email = :email OR b.Emergency_Phone = :email)
        """, booking_id=booking_id, email=email)
        
        booking = cursor.fetchone()
        if not booking:
            return render_template('error.html', error="Booking not found or contact information doesn't match")
        
        # Get all ACTIVE reservations for this booking (exclude cancelled ones)
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title,
                   fi.Departure_Time, fi.Arrival_Time,
                   a1.Airport_Name as Departure_Airport, a2.Airport_Name as Arrival_Airport,
                   c1.City_Name as Departure_City, c2.City_Name as Arrival_City,
                   arc.Class_ID as Travel_Class
            FROM Reservation r
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND r.Row_Number = arc.Row_Number
            WHERE r.Booking_ID = :booking_id
            AND r.Ticket_Status != 'CANCELLED'
            ORDER BY fi.Departure_Time
        """, booking_id=booking_id)
        
        reservations = cursor.fetchall()
        
        # Convert to list of dictionaries for easier template handling
        reservation_list = []
        for res in reservations:
            reservation_list.append({
                'reservation_id': res[0],
                'passenger_id': res[1],
                'instance_id': res[2],
                'row_number': res[3],
                'seat_letter': res[4],
                'seat_cost': float(res[5]),
                'passenger_name': f"{res[6]} {res[7]}",
                'title': res[8],
                'departure_time': res[9].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'departure_airport': res[11],
                'arrival_airport': res[12],
                'departure_city': res[13],
                'arrival_city': res[14],
                'travel_class': res[15],
                'seat_number': f"{res[3]}{res[4]}"
            })
        
        booking_info = {
            'booking_id': booking[0],
            'booking_status': booking[1],
            'contact_email': booking[2],
            'contact_phone': booking[3]
        }
        
        # Store in session for next steps
        session['manage_booking_info'] = {
            'email': email,
            'booking_id': booking_id,
            'action_type': action_type
        }
        
        return render_template('booking_actions.html',
                             booking_info=booking_info,
                             reservations=reservation_list,
                             email=email,
                             action_type=action_type)
        
    except Exception as e:
        print("Error verifying booking:", e)
        return render_template('error.html', error="Error retrieving booking details")
    finally:
        cursor.close()
        conn.close()

@app.route('/process-booking-action', methods=['POST'])
def process_booking_action():
    email = request.form.get('email')
    booking_id = request.form.get('booking_id')
    action_type = request.form.get('action_type')
    selected_reservations = request.form.getlist('selected_reservations')
    
    if not selected_reservations:
        return render_template('error.html', error="No reservations selected")
    
    session['selected_reservations'] = selected_reservations
    session['action_booking_id'] = booking_id
    session['action_email'] = email
    
    if action_type == 'cancel':
        return cancel_reservations(selected_reservations, booking_id, email)
    elif action_type == 'reschedule':
        return redirect_to_reschedule(selected_reservations[0])  # Start with first reservation

def cancel_reservations(reservation_ids, booking_id, email):
    """
    Cancel multiple reservations using USP_Cancel_Reservation stored procedure.
    
    IMPORTANT: When cancelling, ALL passengers on the same flight instance 
    within the same booking are cancelled together (not just the selected ones).
    This ensures the entire group's reservation is cancelled as a unit.
    
    The procedure handles:
    - Refund calculation via FN_Calculate_Refund (80% if >24h before departure)
    - Updating Ticket_Status to CANCELLED
    - Freeing seats (Row_Number/Seat_Letter = NULL)
    - Triggers handle booking status update and logging automatically
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get all unique flight instances from selected reservations
        # Then get ALL reservations for those flight instances in this booking
        # This ensures all passengers on the same flight get cancelled together
        
        placeholders = ','.join([f':res{i}' for i in range(len(reservation_ids))])
        bind_vars = {f'res{i}': res_id for i, res_id in enumerate(reservation_ids)}
        bind_vars['booking_id'] = booking_id
        
        # Find all reservations for the same flight instances within this booking
        cursor.execute(f"""
            SELECT DISTINCT r2.Reservation_ID
            FROM Reservation r1
            JOIN Reservation r2 ON r1.Instance_ID = r2.Instance_ID 
                                AND r1.Booking_ID = r2.Booking_ID
            WHERE r1.Reservation_ID IN ({placeholders})
            AND r2.Booking_ID = :booking_id
            AND r2.Ticket_Status != 'CANCELLED'
        """, bind_vars)
        
        # Get all reservation IDs to cancel (includes all passengers on same flights)
        all_reservation_ids = [row[0] for row in cursor.fetchall()]
        
        print(f"DEBUG - Selected reservations: {reservation_ids}")
        print(f"DEBUG - All reservations to cancel (same flights): {all_reservation_ids}")
        
        total_refund = 0
        cancelled_count = 0
        
        for res_id in all_reservation_ids:
            # Call stored procedure - it handles all cancellation logic
            refund_amount = cursor.var(oracledb.NUMBER)
            success = cursor.var(oracledb.NUMBER)
            
            cursor.callproc('USP_Cancel_Reservation', [
                res_id,           # p_Reservation_ID
                refund_amount,    # p_Refund_Amount OUT
                success           # p_Success OUT
            ])
            
            # Check if cancellation was successful
            if success.getvalue() == 1:
                total_refund += float(refund_amount.getvalue() or 0)
                cancelled_count += 1
                print(f"DEBUG - Cancelled reservation {res_id}, refund: {refund_amount.getvalue()}")
            else:
                print(f"DEBUG - Failed to cancel reservation {res_id}")
        
        # Commit all cancellations as a single transaction
        conn.commit()
        
        # Clear session
        session.pop('selected_reservations', None)
        session.pop('action_booking_id', None)
        session.pop('action_email', None)
        
        return render_template('cancellation_confirmation.html',
                             booking_id=booking_id,
                             cancelled_count=cancelled_count,
                             total_refund=total_refund)
        
    except Exception as e:
        conn.rollback()
        print("Error during cancellation:", e)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error="Cancellation failed")
    finally:
        cursor.close()
        conn.close()

def redirect_to_reschedule(reservation_id):
    """
    Redirect to reschedule flow. When rescheduling, ALL passengers on the same
    flight instance from the same booking should be rescheduled together.
    Passenger info is pre-filled from existing reservation data.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # First, get the booking_id and instance_id from the selected reservation
        cursor.execute("""
            SELECT Booking_ID, Instance_ID FROM Reservation WHERE Reservation_ID = :res_id
        """, res_id=reservation_id)
        base_info = cursor.fetchone()
        
        if not base_info:
            return render_template('error.html', error="Reservation not found")
        
        booking_id = base_info[0]
        instance_id = base_info[1]
        
        # Get ALL active reservations for the same booking AND same flight instance
        # This ensures all passengers on this flight get rescheduled together
        cursor.execute("""
            SELECT r.Reservation_ID, r.Booking_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Gender, TO_CHAR(p.Date_Of_Birth, 'YYYY-MM-DD'), p.Passport_Num,
                   p.Linked_User_ID, r.Passenger_Type,
                   fi.Model_ID, fr.Source_Airport, fr.Dest_Airport,
                   fi.Departure_Time, fi.Arrival_Time,
                   a1.Airport_Name as Departure_Airport, a2.Airport_Name as Arrival_Airport,
                   c1.City_Name as Departure_City, c2.City_Name as Arrival_City,
                   arc.Class_ID as Travel_Class
            FROM Reservation r
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND r.Row_Number = arc.Row_Number
            WHERE r.Booking_ID = :booking_id
            AND r.Instance_ID = :instance_id
            AND r.Ticket_Status != 'CANCELLED'
            ORDER BY r.Reservation_ID
        """, booking_id=booking_id, instance_id=instance_id)
        
        all_reservations = cursor.fetchall()
        
        if not all_reservations:
            return render_template('error.html', error="No active reservations found")
        
        # Use first reservation's flight info as the "original flight" for display
        original_flight = all_reservations[0]
        
        original_flight_info = {
            'reservation_id': original_flight[0],
            'booking_id': original_flight[1],
            'passenger_id': original_flight[2],
            'instance_id': original_flight[3],
            'row_number': original_flight[4],
            'seat_letter': original_flight[5],
            'price_charged': float(original_flight[6]),
            'passenger_name': f"{original_flight[7]} {original_flight[8]}",
            'title': original_flight[9],
            'model_id': original_flight[15],
            'departure_airport_id': original_flight[16],
            'arrival_airport_id': original_flight[17],
            'departure_time': original_flight[18].strftime('%d-%b-%Y %H:%M'),
            'arrival_time': original_flight[19].strftime('%d-%b-%Y %H:%M'),
            'departure_airport': original_flight[20],
            'arrival_airport': original_flight[21],
            'departure_city': original_flight[22],
            'arrival_city': original_flight[23],
            'travel_class': original_flight[24],
            'departure_date': original_flight[18].strftime('%Y-%m-%d'),
            'total_passengers': len(all_reservations)  # Show how many passengers
        }
        
        # Build passenger data list for session (pre-fill passenger info)
        # This way, seat selection will have all passenger data ready
        passenger_data = []
        reschedule_reservation_ids = []
        
        for res in all_reservations:
            reschedule_reservation_ids.append(res[0])  # Reservation ID
            passenger_data.append({
                'first_name': res[7],
                'last_name': res[8],
                'title': res[9],
                'gender': res[10],
                'date_of_birth': res[11],
                'passport_number': res[12] or '',
                'existing_passenger_id': res[2],  # Passenger ID
                'is_self': res[13] is not None,   # Has linked user
                'passenger_type': res[14],         # ADULT or INFANT
                'original_reservation_id': res[0]  # For tracking which reservation to update
            })
        
        # Get booking contact info for session
        cursor.execute("""
            SELECT Contact_Email, Emergency_Phone FROM Booking WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        booking_contact = cursor.fetchone()
        
        # Store everything in session for the reschedule flow
        session['reschedule_original_booking'] = booking_id
        session['reschedule_reservation_ids'] = reschedule_reservation_ids  # ALL reservation IDs
        session['reschedule_passenger_data'] = passenger_data  # Pre-filled passenger info
        session['reschedule_travel_class'] = original_flight[24]  # Keep same travel class
        session['contact_email'] = booking_contact[0] if booking_contact else ''
        session['contact_phone'] = booking_contact[1] if booking_contact else ''
        
        print(f"DEBUG - Reschedule: {len(all_reservations)} passengers on flight {instance_id}")
        print(f"DEBUG - Reservation IDs: {reschedule_reservation_ids}")
        
        return render_template('reschedule_flights.html',
                             original_flight=original_flight_info,
                             reservation_id=reservation_id,
                             original_booking_id=booking_id,
                             passenger_count=len(all_reservations),
                             min_date=datetime.now().strftime('%Y-%m-%d'))
        
    except Exception as e:
        print("Error preparing reschedule:", e)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error="Error preparing reschedule")
    finally:
        cursor.close()
        conn.close()

@app.route('/search-reschedule-flights', methods=['POST'])
def search_reschedule_flights():
    # This route uses the same logic as search_flights but stores reschedule context
    reservation_id = request.form.get('reservation_id')
    original_booking_id = request.form.get('original_booking_id')
    
    # Store reschedule context in session
    session['reschedule_context'] = {
        'reservation_id': reservation_id,
        'original_booking_id': original_booking_id
    }
    
    # Use the existing search_flights logic but with reschedule context
    return search_flights()

@app.route('/select-reschedule-flight/<flight_id>')
def select_reschedule_flight(flight_id):
    """
    Handle flight selection for reschedule.
    Sets up session with pre-filled passenger data from original reservations.
    """
    # Get reschedule context from session
    reschedule_context = session.get('reschedule_context', {})
    reservation_id = reschedule_context.get('reservation_id')
    original_booking_id = session.get('reschedule_original_booking')
    
    if not reservation_id and not original_booking_id:
        return render_template('error.html', error="Reschedule session expired")
    
    # Get pre-filled passenger data from redirect_to_reschedule
    reschedule_passenger_data = session.get('reschedule_passenger_data', [])
    reschedule_reservation_ids = session.get('reschedule_reservation_ids', [])
    reschedule_travel_class = session.get('reschedule_travel_class', 'ECO')
    
    if not reschedule_passenger_data:
        return render_template('error.html', error="Reschedule passenger data not found")
    
    # Store the new flight selection for reschedule
    session['reschedule_new_flight'] = flight_id
    session['reschedule_reservation_id'] = reservation_id or reschedule_reservation_ids[0]
    
    # Set up session for seat_selection with pre-filled passenger data
    session['passenger_data'] = reschedule_passenger_data  # Pre-filled from original reservations
    session['passengers'] = len(reschedule_passenger_data)  # All passengers on this flight
    session['travel_class'] = reschedule_travel_class
    session['trip_type'] = 'one_way'  # Reschedule is always one-way
    session['selected_outbound_flight'] = flight_id
    session['is_reschedule'] = True
    
    print(f"DEBUG - Reschedule flight selected: {flight_id}")
    print(f"DEBUG - Passengers to reschedule: {len(reschedule_passenger_data)}")
    
    # Redirect to seat selection for the new flight
    return redirect(url_for('seat_selection'))

@app.route('/booking-actions')
def booking_actions():
    """Route to handle booking actions page"""
    # Get booking info from session
    manage_booking_info = session.get('manage_booking_info', {})
    
    if not manage_booking_info:
        return redirect(url_for('manage_bookings'))
    
    email = manage_booking_info.get('email')
    booking_id = manage_booking_info.get('booking_id')
    action_type = manage_booking_info.get('action_type')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get booking info - UPDATED
        cursor.execute("""
            SELECT Booking_ID, Booking_Status, Contact_Email, Emergency_Phone 
            FROM Booking 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        booking = cursor.fetchone()
        if not booking:
            return render_template('error.html', error="Booking not found")
        
        # Get all ACTIVE reservations for this booking (exclude cancelled ones)
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title,
                   fi.Departure_Time, fi.Arrival_Time,
                   a1.Airport_Name as Departure_Airport, a2.Airport_Name as Arrival_Airport,
                   c1.City_Name as Departure_City, c2.City_Name as Arrival_City,
                   arc.Class_ID as Travel_Class
            FROM Reservation r
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND r.Row_Number = arc.Row_Number
            WHERE r.Booking_ID = :booking_id
            AND r.Ticket_Status != 'CANCELLED'
            ORDER BY fi.Departure_Time
        """, booking_id=booking_id)
        
        reservations = cursor.fetchall()
        
        # Convert to list of dictionaries for easier template handling
        reservation_list = []
        for res in reservations:
            reservation_list.append({
                'reservation_id': res[0],
                'passenger_id': res[1],
                'instance_id': res[2],
                'row_number': res[3],
                'seat_letter': res[4],
                'seat_cost': float(res[5]),
                'passenger_name': f"{res[6]} {res[7]}",
                'title': res[8],
                'departure_time': res[9].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'departure_airport': res[11],
                'arrival_airport': res[12],
                'departure_city': res[13],
                'arrival_city': res[14],
                'travel_class': res[15],
                'seat_number': f"{res[3]}{res[4]}"
            })
        
        booking_info = {
            'booking_id': booking[0],
            'booking_status': booking[1],
            'contact_email': booking[2],
            'contact_phone': booking[3]
        }
        
        return render_template('booking_actions.html',
                             booking_info=booking_info,
                             reservations=reservation_list,
                             email=email,
                             action_type=action_type)
        
    except Exception as e:
        print("Error loading booking actions:", e)
        return render_template('error.html', error="Error loading booking details")
    finally:
        cursor.close()
        conn.close()

@app.route('/complete-reschedule', methods=['POST'])
def complete_reschedule():
    """
    Complete the reschedule process after seat selection.
    Handles ALL passengers being rescheduled together.
    """
    # Get ALL reservation IDs to reschedule
    reschedule_reservation_ids = session.get('reschedule_reservation_ids', [])
    single_reservation_id = session.get('reschedule_reservation_id')
    
    # Fallback to single reservation if list not available
    if not reschedule_reservation_ids and single_reservation_id:
        reschedule_reservation_ids = [single_reservation_id]
    
    new_flight_id = session.get('reschedule_new_flight')
    selected_seats = request.form.getlist('selected_outbound_seats')
    passenger_data = session.get('passenger_data', session.get('reschedule_passenger_data', []))
    
    if not reschedule_reservation_ids or not new_flight_id:
        return render_template('error.html', error="Reschedule session expired")
    
    if len(selected_seats) != len(reschedule_reservation_ids):
        return render_template('error.html', 
            error=f"Please select exactly {len(reschedule_reservation_ids)} seat(s) for all passengers")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get booking ID from first reservation
        cursor.execute("""
            SELECT r.Booking_ID, b.Booking_Status
            FROM Reservation r
            JOIN Booking b ON r.Booking_ID = b.Booking_ID
            WHERE r.Reservation_ID = :res_id
        """, res_id=reschedule_reservation_ids[0])
        
        booking_info = cursor.fetchone()
        if not booking_info:
            return render_template('error.html', error="Original reservation not found")
        
        booking_id = booking_info[0]
        
        # Get new flight info
        cursor.execute("""
            SELECT fi.Model_ID, fr.Route_ID 
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            WHERE fi.Instance_ID = :flight_id
        """, flight_id=new_flight_id)
        new_flight_info = cursor.fetchone()
        new_model_id = new_flight_info[0]
        new_route_id = new_flight_info[1]
        
        # Get new price
        cursor.execute("""
            SELECT Base_Price FROM Route_Pricing 
            WHERE Route_ID = :route_id 
            AND Class_ID = :class_id
            AND SYSDATE BETWEEN Valid_From AND Valid_To
        """, route_id=new_route_id, class_id=session.get('travel_class', 'ECO'))
        
        new_price_result = cursor.fetchone()
        new_base_price = new_price_result[0] if new_price_result else 0
        
        total_price_difference = 0
        new_reservation_ids = []
        
        print(f"DEBUG - Rescheduling {len(reschedule_reservation_ids)} reservations to flight {new_flight_id}")
        
        # Process each reservation
        for i, old_res_id in enumerate(reschedule_reservation_ids):
            # Get original reservation details
            cursor.execute("""
                SELECT r.Passenger_ID, r.Price_Charged, r.Passenger_Type
                FROM Reservation r
                WHERE r.Reservation_ID = :res_id
            """, res_id=old_res_id)
            
            original_res = cursor.fetchone()
            if not original_res:
                print(f"DEBUG - Reservation {old_res_id} not found, skipping")
                continue
            
            passenger_id = original_res[0]
            old_price = float(original_res[1])
            passenger_type = original_res[2]
            
            # Calculate new price (infants get 50% discount)
            if passenger_type == 'INFANT':
                new_price = new_base_price * 0.5
            else:
                new_price = new_base_price
            
            total_price_difference += (new_price - old_price)
            
            # Parse seat for this passenger
            seat_str = selected_seats[i]
            row_match = re.search(r'\d+', seat_str)
            letter_match = re.search(r'[A-Z]', seat_str)
            
            if not row_match or not letter_match:
                return render_template('error.html', error=f"Invalid seat format: {seat_str}")
            
            new_row_num = int(row_match.group())
            new_seat_letter = letter_match.group()
            
            # Verify seat exists
            cursor.execute("""
                SELECT 1 FROM Aircraft_Seat_Map 
                WHERE Model_ID = :model_id 
                AND Row_Number = :row_num 
                AND Seat_Letter = :seat_letter
            """, model_id=new_model_id, row_num=new_row_num, seat_letter=new_seat_letter)
            
            if not cursor.fetchone():
                return render_template('error.html', error=f"Seat {seat_str} not found in aircraft")
            
            # Delete old reservation
            print(f"DEBUG - Deleting old reservation: {old_res_id}")
            cursor.execute("""
                DELETE FROM Reservation WHERE Reservation_ID = :res_id
            """, res_id=old_res_id)
            
            # Generate new reservation ID using sequence
            cursor.execute("""
                SELECT 'IAT-' || TO_CHAR(SYSDATE, 'YYYYMMDD') || '-' || LPAD(Reservation_Seq.NEXTVAL, 6, '0') 
                FROM DUAL
            """)
            new_res_id = cursor.fetchone()[0]
            new_reservation_ids.append(new_res_id)
            
            # Create new reservation
            cursor.execute("""
                INSERT INTO Reservation 
                (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Passenger_Type, Ticket_Status)
                VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price, :pax_type, 'ISSUED')
            """, 
            res_id=new_res_id,
            booking_id=booking_id,
            passenger_id=passenger_id,
            instance_id=new_flight_id,
            row_num=new_row_num,
            seat_letter=new_seat_letter,
            price=new_price,
            pax_type=passenger_type)
            
            print(f"DEBUG - Created new reservation {new_res_id} for passenger {passenger_id} at seat {new_row_num}{new_seat_letter}")
        
        # Update booking status
        cursor.execute("""
            UPDATE Booking SET Booking_Status = 'CONFIRMED' 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        conn.commit()
        
        change_fee = 500 * len(reschedule_reservation_ids)  # Fee per passenger
        
        print(f"DEBUG - Reschedule completed successfully:")
        print(f"  Booking ID: {booking_id}")
        print(f"  Passengers rescheduled: {len(new_reservation_ids)}")
        print(f"  Price difference: {total_price_difference}")
        
        # Clear session
        clear_reschedule_session()
        
        return render_template('reschedule_confirmation.html',
                             booking_id=booking_id,
                             new_reservation_ids=new_reservation_ids,
                             passenger_count=len(new_reservation_ids),
                             new_flight_id=new_flight_id,
                             price_difference=total_price_difference,
                             change_fee=change_fee)
        
    except Exception as e:
        conn.rollback()
        print("Error during reschedule:", e)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error=f"Reschedule failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def clear_reschedule_session():
    """Helper function to clear all reschedule and booking session data"""
    session.pop('reschedule_reservation_id', None)
    session.pop('reschedule_reservation_ids', None)  # NEW: Clear all reservation IDs
    session.pop('reschedule_new_flight', None)
    session.pop('reschedule_context', None)
    session.pop('reschedule_original_booking', None)
    session.pop('reschedule_passenger_data', None)  # NEW: Clear pre-filled passenger data
    session.pop('reschedule_travel_class', None)    # NEW: Clear travel class
    session.pop('is_reschedule', None)
    session.pop('passenger_data', None)  # Clear passenger data used in seat selection
    
    # Also clear normal booking session data to prevent conflicts
    session.pop('selected_outbound_seats', None)
    session.pop('selected_return_seats', None)
    session.pop('selected_outbound_flight', None)
    session.pop('selected_return_flight', None)
    session.pop('search_travel_class', None)
    session.pop('search_passengers', None)
    session.pop('search_trip_type', None)
    session.pop('travel_class', None)
    session.pop('passengers', None)
    session.pop('trip_type', None)

def get_original_booking_id(reservation_id):
    """Get the original booking ID for a reservation"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT Booking_ID FROM Reservation 
            WHERE Reservation_ID = :res_id
        """, res_id=reservation_id)
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()
        conn.close()

@app.route('/debug-schema')
def debug_schema():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check actual table names in the database
    cursor.execute("""
        SELECT table_name 
        FROM user_tables 
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    result = "<h1>Database Tables</h1><ul>"
    for table in tables:
        result += f"<li>{table[0]}</li>"
    result += "</ul>"
    
    # Show columns for key tables
    for table_name in ['AIRPORT', 'FLIGHT_INSTANCE', 'FLIGHT_ROUTE', 'AIRCRAFT_SEAT_MAP', 'PASSENGER', 'RESERVATION', 'BOOKING', 'PAYMENT']:
        try:
            cursor.execute(f"""
                SELECT column_name, data_type 
                FROM user_tab_columns 
                WHERE table_name = '{table_name}' 
                ORDER BY column_id
            """)
            columns = cursor.fetchall()
            
            result += f"<h2>{table_name} Columns:</h2><ul>"
            for col in columns:
                result += f"<li>{col[0]} - {col[1]}</li>"
            result += "</ul>"
        except:
            result += f"<h2>{table_name} - Table not found or error</h2>"
    
    cursor.close()
    conn.close()
    
    return result

@app.route('/debug-constraint')
def debug_constraint():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Find what constraint is causing the issue
        cursor.execute("""
            SELECT constraint_name, table_name, column_name 
            FROM user_cons_columns 
            WHERE constraint_name = 'SYS_C009170'
        """)
        constraint_info = cursor.fetchone()
        
        if constraint_info:
            return f"Constraint {constraint_info[0]} is on table {constraint_info[1]}, column {constraint_info[2]}"
        else:
            return "Constraint not found"
            
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()

@app.route('/debug-app-user')
def debug_app_user():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check the current maximum User_ID
        cursor.execute("SELECT MAX(User_ID) FROM App_User")
        max_id = cursor.fetchone()[0]
        
        # Check if there's an identity sequence issue
        cursor.execute("""
            SELECT sequence_name, last_number 
            FROM user_sequences 
            WHERE sequence_name LIKE '%USER%' OR sequence_name LIKE '%APP_USER%'
        """)
        sequences = cursor.fetchall()
        
        result = f"<h1>App_User Debug</h1>"
        result += f"<p>Max User_ID: {max_id}</p>"
        result += f"<h2>Sequences:</h2><ul>"
        for seq in sequences:
            result += f"<li>{seq[0]} - Last Number: {seq[1]}</li>"
        result += "</ul>"
        
        return result
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    # Uncomment the line below to run locally       
    # app.run(debug=True)

    # Run the app to be accessible over the network
    # Using port 5001 because 5000 is used by AirPlay on macOS
    app.run(debug=True, host='0.0.0.0', port=5001)