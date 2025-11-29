# routes/flights.py
# Flight search and pricing routes

from flask import Blueprint, render_template, request, redirect, session, jsonify
from db import get_connection
from utils import get_class_name

flights_bp = Blueprint('flights', __name__)


@flights_bp.route('/pricing', methods=['GET', 'POST'])
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


@flights_bp.route('/search-flights', methods=['GET'])
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
        
        travel_class_name = get_class_name(travel_class)

        # Get flights using new schema
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


@flights_bp.route('/search-flights', methods=['POST'])
def search_flights():
    departure_city = request.form.get('departure_city')
    arrival_city = request.form.get('arrival_city')
    departure_date = request.form.get('departure_date')
    travel_class = request.form.get('travel_class')
    passengers = request.form.get('passengers')
    trip_type = request.form.get('trip_type', 'one_way')

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
        
        travel_class_name = get_class_name(travel_class)

        # Get flights using new schema
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


@flights_bp.route('/select-flight/<flight_id>')
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
        return redirect('/passenger-info')


@flights_bp.route('/return-flight-search', methods=['GET', 'POST'])
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
                
            return_departure = flight_data[1]
            return_arrival = flight_data[0]
            
            print(f"Searching return flights: {return_departure} to {return_arrival} on {return_date}")
            
            # Search for return flights
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
        return render_template("return_flight_search.html")


@flights_bp.route('/select-return-flight/<flight_id>')
def select_return_flight(flight_id):
    session['selected_return_flight'] = flight_id
    return redirect('/passenger-info')


@flights_bp.route('/get-seat-status/<flight_id>')
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
