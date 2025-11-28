# app.py
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
    # Redirect to login page if not authenticated, otherwise to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

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
        nationality = request.form.get('nationality')
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
                (Linked_User_ID, First_Name, Last_Name, Date_Of_Birth, Gender, Nationality, Title)
                VALUES (:user_id, :first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :nationality, :title)
            """, 
            user_id=next_user_id,
            first_name=first_name,
            last_name=last_name,
            dob=date_of_birth,
            gender=gender,
            nationality=nationality,
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

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')  # This will be your main page after login

# Update the home route to redirect to dashboard if logged in
@app.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
                   p.Nationality, p.Title, p.Passport_Num
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
        
        # Get upcoming flights
        cursor.execute("""
            SELECT COUNT(*) 
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
            'nationality': user_data[8],
            'title': user_data[9],
            'passport_number': user_data[10] or 'Not provided',
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

        # Get flights using new schema - UPDATED FOR NEW SCHEMA
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
                   (SELECT COUNT(*) FROM Aircraft_Seat_Map WHERE Model_ID = fi.Model_ID) - 
                   (SELECT COUNT(*) FROM Reservation WHERE Instance_ID = fi.Instance_ID AND Row_Number IS NOT NULL) as Seats_Remaining
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
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
    departure_city = request.form.get('departure_city')
    arrival_city = request.form.get('arrival_city')
    departure_date = request.form.get('departure_date')
    travel_class = request.form.get('travel_class')
    passengers = request.form.get('passengers')
    trip_type = request.form.get('trip_type', 'one_way')  # Default to one way

    print(f"Searching {trip_type} flights: {departure_city} to {arrival_city} on {departure_date}")

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

        # Get flights using new schema - UPDATED FOR NEW SCHEMA
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
                   (SELECT COUNT(*) FROM Aircraft_Seat_Map WHERE Model_ID = fi.Model_ID) - 
                   (SELECT COUNT(*) FROM Reservation WHERE Instance_ID = fi.Instance_ID AND Row_Number IS NOT NULL) as Seats_Remaining
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
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

@app.route('/select-flight/<flight_id>')
def select_flight(flight_id):
    # Get parameters from URL first, then fall back to session
    trip_type = request.args.get('trip_type') or session.get('search_trip_type', 'one_way')
    passengers = request.args.get('passengers') or session.get('search_passengers', 1)
    travel_class = request.args.get('travel_class') or session.get('search_travel_class', 'ECO')
    
    # Store flight selection in session
    session['selected_outbound_flight'] = flight_id
    session['trip_type'] = trip_type
    session['passengers'] = passengers
    session['travel_class'] = travel_class
    
    print(f"DEBUG - Setting session travel_class: {travel_class}")
    print(f"DEBUG - Setting session passengers: {passengers}")
    print(f"DEBUG - Setting session trip_type: {trip_type}")
    
    if session['trip_type'] == 'round_trip':
        return redirect('/return-flight-search')
    else:
        return redirect('/seat-selection')

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
            
            # Search for return flights - UPDATED FOR NEW SCHEMA
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
                       (SELECT COUNT(*) FROM Aircraft_Seat_Map WHERE Model_ID = fi.Model_ID) - 
                       (SELECT COUNT(*) FROM Reservation WHERE Instance_ID = fi.Instance_ID AND Row_Number IS NOT NULL) as Seats_Remaining
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                JOIN City c1 ON zm1.City_ID = c1.City_ID
                JOIN City c2 ON zm2.City_ID = c2.City_ID
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
    # Check if this is a reschedule operation
    reschedule_reservation_id = session.get('reschedule_reservation_id')
    
    if reschedule_reservation_id:
        # This is a reschedule flow - use the reschedule flight
        flight_id = session.get('reschedule_new_flight')
        if not flight_id:
            return render_template('error.html', error="Reschedule flight not found")
        # Set other parameters as needed
        session['travel_class'] = session.get('search_travel_class', 'ECO')
        session['passengers'] = 1  # Reschedule is per reservation
        session['trip_type'] = 'one_way'
        session['selected_outbound_flight'] = flight_id
        
        # Store that this is a reschedule operation
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
    print(f"DEBUG - Reschedule mode: {reschedule_reservation_id is not None}")
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
        
        return render_template('seat_selection.html',
                            outbound_flight=outbound_flight,
                            return_flight=return_flight,
                            outbound_seats=outbound_seats,
                            return_seats=return_seats,
                            booked_outbound_seats=booked_outbound_seats,
                            booked_return_seats=booked_return_seats,
                            passengers=passengers,
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

@app.route('/select-return-flight/<flight_id>')
def select_return_flight(flight_id):
    session['selected_return_flight'] = flight_id
    return redirect('/seat-selection')

@app.route('/passenger-info', methods=['GET', 'POST'])
def passenger_info():
    if request.method == 'POST':
        # Check if this is a reschedule operation
        if session.get('is_reschedule'):
            print("DEBUG - Detected reschedule operation, redirecting to complete_reschedule")
            # For reschedule, redirect to complete reschedule
            return redirect(url_for('complete_reschedule'))
        
        # Handle form submission from seat selection for NORMAL booking
        selected_outbound_seats = request.form.getlist('selected_outbound_seats')
        selected_return_seats = request.form.getlist('selected_return_seats')
        
        # Store in session for booking processing
        session['selected_outbound_seats'] = selected_outbound_seats
        session['selected_return_seats'] = selected_return_seats
        
        # Get flight details
        flight_id = session.get('selected_outbound_flight')
        return_flight_id = session.get('selected_return_flight')
        passengers = int(session.get('passengers', 1))
        travel_class = session.get('travel_class', 'ECO')
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Get outbound flight details - UPDATED
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
            
            # Get user's contact information from session
            user_email = session.get('user_email', '')
            user_phone = session.get('user_phone', '')
            
            return render_template('passenger_info.html',
                                outbound_flight=outbound_flight,
                                return_flight=return_flight,
                                selected_outbound_seats=selected_outbound_seats,
                                selected_return_seats=selected_return_seats,
                                passengers=passengers,
                                travel_class=travel_class,
                                user_email=user_email,
                                user_phone=user_phone)
            
        except Exception as e:
            print("Error in passenger info:", e)
            return render_template('error.html', error="Error loading passenger information")
            
        finally:
            cursor.close()
            conn.close()
    
    else:
        # GET request - redirect to seat selection if no seats selected
        if 'selected_outbound_seats' not in session:
            return redirect('/seat-selection')
        
        # Similar logic as above to display the form
        return redirect('/seat-selection')

def validate_cnic(cnic):
    """Validate CNIC format (XXXXX-XXXXXXX-X)"""
    if not cnic:
        return False
    pattern = r'^\d{5}-\d{7}-\d{1}$'
    return re.match(pattern, cnic) is not None

@app.route('/process-booking', methods=['POST'])
def process_booking():
    try:
        # Get passenger data from form
        passengers = int(session.get('passengers', 1))
        passenger_data = []
        
        # Get contact information from separate fields
        contact_email = request.form.get('contact_email')
        contact_phone = request.form.get('contact_phone')
        
        print(f"DEBUG - Contact Email: {contact_email}")
        print(f"DEBUG - Contact Phone: {contact_phone}")
        
        for i in range(passengers):
            passenger_data.append({
                'first_name': request.form.get(f'first_name_{i}'),
                'last_name': request.form.get(f'last_name_{i}'),
                'date_of_birth': request.form.get(f'date_of_birth_{i}'),
                'gender': request.form.get(f'gender_{i}'),
                'passport_number': request.form.get(f'passport_number_{i}', ''),
                'nationality': request.form.get(f'nationality_{i}', 'US'),  # Default nationality
                'title': request.form.get(f'title_{i}', 'MR')  # Default title
            })
        
        # Get seat selections
        selected_outbound_seats = request.form.getlist('selected_outbound_seats')
        selected_return_seats = request.form.getlist('selected_return_seats')
        outbound_flight_id = session.get('selected_outbound_flight')
        return_flight_id = session.get('selected_return_flight')
        trip_type = session.get('trip_type', 'one_way')
        travel_class = session.get('travel_class', 'ECO')
        
        print(f"DEBUG - Outbound flight: {outbound_flight_id}")
        print(f"DEBUG - Return flight: {return_flight_id}")
        print(f"DEBUG - Outbound seats: {selected_outbound_seats}")
        print(f"DEBUG - Return seats: {selected_return_seats}")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Generate base timestamp for IDs
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            total_amount = 0
            
            # Function to generate sequential IDs
            def generate_sequential_id(prefix, table_name, id_column, cursor):
                """Generate a sequential ID that doesn't exist in the database"""
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

            # Get flight details for pricing - UPDATED
            cursor.execute("""
                SELECT fi.Model_ID, fr.Route_ID 
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=outbound_flight_id)
            flight_info = cursor.fetchone()
            model_id = flight_info[0]
            route_id = flight_info[1]
            
            # Calculate total amount using Route_Pricing - UPDATED
            cursor.execute("""
                SELECT Base_Price FROM Route_Pricing 
                WHERE Route_ID = :route_id 
                AND Class_ID = :class_id
                AND SYSDATE BETWEEN Valid_From AND Valid_To
            """, route_id=route_id, class_id=travel_class)
            
            pricing_result = cursor.fetchone()
            if pricing_result:
                base_price = pricing_result[0]
                total_amount = base_price * len(selected_outbound_seats)
                print(f"DEBUG - Base price for {travel_class}: {base_price}")
            else:
                # If no pricing found, use default amounts
                default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                base_price = default_costs.get(travel_class, 100)
                total_amount = base_price * len(selected_outbound_seats)
                print(f"DEBUG - Using default price for {travel_class}: {base_price}")
            
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
                    total_amount += return_base_price * len(selected_return_seats)
                    print(f"DEBUG - Return base price: {return_base_price}")
                else:
                    default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                    return_base_price = default_costs.get(travel_class, 100)
                    total_amount += return_base_price * len(selected_return_seats)
                    print(f"DEBUG - Using default return price: {return_base_price}")
            
            print(f"DEBUG - Total amount: {total_amount}")
            
            # Create booking (PNR will be auto-generated by trigger) - UPDATED
            print(f"DEBUG - Creating booking with contact: {contact_email}, {contact_phone}")
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
            
            # Insert passengers - UPDATED FOR NEW SCHEMA
            passenger_ids = []
            for i, passenger in enumerate(passenger_data):
                print(f"DEBUG - Inserting passenger {i}: {passenger['first_name']} {passenger['last_name']}")
                
                cursor.execute("""
                    INSERT INTO Passenger 
                    (First_Name, Last_Name, Date_Of_Birth, Gender, Nationality, Passport_Num, Title)
                    VALUES (:first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :nationality, :passport, :title)
                """, 
                first_name=passenger['first_name'],
                last_name=passenger['last_name'],
                dob=passenger['date_of_birth'],
                gender=passenger['gender'],
                nationality=passenger['nationality'],
                passport=passenger['passport_number'],
                title=passenger['title'])
                
                # Get the generated passenger ID
                cursor.execute("SELECT Passenger_ID FROM Passenger WHERE First_Name = :first_name AND Last_Name = :last_name AND Date_Of_Birth = TO_DATE(:dob, 'YYYY-MM-DD')", 
                             first_name=passenger['first_name'], last_name=passenger['last_name'], dob=passenger['date_of_birth'])
                passenger_result = cursor.fetchone()
                passenger_ids.append(passenger_result[0])
                print(f"DEBUG - Passenger {i} ID: {passenger_result[0]}")
            
            # Create reservations for outbound flight - UPDATED
            for i, seat_simple in enumerate(selected_outbound_seats):
                if i < len(passenger_ids):
                    # Parse seat information
                    row_match = re.search(r'\d+', seat_simple)
                    letter_match = re.search(r'[A-Z]', seat_simple)
                    
                    if not row_match or not letter_match:
                        print(f"ERROR - Invalid seat format: {seat_simple}")
                        continue
                    
                    row_num = int(row_match.group())
                    seat_letter = letter_match.group()
                    
                    # Verify seat exists in aircraft model - UPDATED
                    cursor.execute("""
                        SELECT 1 FROM Aircraft_Seat_Map 
                        WHERE Model_ID = :model_id 
                        AND Row_Number = :row_num 
                        AND Seat_Letter = :seat_letter
                    """, model_id=model_id, row_num=row_num, seat_letter=seat_letter)
                    
                    if not cursor.fetchone():
                        print(f"ERROR - Seat {seat_simple} not found in aircraft model {model_id}")
                        continue
                    
                    # Get seat price - UPDATED
                    cursor.execute("""
                        SELECT Base_Price FROM Route_Pricing 
                        WHERE Route_ID = :route_id 
                        AND Class_ID = :class_id
                        AND SYSDATE BETWEEN Valid_From AND Valid_To
                    """, route_id=route_id, class_id=travel_class)
                    
                    seat_price_result = cursor.fetchone()
                    seat_price = seat_price_result[0] if seat_price_result else base_price
                    
                    # Create reservation - UPDATED
                    res_id = generate_sequential_id("RES", "Reservation", "Reservation_ID", cursor)
                    
                    print(f"DEBUG - Creating outbound reservation {i}: {res_id} for seat {row_num}{seat_letter}")
                    
                    cursor.execute("""
                        INSERT INTO Reservation 
                        (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged)
                        VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price)
                    """, 
                    res_id=res_id,
                    booking_id=booking_id,
                    passenger_id=passenger_ids[i],
                    instance_id=outbound_flight_id,
                    row_num=row_num,
                    seat_letter=seat_letter,
                    price=seat_price)
                    print(f"DEBUG - Outbound reservation {i} created successfully")
            
            # Create reservations for return flight if applicable - UPDATED
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
                
                for i, seat_simple in enumerate(selected_return_seats):
                    if i < len(passenger_ids):
                        # Parse seat information
                        row_match = re.search(r'\d+', seat_simple)
                        letter_match = re.search(r'[A-Z]', seat_simple)
                        
                        if not row_match or not letter_match:
                            print(f"ERROR - Invalid return seat format: {seat_simple}")
                            continue
                        
                        row_num = int(row_match.group())
                        seat_letter = letter_match.group()
                        
                        # Verify seat exists in return aircraft model - UPDATED
                        cursor.execute("""
                            SELECT 1 FROM Aircraft_Seat_Map 
                            WHERE Model_ID = :model_id 
                            AND Row_Number = :row_num 
                            AND Seat_Letter = :seat_letter
                        """, model_id=return_model_id, row_num=row_num, seat_letter=seat_letter)
                        
                        if not cursor.fetchone():
                            print(f"ERROR - Return seat {seat_simple} not found in aircraft model {return_model_id}")
                            continue
                        
                        # Get return seat price - UPDATED
                        cursor.execute("""
                            SELECT Base_Price FROM Route_Pricing 
                            WHERE Route_ID = :route_id 
                            AND Class_ID = :class_id
                            AND SYSDATE BETWEEN Valid_From AND Valid_To
                        """, route_id=return_route_id, class_id=travel_class)
                        
                        return_seat_price_result = cursor.fetchone()
                        return_seat_price = return_seat_price_result[0] if return_seat_price_result else base_price
                        
                        # Create return reservation - UPDATED
                        res_id = generate_sequential_id("RES", "Reservation", "Reservation_ID", cursor)
                        
                        print(f"DEBUG - Creating return reservation {i}: {res_id} for seat {row_num}{seat_letter}")
                        
                        cursor.execute("""
                            INSERT INTO Reservation 
                            (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged)
                            VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price)
                        """, 
                        res_id=res_id,
                        booking_id=booking_id,
                        passenger_id=passenger_ids[i],
                        instance_id=return_flight_id,
                        row_num=row_num,
                        seat_letter=seat_letter,
                        price=return_seat_price)
                        print(f"DEBUG - Return reservation {i} created successfully")
            
            # Create initial payment record - UPDATED
            payment_id = generate_sequential_id("PAY", "Payment", "Payment_ID", cursor)
            cursor.execute("""
                INSERT INTO Payment 
                (Payment_ID, Booking_ID, Amount_Paid, Payment_Date, Payment_Method)
                VALUES (:payment_id, :booking_id, :amount, SYSTIMESTAMP, 'CREDIT_CARD')
            """,
            payment_id=payment_id,
            booking_id=booking_id,
            amount=total_amount)  # Set initial payment amount to total
            
            conn.commit()
            print(f"DEBUG - All database operations completed successfully!")
            
            # Clear session data
            session.pop('selected_outbound_seats', None)
            session.pop('selected_return_seats', None)
            session.pop('selected_outbound_flight', None)
            session.pop('selected_return_flight', None)
            session.pop('search_travel_class', None)
            session.pop('search_passengers', None)
            session.pop('search_trip_type', None)
            
            return redirect(url_for('booking_confirmation', 
                        booking_id=booking_id, 
                        passenger_count=passengers,
                        total_amount=total_amount,
                        auto_download='true'))
            
        except Exception as e:
            conn.rollback()
            print("Database error during booking:", e)
            print("Error type:", type(e).__name__)
            
            # More detailed error information
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
        # Get booking and passenger details using new schema - UPDATED
        cursor.execute("""
            SELECT b.Booking_ID, 
                   p.Passenger_ID, p.First_Name, p.Last_Name, p.Title, p.Nationality,
                   r.Reservation_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   fi.Instance_ID, fi.Model_ID,
                   TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI'),
                   TO_CHAR(fi.Arrival_Time, 'DD-MON-YYYY HH24:MI'),
                   a1.Airport_Name, a2.Airport_Name,
                   c1.City_Name, c2.City_Name,
                   arc.Class_ID
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
        """, booking_id=booking_id)
        
        booking_data = cursor.fetchall()
        
        if not booking_data:
            return render_template('error.html', error="Booking not found")
        
        # Organize data for ticket generation - CORRECTED COLUMN INDEXES
        passengers_data = []
        booking_info = {
            'booking_id': booking_data[0][0],
            'total_amount': sum(float(row[9]) for row in booking_data),  # Price_Charged is at index 9
            'flight_number': booking_data[0][10],  # Instance_ID at index 10
            'aircraft_type': booking_data[0][11],  # Model_ID at index 11
            'departure_time': booking_data[0][12],  # Departure_Time at index 12
            'arrival_time': booking_data[0][13],    # Arrival_Time at index 13
            'departure_airport': booking_data[0][14],  # Departure Airport at index 14
            'arrival_airport': booking_data[0][15],    # Arrival Airport at index 15
            'departure_city': booking_data[0][16],     # Departure City at index 16
            'arrival_city': booking_data[0][17],       # Arrival City at index 17
            'travel_class': booking_data[0][18],       # Travel Class at index 18
        }
        
        # Extract flight date from departure time
        flight_date = booking_data[0][12].split(' ')[0]
        booking_info['flight_date'] = flight_date
        
        for row in booking_data:
            passenger = {
                'passenger_id': row[1],           # Passenger_ID at index 1
                'first_name': row[2],             # First_Name at index 2
                'last_name': row[3],              # Last_Name at index 3
                'title': row[4],                  # Title at index 4
                'nationality': row[5],            # Nationality at index 5
                'reservation_id': row[6],         # Reservation_ID at index 6
                'row_number': row[7],             # Row_Number at index 7
                'seat_letter': row[8],            # Seat_Letter at index 8
                'seat_number': f"{row[7]}{row[8]}",  # Combine row number and seat letter
                'seat_cost': float(row[9]),       # Price_Charged at index 9
            }
            passengers_data.append(passenger)
        
        # Generate tickets
        booking_info['passengers'] = passengers_data
        booking_info['flight_type'] = 'ONE-WAY'  # Simplified for new schema
        
        ticket_gen = TicketGenerator()
        all_tickets = ticket_gen.generate_all_tickets(booking_info, "temp_tickets")
        
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
        
        # Send ZIP file
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'tickets_{booking_id}.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        print("Error generating tickets:", e)
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
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
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
            'nationality': ticket_data[9],
            'seat_number': f"{ticket_data[3]}{ticket_data[4]}",
            'flight_number': ticket_data[10],
            'aircraft_type': ticket_data[11],
            'departure_time': ticket_data[12],
            'arrival_time': ticket_data[13],
            'departure_airport': ticket_data[14],
            'arrival_airport': ticket_data[15],
            'departure_city': ticket_data[16],
            'arrival_city': ticket_data[17],
            'travel_class': ticket_data[18],
            'flight_date': ticket_data[12].split(' ')[0],
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
        
        # Get all reservations for this booking - UPDATED
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
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
                'nationality': res[9],
                'departure_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[11].strftime('%d-%b-%Y %H:%M'),
                'departure_airport': res[12],
                'arrival_airport': res[13],
                'departure_city': res[14],
                'arrival_city': res[15],
                'travel_class': res[16],
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
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        total_refund = 0
        
        for res_id in reservation_ids:
            # Get reservation details for cancellation log - UPDATED
            cursor.execute("""
                SELECT r.Price_Charged, r.Passenger_ID, r.Instance_ID
                FROM Reservation r
                WHERE r.Reservation_ID = :res_id
            """, res_id=res_id)
            
            res_details = cursor.fetchone()
            if res_details:
                seat_cost = float(res_details[0])
                passenger_id = res_details[1]
                instance_id = res_details[2]
                
                # Calculate refund (example: 80% refund if cancelled more than 24 hours before flight)
                cursor.execute("""
                    SELECT Departure_Time FROM Flight_Instance WHERE Instance_ID = :instance_id
                """, instance_id=instance_id)
                departure_time = cursor.fetchone()[0]
                hours_until_flight = (departure_time - datetime.now()).total_seconds() / 3600
                
                refund_eligible = 'Y' if hours_until_flight > 24 else 'N'
                refund_amount = seat_cost * 0.8 if refund_eligible == 'Y' else 0
                total_refund += refund_amount
                
                # Delete reservation (cascade will handle related data)
                cursor.execute("""
                    DELETE FROM Reservation 
                    WHERE Reservation_ID = :res_id
                """, res_id=res_id)
                
                # Log cancellation - UPDATED
                cursor.execute("SELECT COUNT(*) FROM Cancellation_Log")
                log_id = cursor.fetchone()[0] + 1
                
                cursor.execute("""
                    INSERT INTO Cancellation_Log 
                    (Log_ID, Booking_ID, Cancel_Date, Reason)
                    VALUES (:log_id, :booking_id, SYSTIMESTAMP, 'Customer initiated cancellation')
                """, log_id=log_id, booking_id=booking_id)
        
        # Update booking status if all reservations are cancelled
        cursor.execute("""
            SELECT COUNT(*) FROM Reservation 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        active_reservations = cursor.fetchone()[0]
        if active_reservations == 0:
            cursor.execute("""
                UPDATE Booking SET Booking_Status = 'CANCELLED' 
                WHERE Booking_ID = :booking_id
            """, booking_id=booking_id)
        
        conn.commit()
        
        # Clear session
        session.pop('selected_reservations', None)
        session.pop('action_booking_id', None)
        session.pop('action_email', None)
        
        return render_template('cancellation_confirmation.html',
                             booking_id=booking_id,
                             cancelled_count=len(reservation_ids),
                             total_refund=total_refund)
        
    except Exception as e:
        conn.rollback()
        print("Error during cancellation:", e)
        return render_template('error.html', error="Cancellation failed")
    finally:
        cursor.close()
        conn.close()

def redirect_to_reschedule(reservation_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get original reservation details for rescheduling - UPDATED
        cursor.execute("""
            SELECT r.Reservation_ID, r.Booking_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
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
            WHERE r.Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        original_flight = cursor.fetchone()
        
        if not original_flight:
            return render_template('error.html', error="Reservation not found")
        
        original_flight_info = {
            'reservation_id': original_flight[0],
            'booking_id': original_flight[1],  # This is the original booking ID
            'passenger_id': original_flight[2],
            'instance_id': original_flight[3],
            'row_number': original_flight[4],
            'seat_letter': original_flight[5],
            'price_charged': float(original_flight[6]),
            'passenger_name': f"{original_flight[7]} {original_flight[8]}",
            'title': original_flight[9],
            'nationality': original_flight[10],
            'model_id': original_flight[11],
            'departure_airport_id': original_flight[12],
            'arrival_airport_id': original_flight[13],
            'departure_time': original_flight[14].strftime('%d-%b-%Y %H:%M'),
            'arrival_time': original_flight[15].strftime('%d-%b-%Y %H:%M'),
            'departure_airport': original_flight[16],
            'arrival_airport': original_flight[17],
            'departure_city': original_flight[18],
            'arrival_city': original_flight[19],
            'travel_class': original_flight[20],
            'departure_date': original_flight[14].strftime('%Y-%m-%d')
        }
        
        # Store the original booking ID in session for seat exclusion
        session['reschedule_original_booking'] = original_flight[1]
        
        return render_template('reschedule_flights.html',
                             original_flight=original_flight_info,
                             reservation_id=reservation_id,
                             original_booking_id=original_flight[1],
                             min_date=datetime.now().strftime('%Y-%m-%d'))
        
    except Exception as e:
        print("Error preparing reschedule:", e)
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
    # Get reschedule context from session
    reschedule_context = session.get('reschedule_context', {})
    reservation_id = reschedule_context.get('reservation_id')
    original_booking_id = reschedule_context.get('original_booking_id')
    
    if not reservation_id:
        return render_template('error.html', error="Reschedule session expired")
    
    # Store the new flight selection for reschedule
    session['reschedule_new_flight'] = flight_id
    session['reschedule_reservation_id'] = reservation_id
    session['reschedule_original_booking'] = original_booking_id
    
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
        
        # Get all reservations for this booking - UPDATED
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
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
                'nationality': res[9],
                'departure_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[11].strftime('%d-%b-%Y %H:%M'),
                'departure_airport': res[12],
                'arrival_airport': res[13],
                'departure_city': res[14],
                'arrival_city': res[15],
                'travel_class': res[16],
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
    """Complete the reschedule process after seat selection"""
    reservation_id = session.get('reschedule_reservation_id')
    new_flight_id = session.get('reschedule_new_flight')
    selected_seats = request.form.getlist('selected_outbound_seats')
    
    if not reservation_id or not new_flight_id or not selected_seats:
        return render_template('error.html', error="Reschedule session expired or no seats selected")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get original reservation details including booking info - UPDATED
        cursor.execute("""
            SELECT r.Booking_ID, r.Passenger_ID, r.Price_Charged, r.Instance_ID,
                   fi.Model_ID as Old_Model_ID, fi.Route_ID as Old_Route_ID,
                   b.Booking_Status
            FROM Reservation r
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Booking b ON r.Booking_ID = b.Booking_ID
            WHERE r.Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        original_res = cursor.fetchone()
        if not original_res:
            return render_template('error.html', error="Original reservation not found")
        
        booking_id = original_res[0]  # Use the EXISTING booking ID
        passenger_id = original_res[1]
        old_price = float(original_res[2])
        old_instance_id = original_res[3]  # Get the old flight instance
        old_model_id = original_res[4]
        old_route_id = original_res[5]
        
        # **CRITICAL: Delete old reservation FIRST to free up the seat**
        print(f"DEBUG - Deleting old reservation: {reservation_id}")
        cursor.execute("""
            DELETE FROM Reservation 
            WHERE Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        # **COMMIT the deletion immediately to free up the seat**
        conn.commit()
        print(f"DEBUG - Old reservation {reservation_id} deleted and committed")
        
        # Now proceed with creating the new reservation
        cursor.execute("""
            SELECT fi.Model_ID, fr.Route_ID 
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            WHERE fi.Instance_ID = :flight_id
        """, flight_id=new_flight_id)
        new_flight_info = cursor.fetchone()
        new_model_id = new_flight_info[0]
        new_route_id = new_flight_info[1]
        
        # Get new seat price using the correct travel class - UPDATED
        cursor.execute("""
            SELECT Base_Price FROM Route_Pricing 
            WHERE Route_ID = :route_id 
            AND Class_ID = :class_id
            AND SYSDATE BETWEEN Valid_From AND Valid_To
        """, route_id=new_route_id, class_id=session.get('travel_class', 'ECO'))
        
        new_price_result = cursor.fetchone()
        new_price = new_price_result[0] if new_price_result else old_price
        
        # Parse new seat information
        new_seat_simple = selected_seats[0]  # First selected seat
        row_match = re.search(r'\d+', new_seat_simple)
        letter_match = re.search(r'[A-Z]', new_seat_simple)
        
        if not row_match or not letter_match:
            return render_template('error.html', error="Invalid seat format")
        
        new_row_num = int(row_match.group())
        new_seat_letter = letter_match.group()
        
        # Verify new seat exists - UPDATED
        cursor.execute("""
            SELECT 1 FROM Aircraft_Seat_Map 
            WHERE Model_ID = :model_id 
            AND Row_Number = :row_num 
            AND Seat_Letter = :seat_letter
        """, model_id=new_model_id, row_num=new_row_num, seat_letter=new_seat_letter)
        
        if not cursor.fetchone():
            return render_template('error.html', error="New seat not found in aircraft")
        
        # **CRITICAL: Check if the new seat is actually available**
        cursor.execute("""
            SELECT 1 FROM Reservation 
            WHERE Instance_ID = :instance_id 
            AND Row_Number = :row_num 
            AND Seat_Letter = :seat_letter
        """, instance_id=new_flight_id, row_num=new_row_num, seat_letter=new_seat_letter)
        
        if cursor.fetchone():
            return render_template('error.html', error="Selected seat is no longer available. Please choose a different seat.")
        
        # Calculate price difference and change fee
        price_difference = new_price - old_price
        change_fee = 500  # Fixed change fee
        
        # Generate new reservation ID
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_reservation_id = f"RES{timestamp}"
        
        print(f"DEBUG - Creating new reservation:")
        print(f"  New Reservation: {new_reservation_id}")
        print(f"  Booking ID: {booking_id}")
        print(f"  New Flight: {new_flight_id}")
        print(f"  New Seat: {new_row_num}{new_seat_letter}")
        
        # Create new reservation - UPDATED
        cursor.execute("""
            INSERT INTO Reservation 
            (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged)
            VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price)
        """, 
        res_id=new_reservation_id,
        booking_id=booking_id,
        passenger_id=passenger_id,
        instance_id=new_flight_id,
        row_num=new_row_num,
        seat_letter=new_seat_letter,
        price=new_price)
        
        print(f"DEBUG - New reservation {new_reservation_id} created for booking {booking_id}")
        
        # Update booking status to CONFIRMED
        cursor.execute("""
            UPDATE Booking SET Booking_Status = 'CONFIRMED' 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        conn.commit()
        
        print(f"DEBUG - Reschedule completed successfully:")
        print(f"  Booking ID: {booking_id} (UPDATED)")
        print(f"  Old Reservation: {reservation_id} (DELETED)")
        print(f"  New Reservation: {new_reservation_id} (CREATED)")
        
        # **CRITICAL: Clear ALL session data to prevent stale data**
        clear_reschedule_session()
        
        return render_template('reschedule_confirmation.html',
                             booking_id=booking_id,
                             new_reservation_id=new_reservation_id,
                             new_flight_id=new_flight_id,
                             price_difference=price_difference,
                             change_fee=change_fee)
        
    except Exception as e:
        conn.rollback()
        print("Error during reschedule:", e)
        print("Error type:", type(e).__name__)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error=f"Reschedule failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def clear_reschedule_session():
    """Helper function to clear all reschedule and booking session data"""
    session.pop('reschedule_reservation_id', None)
    session.pop('reschedule_new_flight', None)
    session.pop('reschedule_context', None)
    session.pop('reschedule_original_booking', None)
    session.pop('is_reschedule', None)
    
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
    app.run(debug=True, host='0.0.0.0', port=5000)