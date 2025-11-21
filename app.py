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

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for sessions

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/destination')
def destination():
    return render_template('destination.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

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
        # Get city names
        cursor.execute("SELECT AirportCity FROM AIRPORT WHERE Airport_ID = :dept", dept=departure_city)
        departure_city_name = cursor.fetchone()[0]
        
        cursor.execute("SELECT AirportCity FROM AIRPORT WHERE Airport_ID = :arr", arr=arrival_city)
        arrival_city_name = cursor.fetchone()[0]
        
        # Map travel class codes to full names
        class_names = {
            'ECO': 'Economy',
            'BUS': 'Business', 
            'FIR': 'First Class'
        }
        travel_class_name = class_names.get(travel_class, travel_class)

        # Get flights
        query = """
            SELECT f.Flight_ID,
                   f.Source_Airport_ID,
                   f.Destination_Airport_ID,
                   TO_CHAR(f.Departure_Date_Time, 'YYYY-MM-DD HH24:MI'),
                   TO_CHAR(f.Arrival_Date_Time, 'YYYY-MM-DD HH24:MI'),
                   f.Airplane_Type,
                   a1.AirportCity AS Source_City,
                   a2.AirportCity AS Dest_City
            FROM FLIGHT_DETAILS f
            JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
            WHERE f.Source_Airport_ID = :src
              AND f.Destination_Airport_ID = :dest
              AND TRUNC(f.Departure_Date_Time) = TO_DATE(:dep_date, 'YYYY-MM-DD')
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
                SELECT Source_Airport_ID, Destination_Airport_ID 
                FROM FLIGHT_DETAILS 
                WHERE Flight_ID = :flight_id
            """, flight_id=session['selected_outbound_flight'])
            
            flight_data = cursor.fetchone()
            if not flight_data:
                return render_template("return_flight_results.html", flights=[], error="Original flight not found")
                
            return_departure = flight_data[1]  # Destination becomes source for return
            return_arrival = flight_data[0]    # Source becomes destination for return
            
            print(f"Searching return flights: {return_departure} to {return_arrival} on {return_date}")
            
            # Search for return flights
            query = """
                SELECT f.Flight_ID,
                       f.Source_Airport_ID,
                       f.Destination_Airport_ID,
                       TO_CHAR(f.Departure_Date_Time, 'YYYY-MM-DD HH24:MI'),
                       TO_CHAR(f.Arrival_Date_Time, 'YYYY-MM-DD HH24:MI'),
                       f.Airplane_Type,
                       a1.AirportCity AS Source_City,
                       a2.AirportCity AS Dest_City
                FROM FLIGHT_DETAILS f
                JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
                WHERE f.Source_Airport_ID = :src
                  AND f.Destination_Airport_ID = :dest
                  AND TRUNC(f.Departure_Date_Time) = TO_DATE(:dep_date, 'YYYY-MM-DD')
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
    
    return_flight_id = session.get('selected_return_flight')
    passengers = int(session.get('passengers', 1))
    travel_class = session.get('travel_class', 'ECO')
    trip_type = session.get('trip_type', 'one_way')
    
    print(f"DEBUG - travel_class from session: {travel_class}")
    print(f"DEBUG - passengers: {passengers}")
    print(f"DEBUG - trip_type: {trip_type}")
    print(f"DEBUG - Reschedule mode: {reschedule_reservation_id is not None}")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get outbound flight details
        cursor.execute("""
            SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                   TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
            FROM FLIGHT_DETAILS f
            JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
            WHERE f.Flight_ID = :flight_id
        """, flight_id=flight_id)
        
        outbound_flight = cursor.fetchone()
        
        return_flight = None
        if return_flight_id:
            cursor.execute("""
                SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                       TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
                FROM FLIGHT_DETAILS f
                JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
                WHERE f.Flight_ID = :flight_id
            """, flight_id=return_flight_id)
            return_flight = cursor.fetchone()
        
        # Get available seats for outbound flight
        cursor.execute("""
            SELECT s.Seat_ID, s.Travel_Class_ID, s.Row_Number, s.Seat_Letter,
                   CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
            FROM SEAT_DETAILS s
            LEFT JOIN RESERVATION r ON s.Seat_ID = r.Seat_ID AND r.Reservation_Status = 'ACTIVE'
            WHERE s.Flight_ID = :flight_id 
            AND s.Travel_Class_ID = :travel_class
            ORDER BY s.Row_Number, s.Seat_Letter
        """, flight_id=flight_id, travel_class=travel_class)
        
        outbound_seats = cursor.fetchall()
        
        # Get ALL booked seats for outbound flight (regardless of class) for the seat map
        cursor.execute("""
            SELECT s.Row_Number, s.Seat_Letter
            FROM SEAT_DETAILS s
            JOIN RESERVATION r ON s.Seat_ID = r.Seat_ID
            WHERE s.Flight_ID = :flight_id AND r.Reservation_Status = 'ACTIVE'
        """, flight_id=flight_id)
        
        booked_outbound_seats = [f"{row[0]}{row[1]}" for row in cursor.fetchall()]
        print(f"DEBUG - Booked outbound seats: {booked_outbound_seats}")
        
        return_seats = []
        booked_return_seats = []
        
        if return_flight_id:
            cursor.execute("""
                SELECT s.Seat_ID, s.Travel_Class_ID, s.Row_Number, s.Seat_Letter,
                       CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
                FROM SEAT_DETAILS s
                LEFT JOIN RESERVATION r ON s.Seat_ID = r.Seat_ID AND r.Reservation_Status = 'ACTIVE'
                WHERE s.Flight_ID = :flight_id 
                AND s.Travel_Class_ID = :travel_class
                ORDER BY s.Row_Number, s.Seat_Letter
            """, flight_id=return_flight_id, travel_class=travel_class)
            
            return_seats = cursor.fetchall()
            
            # Get ALL booked seats for return flight
            cursor.execute("""
                SELECT s.Row_Number, s.Seat_Letter
                FROM SEAT_DETAILS s
                JOIN RESERVATION r ON s.Seat_ID = r.Seat_ID
                WHERE s.Flight_ID = :flight_id AND r.Reservation_Status = 'ACTIVE'
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
            SELECT s.Seat_ID,
                   CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
            FROM SEAT_DETAILS s
            LEFT JOIN RESERVATION r ON s.Seat_ID = r.Seat_ID AND r.Reservation_Status = 'ACTIVE'
            WHERE s.Flight_ID = :flight_id
            ORDER BY s.Seat_ID
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
        if session.get('is_reschedule'):
            # For reschedule, redirect to complete reschedule
            return redirect(url_for('complete_reschedule'))
        
        # Handle form submission from seat selection
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
            # Get outbound flight details
            cursor.execute("""
                SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                       TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
                FROM FLIGHT_DETAILS f
                JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
                WHERE f.Flight_ID = :flight_id
            """, flight_id=flight_id)
            outbound_flight = cursor.fetchone()
            
            return_flight = None
            if return_flight_id:
                cursor.execute("""
                    SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                           TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
                    FROM FLIGHT_DETAILS f
                    JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
                    JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
                    WHERE f.Flight_ID = :flight_id
                """, flight_id=return_flight_id)
                return_flight = cursor.fetchone()
            
            return render_template('passenger_info.html',
                                outbound_flight=outbound_flight,
                                return_flight=return_flight,
                                selected_outbound_seats=selected_outbound_seats,
                                selected_return_seats=selected_return_seats,
                                passengers=passengers,
                                travel_class=travel_class)
            
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
        
        for i in range(passengers):
            passenger_data.append({
                'cnic': request.form.get(f'cnic_{i}'),
                'first_name': request.form.get(f'first_name_{i}'),
                'last_name': request.form.get(f'last_name_{i}'),
                'email': request.form.get(f'email_{i}'),
                'phone': request.form.get(f'phone_{i}'),
                'address': request.form.get(f'address_{i}'),
                'city': request.form.get(f'city_{i}'),
                'state': request.form.get(f'state_{i}'),
                'postal_code': request.form.get(f'postal_code_{i}'),
                'country': request.form.get(f'country_{i}'),
                'date_of_birth': request.form.get(f'date_of_birth_{i}'),
                'gender': request.form.get(f'gender_{i}')
            })
        
        # Validate CNIC for all passengers
        for i, passenger in enumerate(passenger_data):
            if not validate_cnic(passenger['cnic']):
                return render_template('error.html', error=f"Invalid CNIC format for passenger {i+1}. Required format: XXXXX-XXXXXXX-X")
        
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
            
            # Generate booking ID
            booking_id = generate_sequential_id("BKG", "BOOKING", "Booking_ID", cursor)
            
            # First, let's check what seat IDs actually exist in the database
            print("DEBUG - Checking actual seat IDs in database...")
            
            # For outbound seats - get the actual seat IDs from the database
            actual_outbound_seats = []
            for simple_seat in selected_outbound_seats:
                if simple_seat and simple_seat.strip():
                    # Extract row number and seat letter from simple seat ID like "1A"
                    row_match = re.search(r'\d+', simple_seat)
                    letter_match = re.search(r'[A-Z]', simple_seat)
                    
                    if not row_match or not letter_match:
                        print(f"ERROR - Invalid seat format: {simple_seat}")
                        return render_template('error.html', error=f"Invalid seat format: {simple_seat}")
                    
                    row_num = int(row_match.group())
                    seat_letter = letter_match.group()
                    
                    print(f"DEBUG - Looking for seat: Flight={outbound_flight_id}, Row={row_num}, Letter={seat_letter}")
                    
                    cursor.execute("""
                        SELECT Seat_ID FROM SEAT_DETAILS 
                        WHERE Flight_ID = :flight_id 
                        AND Row_Number = :row_num 
                        AND Seat_Letter = :seat_letter
                    """, flight_id=outbound_flight_id, row_num=row_num, seat_letter=seat_letter)
                    
                    result = cursor.fetchone()
                    if result:
                        actual_outbound_seats.append(result[0])
                        print(f"DEBUG - Found seat ID for {simple_seat}: {result[0]}")
                    else:
                        print(f"ERROR - Could not find seat ID for {simple_seat}")
                        return render_template('error.html', error=f"Seat {simple_seat} not found in database")
            
            # For return seats - get the actual seat IDs from the database
            actual_return_seats = []
            if return_flight_id:
                for simple_seat in selected_return_seats:
                    if simple_seat and simple_seat.strip():
                        # Extract row number and seat letter from simple seat ID like "1A"
                        row_match = re.search(r'\d+', simple_seat)
                        letter_match = re.search(r'[A-Z]', simple_seat)
                        
                        if not row_match or not letter_match:
                            print(f"ERROR - Invalid return seat format: {simple_seat}")
                            return render_template('error.html', error=f"Invalid return seat format: {simple_seat}")
                        
                        row_num = int(row_match.group())
                        seat_letter = letter_match.group()
                        
                        print(f"DEBUG - Looking for return seat: Flight={return_flight_id}, Row={row_num}, Letter={seat_letter}")
                        
                        cursor.execute("""
                            SELECT Seat_ID FROM SEAT_DETAILS 
                            WHERE Flight_ID = :flight_id 
                            AND Row_Number = :row_num 
                            AND Seat_Letter = :seat_letter
                        """, flight_id=return_flight_id, row_num=row_num, seat_letter=seat_letter)
                        
                        result = cursor.fetchone()
                        if result:
                            actual_return_seats.append(result[0])
                            print(f"DEBUG - Found return seat ID for {simple_seat}: {result[0]}")
                        else:
                            print(f"ERROR - Could not find return seat ID for {simple_seat}")
                            return render_template('error.html', error=f"Return seat {simple_seat} not found in database")
            
            print(f"DEBUG - Actual outbound seats: {actual_outbound_seats}")
            print(f"DEBUG - Actual return seats: {actual_return_seats}")
            
            # Calculate total amount from FLIGHT_COST table using actual seat IDs
            for seat_id in actual_outbound_seats:
                print(f"DEBUG - Checking cost for seat: {seat_id}")
                cursor.execute("""
                    SELECT Cost FROM FLIGHT_COST 
                    WHERE Seat_ID = :seat_id 
                    AND SYSDATE BETWEEN Valid_From_Date AND NVL(Valid_To_Date, SYSDATE)
                """, seat_id=seat_id)
                cost_result = cursor.fetchone()
                if cost_result:
                    total_amount += cost_result[0]
                    print(f"DEBUG - Cost for {seat_id}: {cost_result[0]}")
                else:
                    print(f"DEBUG - No cost found for seat: {seat_id}")
                    # If no cost found, use a default amount based on class
                    default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                    default_amount = default_costs.get(travel_class, 100)
                    total_amount += default_amount
                    print(f"DEBUG - Using default cost for {seat_id}: {default_amount}")
            
            for seat_id in actual_return_seats:
                print(f"DEBUG - Checking cost for return seat: {seat_id}")
                cursor.execute("""
                    SELECT Cost FROM FLIGHT_COST 
                    WHERE Seat_ID = :seat_id 
                    AND SYSDATE BETWEEN Valid_From_Date AND NVL(Valid_To_Date, SYSDATE)
                """, seat_id=seat_id)
                cost_result = cursor.fetchone()
                if cost_result:
                    total_amount += cost_result[0]
                    print(f"DEBUG - Cost for return {seat_id}: {cost_result[0]}")
                else:
                    print(f"DEBUG - No cost found for return seat: {seat_id}")
                    # If no cost found, use a default amount based on class
                    default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                    default_amount = default_costs.get(travel_class, 100)
                    total_amount += default_amount
                    print(f"DEBUG - Using default cost for return {seat_id}: {default_amount}")
            
            print(f"DEBUG - Total amount: {total_amount}")
            
            # Determine trip type for booking
            booking_trip_type = 'ONE_WAY' if trip_type == 'one_way' else 'ROUND_TRIP'
            
            # CRITICAL FIX: Insert ALL passengers FIRST before creating the booking
            lead_passenger_cnic = passenger_data[0]['cnic']
            
            print(f"DEBUG - Inserting all passengers first...")
            for i, passenger in enumerate(passenger_data):
                print(f"DEBUG - Processing passenger {i}: {passenger['cnic']}")
                
                # Check if passenger already exists, if not insert
                cursor.execute("SELECT 1 FROM PASSENGER WHERE CNIC = :cnic", cnic=passenger['cnic'])
                if not cursor.fetchone():
                    print(f"DEBUG - Inserting new passenger: {passenger['cnic']}")
                    # Insert new passenger
                    cursor.execute("""
                        INSERT INTO PASSENGER 
                        (CNIC, P_FirstName, P_LastName, P_Email, P_PhoneNumber, P_Address, P_City, P_State, P_Zipcode, P_Country, Date_Of_Birth, Gender)
                        VALUES (:cnic, :first_name, :last_name, :email, :phone, :address, :city, :state, :postal_code, :country, TO_DATE(:dob, 'YYYY-MM-DD'), :gender)
                    """, 
                    cnic=passenger['cnic'],
                    first_name=passenger['first_name'],
                    last_name=passenger['last_name'], 
                    email=passenger['email'],
                    phone=passenger['phone'],
                    address=passenger['address'],
                    city=passenger['city'],
                    state=passenger['state'],
                    postal_code=passenger['postal_code'],
                    country=passenger['country'],
                    dob=passenger['date_of_birth'],
                    gender=passenger['gender'])
                    print(f"DEBUG - Passenger {passenger['cnic']} inserted successfully")
                else:
                    print(f"DEBUG - Passenger {passenger['cnic']} already exists")
            
            # NOW create the booking record after all passengers are inserted
            print(f"DEBUG - Creating booking: {booking_id} for passenger {lead_passenger_cnic}")
            cursor.execute("""
                INSERT INTO BOOKING 
                (Booking_ID, Lead_Passenger_CNIC, Booking_Date, Total_Amount, Booking_Status, Pay_Option, Trip_Type)
                VALUES (:booking_id, :cnic, SYSTIMESTAMP, :amount, 'CONFIRMED', 'PAY_LATER', :trip_type)
            """, 
            booking_id=booking_id,
            cnic=lead_passenger_cnic,
            amount=total_amount,
            trip_type=booking_trip_type)
            
            print(f"DEBUG - Booking created successfully")
            
            # Now create reservations for each passenger
            for i, passenger in enumerate(passenger_data):
                print(f"DEBUG - Creating reservations for passenger {i}: {passenger['cnic']}")
                
                # Create reservation for outbound flight if seat exists and is valid
                if i < len(actual_outbound_seats) and actual_outbound_seats[i]:
                    seat_id = actual_outbound_seats[i]
                    res_id = generate_sequential_id("RES", "RESERVATION", "Reservation_ID", cursor)
                    
                    print(f"DEBUG - Creating outbound reservation {i}: {res_id} for seat {seat_id}")
                    
                    # Get seat cost for this specific seat
                    cursor.execute("""
                        SELECT Cost FROM FLIGHT_COST 
                        WHERE Seat_ID = :seat_id 
                        AND SYSDATE BETWEEN Valid_From_Date AND NVL(Valid_To_Date, SYSDATE)
                    """, seat_id=seat_id)
                    seat_cost_result = cursor.fetchone()
                    seat_cost = seat_cost_result[0] if seat_cost_result else total_amount / len(actual_outbound_seats)
                    
                    # Verify the seat exists and is not already booked
                    cursor.execute("""
                        SELECT 1 FROM SEAT_DETAILS s 
                        LEFT JOIN RESERVATION r ON s.Seat_ID = r.Seat_ID AND r.Reservation_Status = 'ACTIVE'
                        WHERE s.Seat_ID = :seat_id AND r.Reservation_ID IS NULL
                    """, seat_id=seat_id)
                    
                    if cursor.fetchone():
                        print(f"DEBUG - Seat {seat_id} is available, creating reservation")
                        cursor.execute("""
                            INSERT INTO RESERVATION 
                            (Reservation_ID, Booking_ID, Passenger_CNIC, Seat_ID, Date_Of_Reservation, Reservation_Status, Seat_Cost, Is_Outbound)
                            VALUES (:res_id, :booking_id, :cnic, :seat_id, SYSTIMESTAMP, 'ACTIVE', :seat_cost, 'Y')
                        """, 
                        res_id=res_id,
                        booking_id=booking_id,
                        cnic=passenger['cnic'],
                        seat_id=seat_id,
                        seat_cost=seat_cost)
                        print(f"DEBUG - Outbound reservation {i} created successfully")
                    else:
                        print(f"ERROR - Seat {seat_id} not available for outbound reservation")
                        return render_template('error.html', error=f"Seat {seat_id} is already booked. Please select different seats.")
                
                # Process return flight if exists - CRITICAL FIX: Ensure ALL return seats are processed
                if return_flight_id and i < len(actual_return_seats) and actual_return_seats[i]:
                    seat_id = actual_return_seats[i]
                    res_id = generate_sequential_id("RES", "RESERVATION", "Reservation_ID", cursor)
                    
                    print(f"DEBUG - Creating return reservation {i}: {res_id} for seat {seat_id}")
                    
                    # Get seat cost for this specific seat
                    cursor.execute("""
                        SELECT Cost FROM FLIGHT_COST 
                        WHERE Seat_ID = :seat_id 
                        AND SYSDATE BETWEEN Valid_From_Date AND NVL(Valid_To_Date, SYSDATE)
                    """, seat_id=seat_id)
                    seat_cost_result = cursor.fetchone()
                    seat_cost = seat_cost_result[0] if seat_cost_result else total_amount / len(actual_return_seats)
                    
                    # Verify the seat exists and is not already booked
                    cursor.execute("""
                        SELECT 1 FROM SEAT_DETAILS s 
                        LEFT JOIN RESERVATION r ON s.Seat_ID = r.Seat_ID AND r.Reservation_Status = 'ACTIVE'
                        WHERE s.Seat_ID = :seat_id AND r.Reservation_ID IS NULL
                    """, seat_id=seat_id)
                    
                    if cursor.fetchone():
                        print(f"DEBUG - Return seat {seat_id} is available, creating reservation")
                        cursor.execute("""
                            INSERT INTO RESERVATION 
                            (Reservation_ID, Booking_ID, Passenger_CNIC, Seat_ID, Date_Of_Reservation, Reservation_Status, Seat_Cost, Is_Outbound)
                            VALUES (:res_id, :booking_id, :cnic, :seat_id, SYSTIMESTAMP, 'ACTIVE', :seat_cost, 'N')
                        """, 
                        res_id=res_id,
                        booking_id=booking_id,
                        cnic=passenger['cnic'],
                        seat_id=seat_id,
                        seat_cost=seat_cost)
                        print(f"DEBUG - Return reservation {i} created successfully")
                    else:
                        print(f"ERROR - Seat {seat_id} not available for return reservation")
                        return render_template('error.html', error=f"Return seat {seat_id} is already booked. Please select different seats.")
                else:
                    print(f"DEBUG - No return seat for passenger {i} or no return flight")
            
            # Create initial payment record
            payment_id = generate_sequential_id("PAY", "PAYMENT", "Payment_ID", cursor)
            cursor.execute("""
                INSERT INTO PAYMENT 
                (Payment_ID, Booking_ID, Payment_Amount, Payment_Due_Date, Payment_Status, Payment_Method)
                VALUES (:payment_id, :booking_id, :amount, SYSDATE + 7, 'UNPAID', 'CREDIT_CARD')
            """,
            payment_id=payment_id,
            booking_id=booking_id,
            amount=total_amount)
            
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
            
            # In your process_booking route, update the return statement:
            return redirect(url_for('booking_confirmation', 
                        booking_id=booking_id, 
                        passenger_count=passengers,
                        total_amount=total_amount,
                        auto_download='true'))  # Add this parameter
            
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
        # Get booking and passenger details
        cursor.execute("""
            SELECT b.Booking_ID, b.Total_Amount, b.Trip_Type,
                   p.CNIC, p.P_FirstName, p.P_LastName,
                   r.Reservation_ID, r.Seat_ID, r.Seat_Cost, r.Is_Outbound,
                   s.Row_Number, s.Seat_Letter,
                   f.Flight_ID, f.Airplane_Type,
                   TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI'),
                   TO_CHAR(f.Arrival_Date_Time, 'DD-MON-YYYY HH24:MI'),
                   a1.AirportCity, a2.AirportCity,
                   tc.Travel_Class_Name
            FROM BOOKING b
            JOIN RESERVATION r ON b.Booking_ID = r.Booking_ID
            JOIN PASSENGER p ON r.Passenger_CNIC = p.CNIC
            JOIN SEAT_DETAILS s ON r.Seat_ID = s.Seat_ID
            JOIN FLIGHT_DETAILS f ON s.Flight_ID = f.Flight_ID
            JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
            JOIN TRAVEL_CLASS tc ON s.Travel_Class_ID = tc.Travel_Class_ID
            WHERE b.Booking_ID = :booking_id
            ORDER BY r.Is_Outbound DESC, p.P_LastName
        """, booking_id=booking_id)
        
        booking_data = cursor.fetchall()
        
        if not booking_data:
            return render_template('error.html', error="Booking not found")
        
        # Organize data for ticket generation
        passengers_data = []
        booking_info = {
            'booking_id': booking_data[0][0],
            'total_amount': float(booking_data[0][1]),
            'trip_type': booking_data[0][2],
            'flight_number': booking_data[0][12],
            'aircraft_type': booking_data[0][13],
            'departure_time': booking_data[0][14],
            'arrival_time': booking_data[0][15],
            'departure_city': booking_data[0][16],
            'arrival_city': booking_data[0][17],
            'travel_class': booking_data[0][18],
        }
        
        # Extract flight date from departure time
        flight_date = booking_data[0][14].split(' ')[0]
        booking_info['flight_date'] = flight_date
        
        for row in booking_data:
            passenger = {
                'cnic': row[3],
                'first_name': row[4],
                'last_name': row[5],
                'reservation_id': row[6],
                'seat_id': row[7],
                'seat_cost': float(row[8]),
                'is_outbound': row[9],
                'row_number': row[10],
                'seat_letter': row[11],
                'seat_number': f"{row[10]}{row[11]}",
            }
            passengers_data.append(passenger)
        
        # Determine flight type
        if booking_info['trip_type'] == 'ROUND_TRIP':
            outbound_passengers = [p for p in passengers_data if p['is_outbound'] == 'Y']
            return_passengers = [p for p in passengers_data if p['is_outbound'] == 'N']
            
            # Generate outbound tickets
            outbound_booking = booking_info.copy()
            outbound_booking['passengers'] = outbound_passengers
            outbound_booking['flight_type'] = 'OUTBOUND'
            
            # Generate return tickets
            return_booking = booking_info.copy()
            return_booking['passengers'] = return_passengers
            return_booking['flight_type'] = 'RETURN'
            
            # Generate tickets
            ticket_gen = TicketGenerator()
            outbound_tickets = ticket_gen.generate_all_tickets(outbound_booking, "temp_tickets")
            return_tickets = ticket_gen.generate_all_tickets(return_booking, "temp_tickets")
            
            all_tickets = outbound_tickets + return_tickets
            
        else:
            # One-way trip
            booking_info['passengers'] = passengers_data
            booking_info['flight_type'] = 'ONE-WAY'
            
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
            SELECT r.Reservation_ID, r.Booking_ID, r.Passenger_CNIC, r.Seat_ID, r.Seat_Cost,
                   p.P_FirstName, p.P_LastName,
                   s.Row_Number, s.Seat_Letter, s.Flight_ID,
                   f.Airplane_Type, f.Departure_Date_Time, f.Arrival_Date_Time,
                   a1.AirportCity, a2.AirportCity,
                   tc.Travel_Class_Name
            FROM RESERVATION r
            JOIN PASSENGER p ON r.Passenger_CNIC = p.CNIC
            JOIN SEAT_DETAILS s ON r.Seat_ID = s.Seat_ID
            JOIN FLIGHT_DETAILS f ON s.Flight_ID = f.Flight_ID
            JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
            JOIN TRAVEL_CLASS tc ON s.Travel_Class_ID = tc.Travel_Class_ID
            WHERE r.Reservation_ID = :reservation_id
        """, reservation_id=reservation_id)
        
        ticket_data = cursor.fetchone()
        
        if not ticket_data:
            return render_template('error.html', error="Ticket not found")
        
        # Prepare data for ticket template
        context = {
            'reservation_id': ticket_data[0],
            'booking_id': ticket_data[1],
            'passenger_cnic': ticket_data[2],
            'seat_id': ticket_data[3],
            'seat_cost': float(ticket_data[4]),
            'passenger_name': f"{ticket_data[5]} {ticket_data[6]}",
            'seat_number': f"{ticket_data[7]}{ticket_data[8]}",
            'flight_number': ticket_data[9],
            'aircraft_type': ticket_data[10],
            'departure_time': ticket_data[11].strftime('%d-%b-%Y %H:%M'),
            'arrival_time': ticket_data[12].strftime('%d-%b-%Y %H:%M'),
            'departure_city': ticket_data[13],
            'arrival_city': ticket_data[14],
            'travel_class': ticket_data[15],
            'flight_date': ticket_data[11].strftime('%d-%b-%Y'),
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
    cnic = request.form.get('cnic')
    booking_id = request.form.get('booking_id')
    reservation_id = request.form.get('reservation_id')
    action_type = request.form.get('action_type')
    
    if not validate_cnic(cnic):
        return render_template('error.html', error="Invalid CNIC format")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verify booking exists and belongs to the passenger
        cursor.execute("""
            SELECT b.Booking_ID, b.Booking_Status, b.Total_Amount, b.Lead_Passenger_CNIC
            FROM BOOKING b
            WHERE b.Booking_ID = :booking_id 
            AND b.Lead_Passenger_CNIC = :cnic
        """, booking_id=booking_id, cnic=cnic)
        
        booking = cursor.fetchone()
        if not booking:
            return render_template('error.html', error="Booking not found or CNIC doesn't match")
        
        # Get all reservations for this booking
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_CNIC, r.Seat_ID, r.Reservation_Status, r.Seat_Cost, r.Is_Outbound,
                   p.P_FirstName || ' ' || p.P_LastName as Passenger_Name,
                   s.Flight_ID, s.Travel_Class_ID,
                   f.Departure_Date_Time, f.Arrival_Date_Time,
                   a1.AirportCity as Departure_City, a2.AirportCity as Arrival_City,
                   tc.Travel_Class_Name
            FROM RESERVATION r
            JOIN PASSENGER p ON r.Passenger_CNIC = p.CNIC
            JOIN SEAT_DETAILS s ON r.Seat_ID = s.Seat_ID
            JOIN FLIGHT_DETAILS f ON s.Flight_ID = f.Flight_ID
            JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
            JOIN TRAVEL_CLASS tc ON s.Travel_Class_ID = tc.Travel_Class_ID
            WHERE r.Booking_ID = :booking_id 
            AND r.Reservation_Status = 'ACTIVE'
            ORDER BY f.Departure_Date_Time
        """, booking_id=booking_id)
        
        reservations = cursor.fetchall()
        
        # Convert to list of dictionaries for easier template handling
        reservation_list = []
        for res in reservations:
            reservation_list.append({
                'reservation_id': res[0],
                'passenger_cnic': res[1],
                'seat_id': res[2],
                'reservation_status': res[3],
                'seat_cost': float(res[4]),
                'is_outbound': res[5],
                'passenger_name': res[6],
                'flight_id': res[7],
                'travel_class_id': res[8],
                'departure_time': res[9].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'departure_city': res[11],
                'arrival_city': res[12],
                'travel_class': res[13],
                'seat_number': f"{res[14]}{res[15]}" if len(res) > 15 else "N/A"
            })
        
        booking_info = {
            'booking_id': booking[0],
            'booking_status': booking[1],
            'total_amount': float(booking[2])
        }
        
        # Store in session for next steps
        session['manage_booking_info'] = {
            'cnic': cnic,
            'booking_id': booking_id,
            'action_type': action_type
        }
        
        return render_template('booking_actions.html',
                             booking_info=booking_info,
                             reservations=reservation_list,
                             cnic=cnic,
                             action_type=action_type)
        
    except Exception as e:
        print("Error verifying booking:", e)
        return render_template('error.html', error="Error retrieving booking details")
    finally:
        cursor.close()
        conn.close()

@app.route('/process-booking-action', methods=['POST'])
def process_booking_action():
    cnic = request.form.get('cnic')
    booking_id = request.form.get('booking_id')
    action_type = request.form.get('action_type')
    selected_reservations = request.form.getlist('selected_reservations')
    
    if not selected_reservations:
        return render_template('error.html', error="No reservations selected")
    
    session['selected_reservations'] = selected_reservations
    session['action_booking_id'] = booking_id
    session['action_cnic'] = cnic
    
    if action_type == 'cancel':
        return cancel_reservations(selected_reservations, booking_id, cnic)
    elif action_type == 'reschedule':
        return redirect_to_reschedule(selected_reservations[0])  # Start with first reservation

def cancel_reservations(reservation_ids, booking_id, cnic):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        total_refund = 0
        
        for res_id in reservation_ids:
            # Get reservation details for cancellation log
            cursor.execute("""
                SELECT r.Seat_Cost, r.Passenger_CNIC, s.Flight_ID
                FROM RESERVATION r
                JOIN SEAT_DETAILS s ON r.Seat_ID = s.Seat_ID
                WHERE r.Reservation_ID = :res_id
            """, res_id=res_id)
            
            res_details = cursor.fetchone()
            if res_details:
                seat_cost = float(res_details[0])
                passenger_cnic = res_details[1]
                flight_id = res_details[2]
                
                # Calculate refund (example: 80% refund if cancelled more than 24 hours before flight)
                cursor.execute("""
                    SELECT Departure_Date_Time FROM FLIGHT_DETAILS WHERE Flight_ID = :flight_id
                """, flight_id=flight_id)
                departure_time = cursor.fetchone()[0]
                hours_until_flight = (departure_time - datetime.now()).total_seconds() / 3600
                
                refund_eligible = 'Y' if hours_until_flight > 24 else 'N'
                refund_amount = seat_cost * 0.8 if refund_eligible == 'Y' else 0
                total_refund += refund_amount
                
                # Update reservation status
                cursor.execute("""
                    UPDATE RESERVATION 
                    SET Reservation_Status = 'CANCELLED' 
                    WHERE Reservation_ID = :res_id
                """, res_id=res_id)
                
                # Log cancellation
                cancellation_id = f"CAN{timestamp}_{reservation_ids.index(res_id)}"
                cursor.execute("""
                    INSERT INTO CANCELLATION_LOG 
                    (Cancellation_ID, Booking_ID, Cancellation_Date, Cancelled_By_CNIC, 
                     Reason, Original_Amount, Refund_Eligible, Hours_Since_Booking)
                    VALUES (:cancel_id, :booking_id, SYSTIMESTAMP, :cnic, 
                           'Customer initiated cancellation', :amount, :refund_eligible, :hours)
                """, cancel_id=cancellation_id, booking_id=booking_id, cnic=cnic,
                   amount=seat_cost, refund_eligible=refund_eligible, hours=hours_until_flight)
        
        # Update booking status if all reservations are cancelled
        cursor.execute("""
            SELECT COUNT(*) FROM RESERVATION 
            WHERE Booking_ID = :booking_id AND Reservation_Status = 'ACTIVE'
        """, booking_id=booking_id)
        
        active_reservations = cursor.fetchone()[0]
        if active_reservations == 0:
            cursor.execute("""
                UPDATE BOOKING SET Booking_Status = 'CANCELLED' 
                WHERE Booking_ID = :booking_id
            """, booking_id=booking_id)
        
        conn.commit()
        
        # Clear session
        session.pop('selected_reservations', None)
        session.pop('action_booking_id', None)
        session.pop('action_cnic', None)
        
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
        # Get original flight details for rescheduling
        cursor.execute("""
            SELECT r.Reservation_ID, r.Booking_ID, r.Passenger_CNIC,
                   p.P_FirstName || ' ' || p.P_LastName as Passenger_Name,
                   s.Flight_ID, s.Travel_Class_ID,
                   f.Source_Airport_ID, f.Destination_Airport_ID,
                   f.Departure_Date_Time, f.Arrival_Date_Time,
                   a1.AirportCity as Departure_City, a2.AirportCity as Arrival_City,
                   tc.Travel_Class_Name
            FROM RESERVATION r
            JOIN PASSENGER p ON r.Passenger_CNIC = p.CNIC
            JOIN SEAT_DETAILS s ON r.Seat_ID = s.Seat_ID
            JOIN FLIGHT_DETAILS f ON s.Flight_ID = f.Flight_ID
            JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
            JOIN TRAVEL_CLASS tc ON s.Travel_Class_ID = tc.Travel_Class_ID
            WHERE r.Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        original_flight = cursor.fetchone()
        
        if not original_flight:
            return render_template('error.html', error="Reservation not found")
        
        original_flight_info = {
            'reservation_id': original_flight[0],
            'booking_id': original_flight[1],
            'passenger_cnic': original_flight[2],
            'passenger_name': original_flight[3],
            'flight_id': original_flight[4],
            'travel_class_id': original_flight[5],
            'departure_airport_id': original_flight[6],
            'arrival_airport_id': original_flight[7],
            'departure_time': original_flight[8].strftime('%d-%b-%Y %H:%M'),
            'arrival_time': original_flight[9].strftime('%d-%b-%Y %H:%M'),
            'departure_city': original_flight[10],
            'arrival_city': original_flight[11],
            'travel_class_name': original_flight[12],
            'departure_date': original_flight[8].strftime('%Y-%m-%d')
        }
        
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
    
    cnic = manage_booking_info.get('cnic')
    booking_id = manage_booking_info.get('booking_id')
    action_type = manage_booking_info.get('action_type')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get booking info
        cursor.execute("""
            SELECT Booking_ID, Booking_Status, Total_Amount 
            FROM BOOKING 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        booking = cursor.fetchone()
        if not booking:
            return render_template('error.html', error="Booking not found")
        
        # Get all reservations for this booking
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_CNIC, r.Seat_ID, r.Reservation_Status, r.Seat_Cost, r.Is_Outbound,
                   p.P_FirstName || ' ' || p.P_LastName as Passenger_Name,
                   s.Flight_ID, s.Travel_Class_ID,
                   f.Departure_Date_Time, f.Arrival_Date_Time,
                   a1.AirportCity as Departure_City, a2.AirportCity as Arrival_City,
                   tc.Travel_Class_Name,
                   sd.Row_Number, sd.Seat_Letter
            FROM RESERVATION r
            JOIN PASSENGER p ON r.Passenger_CNIC = p.CNIC
            JOIN SEAT_DETAILS s ON r.Seat_ID = s.Seat_ID
            JOIN FLIGHT_DETAILS f ON s.Flight_ID = f.Flight_ID
            JOIN AIRPORT a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN AIRPORT a2 ON f.Destination_Airport_ID = a2.Airport_ID
            JOIN TRAVEL_CLASS tc ON s.Travel_Class_ID = tc.Travel_Class_ID
            JOIN SEAT_DETAILS sd ON r.Seat_ID = sd.Seat_ID
            WHERE r.Booking_ID = :booking_id 
            AND r.Reservation_Status = 'ACTIVE'
            ORDER BY f.Departure_Date_Time
        """, booking_id=booking_id)
        
        reservations = cursor.fetchall()
        
        # Convert to list of dictionaries for easier template handling
        reservation_list = []
        for res in reservations:
            reservation_list.append({
                'reservation_id': res[0],
                'passenger_cnic': res[1],
                'seat_id': res[2],
                'reservation_status': res[3],
                'seat_cost': float(res[4]),
                'is_outbound': res[5],
                'passenger_name': res[6],
                'flight_id': res[7],
                'travel_class_id': res[8],
                'departure_time': res[9].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'departure_city': res[11],
                'arrival_city': res[12],
                'travel_class': res[13],
                'seat_number': f"{res[14]}{res[15]}"
            })
        
        booking_info = {
            'booking_id': booking[0],
            'booking_status': booking[1],
            'total_amount': float(booking[2])
        }
        
        return render_template('booking_actions.html',
                             booking_info=booking_info,
                             reservations=reservation_list,
                             cnic=cnic,
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
        # Get original reservation details
        cursor.execute("""
            SELECT r.Seat_ID, r.Seat_Cost, r.Passenger_CNIC, r.Booking_ID,
                   s.Flight_ID as Old_Flight_ID
            FROM RESERVATION r
            JOIN SEAT_DETAILS s ON r.Seat_ID = s.Seat_ID
            WHERE r.Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        original_res = cursor.fetchone()
        if not original_res:
            return render_template('error.html', error="Original reservation not found")
        
        old_seat_id = original_res[0]
        old_seat_cost = float(original_res[1])
        passenger_cnic = original_res[2]
        booking_id = original_res[3]
        old_flight_id = original_res[4]
        
        # Get new seat cost
        new_seat_simple = selected_seats[0]  # First selected seat
        # Extract row and letter from simple seat ID
        row_match = re.search(r'\d+', new_seat_simple)
        letter_match = re.search(r'[A-Z]', new_seat_simple)
        
        if not row_match or not letter_match:
            return render_template('error.html', error="Invalid seat format")
        
        row_num = int(row_match.group())
        seat_letter = letter_match.group()
        
        # Get actual seat ID from database
        cursor.execute("""
            SELECT Seat_ID FROM SEAT_DETAILS 
            WHERE Flight_ID = :flight_id 
            AND Row_Number = :row_num 
            AND Seat_Letter = :seat_letter
        """, flight_id=new_flight_id, row_num=row_num, seat_letter=seat_letter)
        
        new_seat_result = cursor.fetchone()
        if not new_seat_result:
            return render_template('error.html', error="New seat not found")
        
        new_seat_id = new_seat_result[0]
        
        # Get new seat cost
        cursor.execute("""
            SELECT Cost FROM FLIGHT_COST 
            WHERE Seat_ID = :seat_id 
            AND SYSDATE BETWEEN Valid_From_Date AND NVL(Valid_To_Date, SYSDATE)
        """, seat_id=new_seat_id)
        
        new_cost_result = cursor.fetchone()
        new_seat_cost = new_cost_result[0] if new_cost_result else old_seat_cost
        
        # Calculate price difference and change fee
        price_difference = new_seat_cost - old_seat_cost
        change_fee = 500.00  # Fixed change fee
        
        # Generate new reservation ID
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_reservation_id = f"RES{timestamp}_NEW"
        
        # Update old reservation status
        cursor.execute("""
            UPDATE RESERVATION 
            SET Reservation_Status = 'CHANGED' 
            WHERE Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        # Create new reservation
        cursor.execute("""
            INSERT INTO RESERVATION 
            (Reservation_ID, Booking_ID, Passenger_CNIC, Seat_ID, Date_Of_Reservation, 
             Reservation_Status, Seat_Cost, Is_Outbound)
            VALUES (:res_id, :booking_id, :cnic, :seat_id, SYSTIMESTAMP, 'ACTIVE', :cost, 'Y')
        """, 
        res_id=new_reservation_id,
        booking_id=booking_id,
        cnic=passenger_cnic,
        seat_id=new_seat_id,
        cost=new_seat_cost)
        
        # Log the change
        change_id = f"CHG{timestamp}"
        cursor.execute("""
            INSERT INTO FLIGHT_CHANGE_LOG 
            (Change_ID, Booking_ID, Change_Date, Changed_By_CNIC, Old_Seat_ID, 
             New_Seat_ID, Price_Difference, Change_Fee)
            VALUES (:change_id, :booking_id, SYSTIMESTAMP, :cnic, :old_seat, 
                   :new_seat, :price_diff, :change_fee)
        """,
        change_id=change_id,
        booking_id=booking_id,
        cnic=passenger_cnic,
        old_seat=old_seat_id,
        new_seat=new_seat_id,
        price_diff=price_difference,
        change_fee=change_fee)
        
        conn.commit()
        
        # Clear reschedule session
        session.pop('reschedule_reservation_id', None)
        session.pop('reschedule_new_flight', None)
        session.pop('reschedule_context', None)
        session.pop('reschedule_original_booking', None)
        
        return render_template('reschedule_confirmation.html',
                             booking_id=booking_id,
                             new_reservation_id=new_reservation_id,
                             new_flight_id=new_flight_id,
                             price_difference=price_difference,
                             change_fee=change_fee)
        
    except Exception as e:
        conn.rollback()
        print("Error during reschedule:", e)
        return render_template('error.html', error="Reschedule failed")
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
        WHERE table_name LIKE '%AIRPORT%' 
           OR table_name LIKE '%FLIGHT%' 
           OR table_name LIKE '%SEAT%' 
           OR table_name LIKE '%PASSENGER%' 
           OR table_name LIKE '%RESERVATION%'
           OR table_name LIKE '%BOOKING%'
           OR table_name LIKE '%PAYMENT%'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    result = "<h1>Database Tables</h1><ul>"
    for table in tables:
        result += f"<li>{table[0]}</li>"
    result += "</ul>"
    
    # Show columns for key tables
    for table_name in ['AIRPORT', 'FLIGHT_DETAILS', 'SEAT_DETAILS', 'PASSENGER', 'RESERVATION', 'BOOKING', 'PAYMENT']:
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
        # Check the specific constraint
        cursor.execute("""
            SELECT uc.table_name, ucc.column_name, uc.constraint_name, uc.constraint_type,
                   uc.r_constraint_name, uc.delete_rule
            FROM user_constraints uc
            JOIN user_cons_columns ucc ON uc.constraint_name = ucc.constraint_name
            WHERE uc.constraint_name = 'SYS_C007989'
        """)
        constraint = cursor.fetchone()
        
        result = "<h1>Constraint SYS_C007989 Details</h1>"
        if constraint:
            result += f"<p>Table: {constraint[0]}</p>"
            result += f"<p>Column: {constraint[1]}</p>"
            result += f"<p>Constraint Type: {constraint[3]}</p>"
            result += f"<p>Referenced Constraint: {constraint[4]}</p>"
            result += f"<p>Delete Rule: {constraint[5]}</p>"
            
            # If it's a foreign key, get the referenced table
            if constraint[3] == 'R':  # R means foreign key
                cursor.execute("""
                    SELECT ucc.table_name, ucc.column_name
                    FROM user_constraints uc
                    JOIN user_cons_columns ucc ON uc.constraint_name = ucc.constraint_name
                    WHERE uc.constraint_name = :ref_constraint
                """, ref_constraint=constraint[4])
                ref_constraint = cursor.fetchone()
                if ref_constraint:
                    result += f"<p>References: {ref_constraint[0]}.{ref_constraint[1]}</p>"
        else:
            result += "<p>Constraint not found</p>"
        
        return result
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()

@app.route('/debug-seats/<flight_id>')
def debug_seats(flight_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT Seat_ID, Travel_Class_ID, Row_Number, Seat_Letter FROM SEAT_DETAILS WHERE Flight_ID = :flight_id ORDER BY Row_Number, Seat_Letter", 
                     flight_id=flight_id)
        seats = cursor.fetchall()
        
        result = f"<h1>Seats for Flight {flight_id}</h1><ul>"
        for seat in seats:
            result += f"<li>ID: {seat[0]}, Class: {seat[1]}, Row: {seat[2]}, Letter: {seat[3]}</li>"
        result += "</ul>"
        
        return result
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)