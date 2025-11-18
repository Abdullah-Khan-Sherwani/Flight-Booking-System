# app.py
from flask import Flask, render_template, request, redirect, session, jsonify
from db import get_connection
from datetime import datetime, timedelta
import json

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
        # Get city names - using correct table and column names
        cursor.execute("SELECT AirportCity FROM Airport WHERE Airport_ID = :dept", dept=departure_city)
        departure_city_name = cursor.fetchone()[0]
        
        cursor.execute("SELECT AirportCity FROM Airport WHERE Airport_ID = :arr", arr=arrival_city)
        arrival_city_name = cursor.fetchone()[0]
        
        # Map travel class codes to full names
        class_names = {
            'ECO': 'Economy',
            'BUS': 'Business', 
            'FIR': 'First Class'
        }
        travel_class_name = class_names.get(travel_class, travel_class)

        # Get flights - using correct table and column names
        query = """
            SELECT f.Flight_ID,
                   f.Source_Airport_ID,
                   f.Destination_Airport_ID,
                   TO_CHAR(f.Departure_Date_Time, 'YYYY-MM-DD HH24:MI'),
                   TO_CHAR(f.Arrival_Date_Time, 'YYYY-MM-DD HH24:MI'),
                   f.Airplane_Type,
                   a1.AirportCity AS Source_City,
                   a2.AirportCity AS Dest_City
            FROM Flight_Details f
            JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
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
                FROM Flight_Details 
                WHERE Flight_ID = :flight_id
            """, flight_id=session['selected_outbound_flight'])
            
            flight_data = cursor.fetchone()
            if not flight_data:
                return render_template("return_flight_results.html", flights=[], error="Original flight not found")
                
            return_departure = flight_data[1]  # Destination becomes source for return
            return_arrival = flight_data[0]    # Source becomes destination for return
            
            print(f"Searching return flights: {return_departure} to {return_arrival} on {return_date}")
            
            # Search for return flights - USING CORRECT TABLE NAMES
            query = """
                SELECT f.Flight_ID,
                       f.Source_Airport_ID,
                       f.Destination_Airport_ID,
                       TO_CHAR(f.Departure_Date_Time, 'YYYY-MM-DD HH24:MI'),
                       TO_CHAR(f.Arrival_Date_Time, 'YYYY-MM-DD HH24:MI'),
                       f.Airplane_Type,
                       a1.AirportCity AS Source_City,
                       a2.AirportCity AS Dest_City
                FROM Flight_Details f
                JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
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
    flight_id = session.get('selected_outbound_flight')
    return_flight_id = session.get('selected_return_flight')
    passengers = int(session.get('passengers', 1))
    travel_class = session.get('travel_class', 'ECO')
    trip_type = session.get('trip_type', 'one_way')
    
    print(f"DEBUG - travel_class from session: {travel_class}")
    print(f"DEBUG - passengers: {passengers}")
    print(f"DEBUG - trip_type: {trip_type}")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get outbound flight details
        cursor.execute("""
            SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                   TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
            FROM Flight_Details f
            JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
            WHERE f.Flight_ID = :flight_id
        """, flight_id=flight_id)
        
        outbound_flight = cursor.fetchone()
        
        return_flight = None
        if return_flight_id:
            cursor.execute("""
                SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                       TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
                FROM Flight_Details f
                JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
                WHERE f.Flight_ID = :flight_id
            """, flight_id=return_flight_id)
            return_flight = cursor.fetchone()
        
        # Get available seats for outbound flight
        cursor.execute("""
            SELECT s.Seat_ID, s.Travel_Class_ID, s.Row_Number, s.Seat_Letter,
                   CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
            FROM Seat_Details s
            LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID AND r.Seat_ID LIKE :flight_pattern
            WHERE s.Flight_ID = :flight_id 
            AND s.Travel_Class_ID = :travel_class
            ORDER BY s.Row_Number, s.Seat_Letter
        """, flight_id=flight_id, travel_class=travel_class, flight_pattern=f'{flight_id}%')
        
        outbound_seats = cursor.fetchall()
        
        # Get ALL booked seats for outbound flight (regardless of class) for the seat map
        cursor.execute("""
            SELECT s.Row_Number, s.Seat_Letter
            FROM Seat_Details s
            JOIN Reservation r ON s.Seat_ID = r.Seat_ID
            WHERE s.Flight_ID = :flight_id
        """, flight_id=flight_id)
        
        booked_outbound_seats = [f"{row[0]}{row[1]}" for row in cursor.fetchall()]
        print(f"DEBUG - Booked outbound seats: {booked_outbound_seats}")
        
        return_seats = []
        booked_return_seats = []
        
        if return_flight_id:
            cursor.execute("""
                SELECT s.Seat_ID, s.Travel_Class_ID, s.Row_Number, s.Seat_Letter,
                       CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
                FROM Seat_Details s
                LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID AND r.Seat_ID LIKE :flight_pattern
                WHERE s.Flight_ID = :flight_id 
                AND s.Travel_Class_ID = :travel_class
                ORDER BY s.Row_Number, s.Seat_Letter
            """, flight_id=return_flight_id, travel_class=travel_class, flight_pattern=f'{return_flight_id}%')
            
            return_seats = cursor.fetchall()
            
            # Get ALL booked seats for return flight
            cursor.execute("""
                SELECT s.Row_Number, s.Seat_Letter
                FROM Seat_Details s
                JOIN Reservation r ON s.Seat_ID = r.Seat_ID
                WHERE s.Flight_ID = :flight_id
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
                            trip_type=trip_type)
        
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
            FROM Seat_Details s
            LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID
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
            # Get outbound flight details - using correct table names
            cursor.execute("""
                SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                       TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
                FROM Flight_Details f
                JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
                WHERE f.Flight_ID = :flight_id
            """, flight_id=flight_id)
            outbound_flight = cursor.fetchone()
            
            return_flight = None
            if return_flight_id:
                cursor.execute("""
                    SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
                           TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
                    FROM Flight_Details f
                    JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
                    JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
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

@app.route('/process-booking', methods=['POST'])
def process_booking():
    try:
        # Get passenger data from form
        passengers = int(session.get('passengers', 1))
        passenger_data = []
        
        for i in range(passengers):
            passenger_data.append({
                'first_name': request.form.get(f'first_name_{i}'),
                'last_name': request.form.get(f'last_name_{i}'),
                'email': request.form.get(f'email_{i}'),
                'phone': request.form.get(f'phone_{i}'),
                'address': request.form.get(f'address_{i}'),
                'city': request.form.get(f'city_{i}'),
                'state': request.form.get(f'state_{i}'),
                'postal_code': request.form.get(f'postal_code_{i}'),
                'country': request.form.get(f'country_{i}')
            })
        
        # Get seat selections
        selected_outbound_seats = request.form.getlist('selected_outbound_seats')
        selected_return_seats = request.form.getlist('selected_return_seats')
        outbound_flight_id = session.get('selected_outbound_flight')
        return_flight_id = session.get('selected_return_flight')
        
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
            
            # Generate reservation ID
            reservation_id = generate_sequential_id("RES", "Reservation", "Reservation_ID", cursor)
            
            # First, convert simple seat numbers (like "1A") to proper seat IDs
            def convert_seat_id(flight_id, simple_seat_id):
                """Convert simple seat ID like '1A' to proper seat ID like 'FLIGHT_ID-1A'"""
                if not simple_seat_id or not flight_id:
                    return None
                # If it's already a proper seat ID, return as is
                if '-' in simple_seat_id:
                    return simple_seat_id
                # Otherwise create proper seat ID
                return f"{flight_id}-{simple_seat_id}"
            
            # Convert all seat IDs to proper format
            proper_outbound_seats = [convert_seat_id(outbound_flight_id, seat) for seat in selected_outbound_seats if seat and seat.strip()]
            proper_return_seats = [convert_seat_id(return_flight_id, seat) for seat in selected_return_seats if seat and seat.strip()]
            
            print(f"DEBUG - Proper outbound seats: {proper_outbound_seats}")
            print(f"DEBUG - Proper return seats: {proper_return_seats}")
            
            # Calculate total amount from Flight_Cost table
            for seat in proper_outbound_seats:
                if seat:  # Check if seat is not empty
                    print(f"DEBUG - Checking cost for seat: {seat}")
                    cursor.execute("SELECT Cost FROM Flight_Cost WHERE Seat_ID = :seat_id", seat_id=seat)
                    cost_result = cursor.fetchone()
                    if cost_result:
                        total_amount += cost_result[0]
                        print(f"DEBUG - Cost for {seat}: {cost_result[0]}")
                    else:
                        print(f"DEBUG - No cost found for seat: {seat}")
                        # If no cost found, use a default amount based on class
                        travel_class = session.get('travel_class', 'ECO')
                        default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                        default_amount = default_costs.get(travel_class, 100)
                        total_amount += default_amount
                        print(f"DEBUG - Using default cost for {seat}: {default_amount}")
            
            for seat in proper_return_seats:
                if seat:  # Check if seat is not empty
                    print(f"DEBUG - Checking cost for return seat: {seat}")
                    cursor.execute("SELECT Cost FROM Flight_Cost WHERE Seat_ID = :seat_id", seat_id=seat)
                    cost_result = cursor.fetchone()
                    if cost_result:
                        total_amount += cost_result[0]
                        print(f"DEBUG - Cost for return {seat}: {cost_result[0]}")
                    else:
                        print(f"DEBUG - No cost found for return seat: {seat}")
                        # If no cost found, use a default amount based on class
                        travel_class = session.get('travel_class', 'ECO')
                        default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                        default_amount = default_costs.get(travel_class, 100)
                        total_amount += default_amount
                        print(f"DEBUG - Using default cost for return {seat}: {default_amount}")
            
            print(f"DEBUG - Total amount: {total_amount}")
            
            # First, verify all seats exist before processing
            all_seats = [s for s in proper_outbound_seats if s] + [s for s in proper_return_seats if s]
            
            for seat in all_seats:
                cursor.execute("SELECT 1 FROM Seat_Details WHERE Seat_ID = :seat_id", seat_id=seat)
                if not cursor.fetchone():
                    print(f"ERROR - Seat {seat} not found in database")
                    return render_template('error.html', error=f"Seat {seat} not found in database. Please try selecting different seats.")
            
            # Process each passenger
            for i, passenger in enumerate(passenger_data):
                # Generate unique passenger ID
                passenger_id = generate_sequential_id("PASS", "Passenger", "Passenger_ID", cursor)
                
                print(f"DEBUG - Processing passenger {i}: {passenger_id}")
                
                # Insert passenger
                cursor.execute("""
                    INSERT INTO Passenger 
                    (Passenger_ID, P_FirstName, P_LastName, P_Email, P_PhoneNumber, P_Address, P_City, P_State, P_Zipcode, P_Country)
                    VALUES (:id, :first_name, :last_name, :email, :phone, :address, :city, :state, :postal_code, :country)
                """, 
                id=passenger_id,
                first_name=passenger['first_name'],
                last_name=passenger['last_name'], 
                email=passenger['email'],
                phone=passenger['phone'],
                address=passenger['address'],
                city=passenger['city'],
                state=passenger['state'],
                postal_code=passenger['postal_code'],
                country=passenger['country'])
                
                # Create reservation for outbound flight if seat exists and is valid
                if i < len(proper_outbound_seats) and proper_outbound_seats[i]:
                    seat_id = proper_outbound_seats[i]
                    res_id = generate_sequential_id("RESV", "Reservation", "Reservation_ID", cursor)
                    
                    print(f"DEBUG - Creating outbound reservation: {res_id} for seat {seat_id}")
                    
                    # Verify the seat exists and is not already booked
                    cursor.execute("""
                        SELECT 1 FROM Seat_Details s 
                        LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID 
                        WHERE s.Seat_ID = :seat_id AND r.Reservation_ID IS NULL
                    """, seat_id=seat_id)
                    
                    if cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO Reservation 
                            (Reservation_ID, Passenger_ID, Seat_ID, Date_Of_Reservation)
                            VALUES (:res_id, :pass_id, :seat_id, SYSDATE)
                        """, 
                        res_id=res_id,
                        pass_id=passenger_id,
                        seat_id=seat_id)
                        
                        # Create payment status for outbound
                        pay_id = generate_sequential_id("PAY", "Payment_Status", "Payment_ID", cursor)
                        
                        seat_amount = total_amount / max(1, len([s for s in proper_outbound_seats if s]))
                        print(f"DEBUG - Creating payment for outbound: {pay_id}, amount: {seat_amount}")
                            
                        cursor.execute("""
                            INSERT INTO Payment_Status 
                            (Payment_ID, Payment_Status_YN, Payment_Due_Date, Payment_Amount, Reservation_ID)
                            VALUES (:pay_id, 'Y', SYSDATE + 7, :amount, :res_id)
                        """,
                        pay_id=pay_id,
                        amount=seat_amount,
                        res_id=res_id)
                    else:
                        print(f"ERROR - Seat {seat_id} not available for outbound reservation")
                        return render_template('error.html', error=f"Seat {seat_id} is already booked. Please select different seats.")
                
                # Process return flight if exists
                if return_flight_id and i < len(proper_return_seats) and proper_return_seats[i]:
                    seat_id = proper_return_seats[i]
                    res_id = generate_sequential_id("RESV_RET", "Reservation", "Reservation_ID", cursor)
                    
                    print(f"DEBUG - Creating return reservation: {res_id} for seat {seat_id}")
                    
                    # Verify the seat exists and is not already booked
                    cursor.execute("""
                        SELECT 1 FROM Seat_Details s 
                        LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID 
                        WHERE s.Seat_ID = :seat_id AND r.Reservation_ID IS NULL
                    """, seat_id=seat_id)
                    
                    if cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO Reservation 
                            (Reservation_ID, Passenger_ID, Seat_ID, Date_Of_Reservation)
                            VALUES (:res_id, :pass_id, :seat_id, SYSDATE)
                        """, 
                        res_id=res_id,
                        pass_id=passenger_id,
                        seat_id=seat_id)
                        
                        # Create payment status for return
                        pay_id = generate_sequential_id("PAY_RET", "Payment_Status", "Payment_ID", cursor)
                        
                        seat_amount = total_amount / max(1, len([s for s in proper_return_seats if s]))
                        print(f"DEBUG - Creating payment for return: {pay_id}, amount: {seat_amount}")
                            
                        cursor.execute("""
                            INSERT INTO Payment_Status 
                            (Payment_ID, Payment_Status_YN, Payment_Due_Date, Payment_Amount, Reservation_ID)
                            VALUES (:pay_id, 'Y', SYSDATE + 7, :amount, :res_id)
                        """,
                        pay_id=pay_id,
                        amount=seat_amount,
                        res_id=res_id)
                    else:
                        print(f"ERROR - Seat {seat_id} not available for return reservation")
                        return render_template('error.html', error=f"Return seat {seat_id} is already booked. Please select different seats.")
            
            conn.commit()
            
            # Clear session data
            session.pop('selected_outbound_seats', None)
            session.pop('selected_return_seats', None)
            session.pop('selected_outbound_flight', None)
            session.pop('selected_return_flight', None)
            
            return render_template('booking_confirmation.html', 
                                reservation_id=reservation_id,
                                passenger_count=passengers,
                                total_amount=total_amount)
            
        except Exception as e:
            conn.rollback()
            print("Database error during booking:", e)
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
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    result = "<h1>Database Tables</h1><ul>"
    for table in tables:
        result += f"<li>{table[0]}</li>"
    result += "</ul>"
    
    # Show columns for key tables
    for table_name in ['AIRPORT', 'FLIGHT_DETAILS', 'SEAT_DETAILS', 'PASSENGER', 'RESERVATION']:
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

@app.route('/debug-seats/<flight_id>')
def debug_seats(flight_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT Seat_ID, Travel_Class_ID, Row_Number, Seat_Letter FROM Seat_Details WHERE Flight_ID = :flight_id ORDER BY Row_Number, Seat_Letter", 
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

@app.route('/debug-constraints')
def debug_constraints():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check unique constraints
        cursor.execute("""
            SELECT uc.constraint_name, uc.table_name, ucc.column_name, uc.constraint_type
            FROM user_constraints uc
            JOIN user_cons_columns ucc ON uc.constraint_name = ucc.constraint_name
            WHERE uc.constraint_name = 'SYS_C007710'
        """)
        constraint = cursor.fetchone()
        
        if constraint:
            result = f"<h1>Constraint SYS_C007710</h1>"
            result += f"<p>Table: {constraint[1]}</p>"
            result += f"<p>Column: {constraint[2]}</p>"
            result += f"<p>Type: {constraint[3]}</p>"
        else:
            result = "<h1>Constraint not found</h1>"
        
        return result
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()

@app.route('/debug-all-constraints')
def debug_all_constraints():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check all constraints for the problematic tables
        cursor.execute("""
            SELECT uc.constraint_name, uc.table_name, ucc.column_name, uc.constraint_type,
                   uc.search_condition, uc.status
            FROM user_constraints uc
            JOIN user_cons_columns ucc ON uc.constraint_name = ucc.constraint_name
            WHERE uc.table_name IN ('PASSENGER', 'RESERVATION', 'PAYMENT_STATUS', 'SEAT_DETAILS')
            ORDER BY uc.table_name, uc.constraint_type
        """)
        constraints = cursor.fetchall()
        
        result = "<h1>All Constraints for Booking Tables</h1>"
        result += "<table border='1'><tr><th>Constraint</th><th>Table</th><th>Column</th><th>Type</th><th>Condition</th><th>Status</th></tr>"
        for constraint in constraints:
            result += f"<tr><td>{constraint[0]}</td><td>{constraint[1]}</td><td>{constraint[2]}</td><td>{constraint[3]}</td><td>{constraint[4] or 'N/A'}</td><td>{constraint[5]}</td></tr>"
        result += "</table>"
        
        # Also show current data counts
        result += "<h2>Current Data Counts</h2>"
        for table in ['PASSENGER', 'RESERVATION', 'PAYMENT_STATUS']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            result += f"<p>{table}: {count} records</p>"
        
        return result
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)