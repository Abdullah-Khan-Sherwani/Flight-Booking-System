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
        SELECT flight_id, source_airport_id, destination_airport_id,
               departure_date_time, arrival_date_time, airplane_type
        FROM main_flightdetails
        WHERE source_airport_id = :1 AND destination_airport_id = :2
    """

    cursor.execute(query, [source, destination])

    flights = []
    for row in cursor:
        flights.append({
            "flight_id": row[0],
            "source": row[1],
            "destination": row[2],
            "departure": str(row[3]),
            "arrival": str(row[4]),
            "airplane_type": row[5]
        })

    cursor.close()
    conn.close()

    return jsonify(flights)