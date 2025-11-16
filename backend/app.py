from flask import Flask, render_template, request, redirect, url_for
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
    trip_type = request.form.get("trip_type")             # 'one_way' / 'round_trip'

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
        "trip_type":      trip_type,
    }

    return render_template(
        "search_results.html",
        flights=flights,
        search_criteria=search_criteria,
    )

# ----------------- SELECT FLIGHT (FROM SEARCH RESULTS) -----------------

@app.route("/select_flight")
def select_flight():
    flight_id = request.args.get("flight_id")
    trip_type = request.args.get("trip_type", "one_way")
    passengers = request.args.get("passengers", "1")
    travel_class = request.args.get("travel_class", "")
    departure_city = request.args.get("departure_city")
    arrival_city = request.args.get("arrival_city")
    departure_date = request.args.get("date") or request.args.get("departure_date")

    # For round trip, show a page asking for return date
    if trip_type == "round_trip":
        return render_template(
            "return_flight_search.html",
            flight_id=flight_id,
            passengers=passengers,
            travel_class=travel_class,
            departure_city=departure_city,
            arrival_city=arrival_city,
            departure_date=departure_date,
        )

    # One-way: go directly to booking with passenger count
    return redirect(url_for("book_flight", flight_id=flight_id, passengers=passengers))

# ----------------- RETURN FLIGHT SEARCH (ROUND TRIP RETURN DATE) -----------------

@app.route("/return_flight_search", methods=["POST"])
def return_flight_search():
    flight_id = request.form.get("flight_id")
    passengers = request.form.get("passengers", "1")
    return_date = request.form.get("return_date")

    # For now we just pass return_date as metadata; you can later use it
    # to search for an actual return flight.
    return redirect(
        url_for(
            "book_flight",
            flight_id=flight_id,
            passengers=passengers,
            trip_type="round_trip",
            return_date=return_date,
        )
    )

# ----------------- BOOK FLIGHT (PASSENGER + RESERVATION + PAYMENT) -----------------

@app.route("/book/<flight_id>", methods=["GET", "POST"])
def book_flight(flight_id):
    # Number of passengers (from query string or form, default 1)
    passengers_str = request.args.get("passengers") or request.form.get("passengers") or "1"
    try:
        passengers_count = max(1, int(passengers_str))
    except ValueError:
        passengers_count = 1

    # ----------------- POST: CREATE BOOKING -----------------
    if request.method == "POST":
        conn = get_connection()
        cursor = conn.cursor()

        # Seats: expect comma-separated list: "PK301-8F,PK301-8E"
        seat_ids_str = request.form.get("seat_ids", "")
        seat_ids = [s.strip() for s in seat_ids_str.split(",") if s.strip()]

        # Limit number of seats to passengers_count
        if len(seat_ids) > passengers_count:
            seat_ids = seat_ids[:passengers_count]

        passenger_records = []   # [(passenger_id, full_name)]
        reservation_records = [] # [(reservation_id, seat_id, passenger_id)]
        payment_records = []     # [(payment_id, amount)]

        # If not enough seats were selected, re-render the booking page with an error
        if len(seat_ids) < passengers_count:
            # reload flight + seats like in GET
            cursor.execute(
                """
                SELECT
                    f.flight_id,
                    sa.airport_city AS source_city,
                    da.airport_city AS destination_city,
                    TO_CHAR(f.departure_date_time, 'YYYY-MM-DD HH24:MI'),
                    TO_CHAR(f.arrival_date_time,   'YYYY-MM-DD HH24:MI'),
                    f.airplane_type
                FROM main_flightdetails f
                JOIN main_airport sa ON sa.airport_id = f.source_airport_id
                JOIN main_airport da ON da.airport_id = f.destination_airport_id
                WHERE f.flight_id = :1
                """,
                [flight_id],
            )
            flight = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    s.seat_id,
                    tc.name AS class_name,
                    fc.cost,
                    CASE
                        WHEN COUNT(r.reservation_id) > 0 THEN 1
                        ELSE 0
                    END AS is_booked
                FROM main_seatdetails s
                JOIN main_travelclass tc
                    ON tc.travel_class_id = s.travel_class_id
                LEFT JOIN main_flightcost fc
                    ON fc.seat_id = s.seat_id
                LEFT JOIN main_reservation r
                    ON r.seat_id = s.seat_id
                WHERE s.flight_id = :1
                GROUP BY
                    s.seat_id,
                    tc.name,
                    fc.cost
                ORDER BY s.seat_id
                """,
                [flight_id],
            )
            seats = cursor.fetchall()

            cursor.close()
            conn.close()

            error_message = (
                f"You selected {len(seat_ids)} seat(s) for {passengers_count} passenger(s). "
                f"Please select {passengers_count} seats."
            )

            return render_template(
                "booking.html",
                flight=flight,
                seats=seats,
                passengers=passengers_count,
                error_message=error_message,
            )

        # Insert passengers + reservations + payments
        for idx in range(1, passengers_count + 1):
            # If we don't have enough seats selected, break (extra safety)
            if idx > len(seat_ids):
                break

            seat_id = seat_ids[idx - 1]

            first_name = request.form.get(f"first_name_{idx}")
            last_name = request.form.get(f"last_name_{idx}")
            email = request.form.get(f"email_{idx}")
            phone = request.form.get(f"phone_number_{idx}")

            # Per-passenger address info
            address = request.form.get(f"address_{idx}")
            city = request.form.get(f"city_{idx}")
            state = request.form.get(f"state_{idx}")
            zipcode = request.form.get(f"zipcode_{idx}")
            country = request.form.get(f"country_{idx}")

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

            # Look up cost for the selected seat (take any available cost, default 0)
            cursor.execute(
                """
                SELECT NVL(MAX(cost), 0)
                FROM main_flightcost
                WHERE seat_id = :1
                """,
                [seat_id],
            )
            row = cursor.fetchone()
            amount = row[0] if row and row[0] is not None else 0

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

            passenger_records.append((passenger_id, f"{first_name} {last_name}"))
            reservation_records.append((reservation_id, seat_id, passenger_id))
            payment_records.append((payment_id, amount))

        conn.commit()
        cursor.close()
        conn.close()

        # Use the first passenger/reservation/payment for confirmation display
        primary_passenger_name = passenger_records[0][1] if passenger_records else "N/A"
        primary_reservation_id = reservation_records[0][0] if reservation_records else "N/A"
        primary_seat_id = reservation_records[0][1] if reservation_records else "N/A"
        primary_payment_id = payment_records[0][0] if payment_records else "N/A"
        primary_amount = payment_records[0][1] if payment_records else 0

        return render_template(
            "booking_confirmation.html",
            flight_id=flight_id,
            seat_id=primary_seat_id,
            passenger_name=primary_passenger_name,
            reservation_id=primary_reservation_id,
            payment_id=primary_payment_id,
            amount=primary_amount,
            passengers_count=passengers_count,
        )

    # ----------------- GET: SHOW SEAT MAP -----------------
    conn = get_connection()
    cursor = conn.cursor()

    # Flight info for top of page
    cursor.execute(
        """
        SELECT
            f.flight_id,
            sa.airport_city AS source_city,
            da.airport_city AS destination_city,
            TO_CHAR(f.departure_date_time, 'YYYY-MM-DD HH24:MI'),
            TO_CHAR(f.arrival_date_time,   'YYYY-MM-DD HH24:MI'),
            f.airplane_type
        FROM main_flightdetails f
        JOIN main_airport sa ON sa.airport_id = f.source_airport_id
        JOIN main_airport da ON da.airport_id = f.destination_airport_id
        WHERE f.flight_id = :1
        """,
        [flight_id],
    )
    flight = cursor.fetchone()

    # Seats + whether they are already booked
    cursor.execute(
        """
        SELECT
            s.seat_id,
            tc.name AS class_name,
            fc.cost,
            CASE
                WHEN COUNT(r.reservation_id) > 0 THEN 1
                ELSE 0
            END AS is_booked
        FROM main_seatdetails s
        JOIN main_travelclass tc
            ON tc.travel_class_id = s.travel_class_id
        LEFT JOIN main_flightcost fc
            ON fc.seat_id = s.seat_id
        LEFT JOIN main_reservation r
            ON r.seat_id = s.seat_id
        WHERE s.flight_id = :1
        GROUP BY
            s.seat_id,
            tc.name,
            fc.cost
        ORDER BY s.seat_id
        """,
        [flight_id],
    )
    seats = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "booking.html",
        flight=flight,
        seats=seats,
        passengers=passengers_count,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)