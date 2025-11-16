from flask import Flask, render_template, request
from flask_cors import CORS

import uuid
from datetime import date, timedelta

from oracle import get_connection
from routes.flights import flights_bp   # JSON API: /flights/search
from routes.seats import seats_bp       # JSON API: /flights/<id>/seats

# IMPORTANT: point Flask to your templates and static files
app = Flask(
    __name__,
    template_folder="../main/templates",
    static_folder="../main/static",
)

CORS(app)

# ----------------- REGISTER BLUEPRINTS -----------------
# Register JSON API blueprints AFTER app is created
app.register_blueprint(flights_bp, url_prefix="/flights")
app.register_blueprint(seats_bp, url_prefix="/flights")

# ----------------- BASIC PAGES -----------------

@app.route("/")
def home():
    # Renders main/templates/index.html
    return render_template("index.html")

@app.route("/destination")
def destination():
    return render_template("destination.html")

@app.route("/pricing")
def pricing():
    return render_template("pricing.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# ----------------- SEARCH FLIGHTS (FORM POST) -----------------

@app.route("/search_flights", methods=["POST"])
def search_flights():
    departure_city = request.form.get("departure_city")   # e.g. 'KHI'
    arrival_city = request.form.get("arrival_city")       # e.g. 'DXB' or 'LHE'
    departure_date = request.form.get("departure_date")   # 'YYYY-MM-DD' (for display)
    travel_class = request.form.get("travel_class")       # 'ECO' / 'BUS' / 'FIR'
    passengers = request.form.get("passengers")           # string -> shown as text

    conn = get_connection()
    cursor = conn.cursor()

    # Join with MAIN_AIRPORT, MAIN_SEATDETAILS, MAIN_TRAVELCLASS, MAIN_FLIGHTCOST
    # to get city names, travel class, and lowest price per flight.
    query = """
        SELECT
            f.flight_id,
            sa.airport_city AS source_city,
            da.airport_city AS destination_city,
            TO_CHAR(f.departure_date_time, 'YYYY-MM-DD HH24:MI'),
            TO_CHAR(f.arrival_date_time,   'YYYY-MM-DD HH24:MI'),
            f.airplane_type,
            MIN(fc.cost) AS lowest_price,
            tc.name      AS travel_class
        FROM main_flightdetails f
        JOIN main_airport sa       ON f.source_airport_id      = sa.airport_id
        JOIN main_airport da       ON f.destination_airport_id = da.airport_id
        JOIN main_seatdetails s    ON s.flight_id              = f.flight_id
        JOIN main_travelclass tc   ON s.travel_class_id        = tc.travel_class_id
        JOIN main_flightcost fc    ON fc.seat_id               = s.seat_id
        WHERE f.source_airport_id      = :1
          AND f.destination_airport_id = :2
        GROUP BY
            f.flight_id,
            sa.airport_city,
            da.airport_city,
            f.departure_date_time,
            f.arrival_date_time,
            f.airplane_type,
            tc.name
        ORDER BY lowest_price ASC
    """

    cursor.execute(query, [departure_city, arrival_city])
    flights = cursor.fetchall()

    cursor.close()
    conn.close()

    # Used by search_results.html in the header
    search_criteria = {
        "departure_city": departure_city,
        "arrival_city":   arrival_city,
        "date":           departure_date,
        "travel_class":   travel_class,
        "passengers":     passengers,
    }

    return render_template(
        "search_results.html",
        flights=flights,
        search_criteria=search_criteria,
    )


# ----------------- BOOK FLIGHT (PASSENGER + RESERVATION + PAYMENT) -----------------

@app.route("/book/<flight_id>", methods=["GET", "POST"])
def book_flight(flight_id):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        # Read passenger info from form
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone = request.form.get("phone_number")
        address = request.form.get("address")
        city = request.form.get("city")
        state = request.form.get("state")
        zipcode = request.form.get("zipcode")
        country = request.form.get("country")
        seat_id = request.form.get("seat_id")

        # Generate simple IDs
        passenger_id = "P" + uuid.uuid4().hex[:5].upper()
        reservation_id = "R" + uuid.uuid4().hex[:5].upper()
        payment_id = "PAY" + uuid.uuid4().hex[:5].upper()

        # Insert passenger
        cursor.execute(
            """
            INSERT INTO main_passenger
            (passenger_id, first_name, last_name, email, phone_number,
             address, city, state, zipcode, country)
            VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10)
            """,
            [
                passenger_id,
                first_name,
                last_name,
                email,
                phone,
                address,
                city,
                state,
                zipcode,
                country,
            ],
        )

        # Insert reservation (date_of_reservation = today via SYSDATE)
        cursor.execute(
            """
            INSERT INTO main_reservation
            (reservation_id, passenger_id, seat_id, date_of_reservation)
            VALUES (:1, :2, :3, SYSDATE)
            """,
            [reservation_id, passenger_id, seat_id],
        )

        # Look up cost for the selected seat
        cursor.execute(
            """
            SELECT cost
            FROM main_flightcost
            WHERE seat_id = :1
            AND ROWNUM = 1
            """,
            [seat_id],
        )
        row = cursor.fetchone()
        amount = row[0] if row else 0

        # Insert payment record (status N, due in 7 days)
        due_date = date.today() + timedelta(days=7)
        cursor.execute(
            """
            INSERT INTO main_paymentstatus
            (payment_id, payment_status_yn, payment_due_date,
             payment_amount, reservation_id)
            VALUES (:1, 'N', :2, :3, :4)
            """,
            [payment_id, due_date, amount, reservation_id],
        )

        conn.commit()
        cursor.close()
        conn.close()

        return render_template(
            "booking_confirmation.html",
            flight_id=flight_id,
            seat_id=seat_id,
            passenger_name=f"{first_name} {last_name}",
            reservation_id=reservation_id,
            payment_id=payment_id,
            amount=amount,
        )

    # GET: show available seats for this flight
    cursor.execute(
        """
        SELECT
            s.seat_id,
            tc.name AS class_name,
            fc.cost
        FROM main_seatdetails s
        JOIN main_travelclass tc ON tc.travel_class_id = s.travel_class_id
        LEFT JOIN main_flightcost fc ON fc.seat_id = s.seat_id
        WHERE s.flight_id = :1
        ORDER BY tc.name, s.seat_id
        """,
        [flight_id],
    )
    seats = cursor.fetchall()

    # Also fetch flight basic info for display
    cursor.execute(
        """
        SELECT
            f.flight_id,
            sa.airport_city AS source_city,
            da.airport_city AS destination_city,
            TO_CHAR(f.departure_date_time, 'YYYY-MM-DD HH24:MI'),
            TO_CHAR(f.arrival_date_time, 'YYYY-MM-DD HH24:MI'),
            f.airplane_type
        FROM main_flightdetails f
        JOIN main_airport sa ON sa.airport_id = f.source_airport_id
        JOIN main_airport da ON da.airport_id = f.destination_airport_id
        WHERE f.flight_id = :1
        """,
        [flight_id],
    )
    flight = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "booking.html",
        flight=flight,
        seats=seats,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)