from datetime import datetime, date, timedelta
from oracle import get_connection
import oracledb


def seed():
    conn = get_connection()
    cur = conn.cursor()

    print("Clearing old data...")

    # Delete children → parents to respect FKs
    cur.execute("DELETE FROM main_flightcost")
    cur.execute("DELETE FROM main_serviceoffering")
    cur.execute("DELETE FROM main_paymentstatus")
    cur.execute("DELETE FROM main_reservation")
    cur.execute("DELETE FROM main_seatdetails")
    cur.execute("DELETE FROM main_travelclass")
    cur.execute("DELETE FROM main_flightservice")
    cur.execute("DELETE FROM main_passenger")
    cur.execute("DELETE FROM main_flightdetails")
    cur.execute("DELETE FROM main_airport")

    print("Inserting airports...")
    airports = [
        ("KHI", "Karachi",     "Pakistan"),
        ("LHE", "Lahore",      "Pakistan"),
        ("ISB", "Islamabad",   "Pakistan"),
        ("PEW", "Peshawar",    "Pakistan"),
        ("UET", "Quetta",      "Pakistan"),
        ("MUX", "Multan",      "Pakistan"),
        ("DXB", "Dubai",       "UAE"),
    ]
    cur.executemany(
        "INSERT INTO main_airport (airport_id, airport_city, airport_country) "
        "VALUES (:1, :2, :3)",
        airports,
    )

    print("Inserting travel classes...")
    travel_classes = [
        ("ECO", "Economy", 150),
        ("BUS", "Business", 30),
        ("FIR", "First Class", 10),
    ]
    cur.executemany(
        "INSERT INTO main_travelclass (travel_class_id, name, capacity) "
        "VALUES (:1, :2, :3)",
        travel_classes,
    )

    print("Inserting flights...")
    flights = [
    (
        "PK301", "KHI", "DXB",
        oracledb.Timestamp(2025, 11, 15, 10, 0, 0),
        oracledb.Timestamp(2025, 11, 15, 14, 0, 0),
        "Airbus A320",
    ),
    (
        "PK302", "DXB", "KHI",
        oracledb.Timestamp(2025, 11, 16, 18, 0, 0),
        oracledb.Timestamp(2025, 11, 16, 22, 0, 0),
        "Boeing 737",
    ),
    (
        "PK101", "KHI", "LHE",
        oracledb.Timestamp(2025, 11, 17, 9, 0, 0),
        oracledb.Timestamp(2025, 11, 17, 10, 30, 0),
        "Airbus A320",
    ),
    (
        "PK102", "LHE", "KHI",
        oracledb.Timestamp(2025, 11, 17, 18, 0, 0),
        oracledb.Timestamp(2025, 11, 17, 19, 30, 0),
        "Boeing 737",
    ),
    ]
    cur.executemany(
        """
        INSERT INTO main_flightdetails
        (flight_id, source_airport_id, destination_airport_id,
        departure_date_time, arrival_date_time, airplane_type)
        VALUES (:1, :2, :3, :4, :5, :6)
        """,
        flights,
    )

    print("Inserting seats...")

    # dynamic full seat map generator
    rows = range(1, 31)       # rows 1–30
    letters = ["A", "B", "C", "D", "E", "F"]

    seats = []
    for flight_id, source, dest, dep, arr, airplane in flights:
        for row in rows:
            for letter in letters:
                # Make seat_id globally unique by prefixing with flight_id
                # e.g. PK301-12A
                seat_code = f"{row}{letter}"
                seat_id = f"{flight_id}-{seat_code}"
                # class rules
                if row <= 3:
                    travel_class_id = "BUS"
                elif row <= 5:
                    travel_class_id = "FIR"
                else:
                    travel_class_id = "ECO"
                seats.append((seat_id, travel_class_id, flight_id))

    cur.executemany(
        """
        INSERT INTO main_seatdetails
        (seat_id, travel_class_id, flight_id)
        VALUES (:1, :2, :3)
        """,
        seats,
    )

    print("Inserting passengers...")
    passengers = [
        ("P001", "Hamza", "Kashif", "hamzahisam@gmail.com", "03341371292",
         "Some Street", "Karachi", "Sindh", "75300", "Pakistan"),
        ("P002", "Ali", "Ahmed", "ali@example.com", "03001234567",
         "Another Street", "Lahore", "Punjab", "54000", "Pakistan"),
    ]
    cur.executemany(
        """
        INSERT INTO main_passenger
        (passenger_id, first_name, last_name, email, phone_number,
         address, city, state, zipcode, country)
        VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10)
        """,
        passengers,
    )

    print("Inserting reservations...")
    today = date.today()
    reservations = [
        ("R001", "P001", "PK301-1A",  today),
        ("R002", "P002", "PK301-22C", today),
    ]
    cur.executemany(
        """
        INSERT INTO main_reservation
        (reservation_id, passenger_id, seat_id, date_of_reservation)
        VALUES (:1, :2, :3, :4)
        """,
        reservations,
    )

    print("Inserting payment status...")
    payments = [
        ("PAY001", "Y", today,            65000, "R001"),
        ("PAY002", "N", today + timedelta(days=7), 40000, "R002"),
    ]
    cur.executemany(
        """
        INSERT INTO main_paymentstatus
        (payment_id, payment_status_yn, payment_due_date,
         payment_amount, reservation_id)
        VALUES (:1, :2, :3, :4, :5)
        """,
        payments,
    )

    print("Inserting flight services...")
    services = [
        ("MEAL", "Meals Included"),
        ("WIFI", "WiFi"),
        ("TV",   "In-Flight Entertainment"),
    ]
    cur.executemany(
        """
        INSERT INTO main_flightservice
        (service_id, service_name)
        VALUES (:1, :2)
        """,
        services,
    )

    print("Inserting service offerings...")
    service_offerings = [
        # travel_class_id, service_id, offered_yn, from_date, to_date
        ("BUS", "MEAL", "Y", today, today + timedelta(days=90)),
        ("BUS", "WIFI", "Y", today, today + timedelta(days=90)),
        ("ECO", "MEAL", "Y", today, today + timedelta(days=90)),
        ("ECO", "WIFI", "N", today, today + timedelta(days=90)),
    ]
    cur.executemany(
        """
        INSERT INTO main_serviceoffering
        (travel_class_id, service_id, offered_yn, from_date, to_date)
        VALUES (:1, :2, :3, :4, :5)
        """,
        service_offerings,
    )

    print("Inserting flight costs...")
    flight_costs = [
        # seat_id, valid_from_date, valid_to_date, cost
        ("PK301-1A",  today, today + timedelta(days=30), 65000),
        ("PK301-22C", today, today + timedelta(days=30), 40000),
        ("PK301-1B",  today, today + timedelta(days=30), 63000),
        ("PK301-22D", today, today + timedelta(days=30), 38000),
    ]
    cur.executemany(
        """
        INSERT INTO main_flightcost
        (seat_id, valid_from_date, valid_to_date, cost)
        VALUES (:1, :2, :3, :4)
        """,
        flight_costs,
    )

    conn.commit()
    cur.close()
    conn.close()
    print("\nALL DATA INSERTED SUCCESSFULLY ✔")


if __name__ == "__main__":
    seed()