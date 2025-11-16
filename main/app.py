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

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get city names
        cursor.execute("SELECT airport_city FROM main_airport WHERE airport_id = :dept", dept=departure_city)
        departure_city_name = cursor.fetchone()[0]
        
        cursor.execute("SELECT airport_city FROM main_airport WHERE airport_id = :arr", arr=arrival_city)
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
                   a1.airport_city AS Source_City,
                   a2.airport_city AS Dest_City
            FROM main_flightdetails f
            JOIN main_airport a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN main_airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
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
    # Store flight selection in session
    session['selected_outbound_flight'] = flight_id
    session['trip_type'] = request.args.get('trip_type', 'one_way')
    session['passengers'] = request.args.get('passengers', 1)
    session['travel_class'] = request.args.get('travel_class', 'ECO')
    
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
                FROM main_flightdetails 
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
                       a1.airport_city AS Source_City,
                       a2.airport_city AS Dest_City
                FROM main_flightdetails f
                JOIN main_airport a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN main_airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
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
    trip_type = session.get('trip_type', 'one_way')  # Get trip type from session
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get outbound flight details
        cursor.execute("""
            SELECT f.Flight_ID, f.Airplane_Type, a1.airport_city, a2.airport_city,
                   TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
            FROM main_flightdetails f
            JOIN main_airport a1 ON f.Source_Airport_ID = a1.Airport_ID
            JOIN main_airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
            WHERE f.Flight_ID = :flight_id
        """, flight_id=flight_id)
        
        outbound_flight = cursor.fetchone()
        
        return_flight = None
        if return_flight_id:
            cursor.execute("""
                SELECT f.Flight_ID, f.Airplane_Type, a1.airport_city, a2.airport_city,
                       TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
                FROM main_flightdetails f
                JOIN main_airport a1 ON f.Source_Airport_ID = a1.Airport_ID
                JOIN main_airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
                WHERE f.Flight_ID = :flight_id
            """, flight_id=return_flight_id)
            return_flight = cursor.fetchone()
        
        # Get available seats for outbound flight with row and seat info
        cursor.execute("""
            SELECT s.Seat_ID, s.Travel_Class_ID, s.Row_Number, s.Seat_Letter,
                   CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
            FROM main_seatdetails s
            LEFT JOIN main_reservation r ON s.Seat_ID = r.Seat_ID AND r.Seat_ID LIKE :flight_pattern
            WHERE s.Flight_ID = :flight_id 
            AND s.Travel_Class_ID = :travel_class
            ORDER BY s.Row_Number, s.Seat_Letter
        """, flight_id=flight_id, travel_class=travel_class, flight_pattern=f'{flight_id}%')
        
        outbound_seats = cursor.fetchall()
        
        return_seats = []
        if return_flight_id:
            cursor.execute("""
                SELECT s.Seat_ID, s.Travel_Class_ID, s.Row_Number, s.Seat_Letter,
                       CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
                FROM main_seatdetails s
                LEFT JOIN main_reservation r ON s.Seat_ID = r.Seat_ID AND r.Seat_ID LIKE :flight_pattern
                WHERE s.Flight_ID = :flight_id 
                AND s.Travel_Class_ID = :travel_class
                ORDER BY s.Row_Number, s.Seat_Letter
            """, flight_id=return_flight_id, travel_class=travel_class, flight_pattern=f'{return_flight_id}%')
            
            return_seats = cursor.fetchall()
        
        return render_template('seat_selection.html',
                            outbound_flight=outbound_flight,
                            return_flight=return_flight,
                            outbound_seats=outbound_seats,
                            return_seats=return_seats,
                            passengers=passengers,
                            travel_class=travel_class,
                            trip_type=trip_type)  # Pass trip_type to template
        
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
            FROM main_seatdetails s
            LEFT JOIN main_reservation r ON s.Seat_ID = r.Seat_ID
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

@app.route('/book-flights', methods=['POST'])
def book_flights():
    try:
        data = request.get_json()
        selected_outbound_seats = data.get('outbound_seats', [])
        selected_return_seats = data.get('return_seats', [])
        passenger_count = int(session.get('passengers', 1))
        trip_type = session.get('trip_type', 'one_way')  # Get trip type from session
        
        # Validate seat selection
        if len(selected_outbound_seats) != passenger_count:
            return jsonify({'success': False, 'message': f'Please select exactly {passenger_count} seat(s) for outbound flight'})
        
        # Only validate return seats for round trips
        if trip_type == 'round_trip' and len(selected_return_seats) != passenger_count:
            return jsonify({'success': False, 'message': f'Please select exactly {passenger_count} seat(s) for return flight'})
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate reservation IDs and process booking
        reservation_id = f"RES{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # For demo purposes, we'll just return success
        # In real implementation, you would insert into Reservation, Payment_Status tables
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Booking successful!', 
            'reservation_id': reservation_id
        })
        
    except Exception as e:
        print("Booking error:", e)
        return jsonify({'success': False, 'message': 'Booking failed. Please try again.'})
    
@app.route('/select-return-flight/<flight_id>')
def select_return_flight(flight_id):
    session['selected_return_flight'] = flight_id
    return redirect('/seat-selection')

@app.route('/debug-schema')
def debug_schema():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT column_name, data_type 
        FROM user_tab_columns 
        WHERE table_name = 'MAIN_AIRPORT' 
        ORDER BY column_id
    """)
    airport_columns = cursor.fetchall()
    
    cursor.execute("""
        SELECT column_name, data_type 
        FROM user_tab_columns 
        WHERE table_name = 'MAIN_FLIGHTDETAILS' 
        ORDER BY column_id
    """)
    flight_columns = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    result = "<h1>Database Schema</h1>"
    result += "<h2>MAIN_AIRPORT Columns:</h2><ul>"
    for col in airport_columns:
        result += f"<li>{col[0]} - {col[1]}</li>"
    result += "</ul>"
    
    result += "<h2>MAIN_FLIGHTDETAILS Columns:</h2><ul>"
    for col in flight_columns:
        result += f"<li>{col[0]} - {col[1]}</li>"
    result += "</ul>"
    
    return result

if __name__ == '__main__':
    app.run(debug=True)