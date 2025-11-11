# app.py
from flask import Flask, render_template, request, redirect
from db import get_connection
from datetime import datetime
from flask_wtf import CSRFProtect

app = Flask(__name__)

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

    print(f"Searching flights: {departure_city} to {arrival_city} on {departure_date}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # First, get the full city names for the search criteria
        cursor.execute("""
            SELECT airport_city FROM main_airport WHERE airport_id = :dept
        """, dept=departure_city)
        departure_city_name = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT airport_city FROM main_airport WHERE airport_id = :arr
        """, arr=arrival_city)
        arrival_city_name = cursor.fetchone()[0]
        
        # Map travel class codes to full names
        class_names = {
            'ECO': 'Economy',
            'BUS': 'Business', 
            'FIR': 'First Class'
        }
        travel_class_name = class_names.get(travel_class, travel_class)

        # Then get the flights
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

        # Debug: Print what we found
        print(f"Found {len(flights)} flights")
        for flight in flights:
            print(f"Flight: {flight}")

        context = {
            "flights": flights,
            "search_criteria": {
                "departure_city": departure_city_name,  # Use full city name
                "arrival_city": arrival_city_name,      # Use full city name
                "date": departure_date,
                "travel_class": travel_class_name,      # Use full class name
                "passengers": passengers
            }
        }

        return render_template("search_results.html", **context)

    except Exception as e:
        print("Error while searching flights:", e)
        return render_template("search_results.html", flights=[], error="No flights found or invalid input")

    finally:
        cursor.close()
        conn.close()


@app.route('/debug-schema')
def debug_schema():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check airport table structure
    cursor.execute("""
        SELECT column_name, data_type 
        FROM user_tab_columns 
        WHERE table_name = 'MAIN_AIRPORT' 
        ORDER BY column_id
    """)
    airport_columns = cursor.fetchall()
    
    # Check flightdetails table structure
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
