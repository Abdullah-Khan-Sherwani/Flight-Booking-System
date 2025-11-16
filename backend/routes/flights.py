from flask import Blueprint, request, jsonify
from oracle import get_connection

flights_bp = Blueprint("flights", __name__)

@flights_bp.route("/search", methods=["GET"])
def search_flights():
    source = request.args.get("source")
    destination = request.args.get("destination")

    if not source or not destination:
        return jsonify({"error": "source and destination are required"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            f.flight_id,
            f.source_airport_id,
            f.destination_airport_id,
            TO_CHAR(f.departure_date_time, 'YYYY-MM-DD HH24:MI'),
            TO_CHAR(f.arrival_date_time, 'YYYY-MM-DD HH24:MI'),
            f.airplane_type,
            MIN(fc.cost) AS lowest_price,
            tc.name AS travel_class
        FROM main_flightdetails f
        JOIN main_seatdetails s ON s.flight_id = f.flight_id
        JOIN main_travelclass tc ON tc.travel_class_id = s.travel_class_id
        JOIN main_flightcost fc ON fc.seat_id = s.seat_id
        WHERE f.source_airport_id = :1 
          AND f.destination_airport_id = :2
        GROUP BY 
            f.flight_id,
            f.source_airport_id,
            f.destination_airport_id,
            f.departure_date_time,
            f.arrival_date_time,
            f.airplane_type,
            tc.name
        ORDER BY lowest_price
    """

    cursor.execute(query, [source, destination])

    flights = []
    for row in cursor:
        flights.append({
            "flight_id": row[0],
            "source": row[1],
            "destination": row[2],
            "departure": row[3],
            "arrival": row[4],
            "airplane_type": row[5],
            "lowest_price": row[6],
            "travel_class": row[7]
        })

    cursor.close()
    conn.close()

    return jsonify(flights)

# http://127.0.0.1:5000/flights/search?source=KHI&destination=DXB