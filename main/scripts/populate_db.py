# main/populate_db.py

from datetime import datetime, date, timedelta
from django.utils import timezone

from main.models import (
    Airport, FlightDetails, Passenger, TravelClass,
    SeatDetails, Reservation, PaymentStatus,
    FlightService, ServiceOffering, FlightCost
)

def run():

    print("Clearing old data...")
    FlightCost.objects.all().delete()
    ServiceOffering.objects.all().delete()
    FlightService.objects.all().delete()
    PaymentStatus.objects.all().delete()
    Reservation.objects.all().delete()
    SeatDetails.objects.all().delete()
    TravelClass.objects.all().delete()
    Passenger.objects.all().delete()
    FlightDetails.objects.all().delete()
    Airport.objects.all().delete()

    print("Inserting airports...")
    airport_khi = Airport.objects.create(
        airport_id="KHI",
        airport_city="Karachi",
        airport_country="Pakistan"
    )

    airport_dxb = Airport.objects.create(
        airport_id="DXB",
        airport_city="Dubai",
        airport_country="UAE"
    )

    airport_lhe = Airport.objects.create(
        airport_id="LHE",
        airport_city="Lahore",
        airport_country="Pakistan"
    )

    print("Inserting travel classes...")
    eco = TravelClass.objects.create(travel_class_id="ECO", name="Economy", capacity=150)
    bus = TravelClass.objects.create(travel_class_id="BUS", name="Business", capacity=30)

    print("Inserting flights...")
    flight1 = FlightDetails.objects.create(
        flight_id="PK301",
        source_airport=airport_khi,
        destination_airport=airport_dxb,
        departure_date_time=datetime(2025, 11, 15, 10, 0),
        arrival_date_time=datetime(2025, 11, 15, 14, 0),
        airplane_type="Airbus A320"
    )

    flight2 = FlightDetails.objects.create(
        flight_id="PK302",
        source_airport=airport_dxb,
        destination_airport=airport_khi,
        departure_date_time=datetime(2025, 11, 16, 18, 0),
        arrival_date_time=datetime(2025, 11, 16, 22, 0),
        airplane_type="Boeing 737"
    )

    print("Inserting seats...")
    seat1A = SeatDetails.objects.create(seat_id="1A", travel_class=bus, flight=flight1)
    seat22C = SeatDetails.objects.create(seat_id="22C", travel_class=eco, flight=flight1)

    seat1B = SeatDetails.objects.create(seat_id="1B", travel_class=bus, flight=flight2)
    seat14D = SeatDetails.objects.create(seat_id="14D", travel_class=eco, flight=flight2)

    print("Inserting passengers...")
    passenger1 = Passenger.objects.create(
        passenger_id="P001",
        first_name="Hamza",
        last_name="Kashif",
        email="hamzahisam@gmail.com",
        phone_number="03341371292",
        address="Some Street",
        city="Karachi",
        state="Sindh",
        zipcode="75300",
        country="Pakistan"
    )

    passenger2 = Passenger.objects.create(
        passenger_id="P002",
        first_name="Ali",
        last_name="Ahmed",
        email="ali@example.com",
        phone_number="03001234567",
        address="Another Street",
        city="Karachi",
        state="Sindh",
        zipcode="75500",
        country="Pakistan"
    )

    print("Inserting reservations...")
    reservation1 = Reservation.objects.create(
        reservation_id="R001",
        passenger=passenger1,
        seat=seat1A,
        date_of_reservation=date.today()
    )

    reservation2 = Reservation.objects.create(
        reservation_id="R002",
        passenger=passenger2,
        seat=seat22C,
        date_of_reservation=date.today()
    )

    print("Inserting payments...")
    PaymentStatus.objects.create(
        payment_id="PAY001",
        payment_status_yn="Y",
        payment_due_date=date.today(),
        payment_amount=65000,
        reservation=reservation1
    )

    PaymentStatus.objects.create(
        payment_id="PAY002",
        payment_status_yn="N",
        payment_due_date=date.today() + timedelta(days=7),
        payment_amount=40000,
        reservation=reservation2
    )

    print("Inserting flight services...")
    service_meal = FlightService.objects.create(service_id="MEAL", service_name="Meals Included")
    service_wifi = FlightService.objects.create(service_id="WIFI", service_name="WiFi")
    service_tv = FlightService.objects.create(service_id="TV", service_name="In-Flight Entertainment")

    print("Service offerings...")
    ServiceOffering.objects.create(
        travel_class=bus,
        service=service_meal,
        offered_yn="Y",
        from_date=date.today(),
        to_date=date.today() + timedelta(days=90)
    )

    ServiceOffering.objects.create(
        travel_class=eco,
        service=service_wifi,
        offered_yn="N",
        from_date=date.today(),
        to_date=date.today() + timedelta(days=90)
    )

    print("Inserting flight costs...")
    FlightCost.objects.create(
        seat=seat1A,
        valid_from_date=date.today(),
        valid_to_date=date.today() + timedelta(days=30),
        cost=65000
    )

    FlightCost.objects.create(
        seat=seat22C,
        valid_from_date=date.today(),
        valid_to_date=date.today() + timedelta(days=30),
        cost=40000
    )

    print("\nALL DATA INSERTED SUCCESSFULLY ✔")