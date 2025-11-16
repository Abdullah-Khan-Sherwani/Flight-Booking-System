from flask import Blueprint, jsonify
from oracle import get_connection

seats_bp = Blueprint("seats", __name__)

@seats_bp.route("/<flight_id>/seats", methods=["GET"])
def get_seats(flight_id):
    conn = get_connection()
    cur = conn.cursor()

    query = """
    SELECT
        s.seat_id,
        tc.name AS class_name,
        fc.cost
    FROM main_seatdetails s
    JOIN main_travelclass tc ON s.travel_class_id = tc.travel_class_id
    LEFT JOIN main_flightcost fc ON fc.seat_id = s.seat_id
    WHERE s.flight_id = :1
    ORDER BY tc.name, s.seat_id
    """

    cur.execute(query, [flight_id])
    rows = cur.fetchall()

    seats = [
        {
            "seat_id": r[0],
            "class": r[1],
            "price": r[2],
        }
        for r in rows
    ]

    cur.close()
    conn.close()

    return jsonify(seats)