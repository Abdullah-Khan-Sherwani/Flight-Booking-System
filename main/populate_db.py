from datetime import datetime, timedelta
from main.models import (
    Airport, FlightDetails, TravelClass, SeatDetails, Passenger,
    Reservation, PaymentStatus, FlightService, ServiceOffering, FlightCost
)
from django.db import transaction
from django.utils import timezone

import warnings

warnings.filterwarnings("ignore")

# Wrap everything in a transaction to avoid partial inserts if error occurs
with transaction.atomic():
    
    # -----------------------------
    # 1. Airports
    # -----------------------------
    airports = [
        ('KHI', 'Karachi', 'Pakistan'),
        ('LHE', 'Lahore', 'Pakistan'),
        ('ISB', 'Islamabad', 'Pakistan'),
        ('PEW', 'Peshawar', 'Pakistan'),
        ('UET', 'Quetta', 'Pakistan'),  # Fixed from QUA to UET
        ('MUX', 'Multan', 'Pakistan')
    ]
    
    for code, city, country in airports:
        Airport.objects.update_or_create(
            airport_id=code,
            defaults={'airport_city': city, 'airport_country': country}
        )
    
    # -----------------------------
    # 2. Travel Classes
    # -----------------------------
    travel_classes = [
        ('ECO', 'Economy', 150),  # Fixed from ECON to ECO
        ('BUS', 'Business', 50),
        ('FIR', 'First', 20)      # Fixed from FST to FIR
    ]
    
    for tc_id, name, cap in travel_classes:
        TravelClass.objects.update_or_create(
            travel_class_id=tc_id,
            defaults={'name': name, 'capacity': cap}
        )
    
    # -----------------------------
    # 3. Flight Services
    # -----------------------------
    services = [
        ('MEAL', 'Meal'),
        ('WIFI', 'Wi-Fi'),
        ('ENT', 'In-flight Entertainment'),
        ('EXL', 'Extra Legroom'),
        ('PRI', 'Priority Boarding')
    ]
    
    for s_id, name in services:
        FlightService.objects.update_or_create(service_id=s_id, defaults={'service_name': name})
    
    # -----------------------------
    # 4. Create Flights Between All Cities
    # -----------------------------
    flight_counter = 101
    flights_created = []
    
    # Define flight durations between cities (in hours)
    flight_durations = {
        ('KHI', 'LHE'): 2.0,
        ('KHI', 'ISB'): 2.5,
        ('KHI', 'PEW'): 3.0,
        ('KHI', 'UET'): 2.0,
        ('KHI', 'MUX'): 1.5,
        ('LHE', 'ISB'): 1.0,
        ('LHE', 'PEW'): 1.5,
        ('LHE', 'UET'): 2.0,
        ('LHE', 'MUX'): 1.0,
        ('ISB', 'PEW'): 1.0,
        ('ISB', 'UET'): 2.5,
        ('ISB', 'MUX'): 1.5,
        ('PEW', 'UET'): 2.0,
        ('PEW', 'MUX'): 2.0,
        ('UET', 'MUX'): 1.5,
    }
    
    # Create flights for November 10, 2025
    base_date = datetime(2025, 11, 10)
    
    # Generate flights in both directions
    for (source, dest), duration in flight_durations.items():
        # Forward flight (source -> destination)
        flight_id_forward = f'IAT{flight_counter}'
        departure_time = base_date.replace(hour=8, minute=0) + timedelta(hours=(flight_counter-101)*0.5)
        arrival_time = departure_time + timedelta(hours=duration)
        
        flight_forward = FlightDetails.objects.update_or_create(
            flight_id=flight_id_forward,
            defaults={
                'source_airport': Airport.objects.get(airport_id=source),
                'destination_airport': Airport.objects.get(airport_id=dest),
                'departure_date_time': departure_time,
                'arrival_date_time': arrival_time,
                'airplane_type': 'Airbus A320'
            }
        )[0]
        flights_created.append(flight_forward)
        flight_counter += 1
        
        # Return flight (destination -> source)
        flight_id_return = f'IAT{flight_counter}'
        departure_time_return = base_date.replace(hour=14, minute=0) + timedelta(hours=(flight_counter-101)*0.5)
        arrival_time_return = departure_time_return + timedelta(hours=duration)
        
        flight_return = FlightDetails.objects.update_or_create(
            flight_id=flight_id_return,
            defaults={
                'source_airport': Airport.objects.get(airport_id=dest),
                'destination_airport': Airport.objects.get(airport_id=source),
                'departure_date_time': departure_time_return,
                'arrival_date_time': arrival_time_return,
                'airplane_type': 'Boeing 737'
            }
        )[0]
        flights_created.append(flight_return)
        flight_counter += 1
    
    # Create additional flights for November 11, 2025
    base_date_nov11 = datetime(2025, 11, 11)
    
    # Add morning flights for popular routes
    popular_routes = [('KHI', 'ISB'), ('LHE', 'ISB'), ('KHI', 'LHE'), ('ISB', 'PEW')]
    
    for source, dest in popular_routes:
        duration = flight_durations.get((source, dest), 2.0)
        
        # Morning flight on Nov 11
        flight_id_morning = f'IAT{flight_counter}'
        departure_time_morning = base_date_nov11.replace(hour=7, minute=30)
        arrival_time_morning = departure_time_morning + timedelta(hours=duration)
        
        flight_morning = FlightDetails.objects.update_or_create(
            flight_id=flight_id_morning,
            defaults={
                'source_airport': Airport.objects.get(airport_id=source),
                'destination_airport': Airport.objects.get(airport_id=dest),
                'departure_date_time': departure_time_morning,
                'arrival_date_time': arrival_time_morning,
                'airplane_type': 'Airbus A321'
            }
        )[0]
        flights_created.append(flight_morning)
        flight_counter += 1
        
        # Evening flight on Nov 11
        flight_id_evening = f'IAT{flight_counter}'
        departure_time_evening = base_date_nov11.replace(hour=18, minute=0)
        arrival_time_evening = departure_time_evening + timedelta(hours=duration)
        
        flight_evening = FlightDetails.objects.update_or_create(
            flight_id=flight_id_evening,
            defaults={
                'source_airport': Airport.objects.get(airport_id=source),
                'destination_airport': Airport.objects.get(airport_id=dest),
                'departure_date_time': departure_time_evening,
                'arrival_date_time': arrival_time_evening,
                'airplane_type': 'Boeing 737'
            }
        )[0]
        flights_created.append(flight_evening)
        flight_counter += 1
    
    # -----------------------------
    # 5. Seats for All Flights
    # -----------------------------
    for flight in FlightDetails.objects.all():
        for tc in TravelClass.objects.all():
            # Create seats for each travel class
            seats_per_row = 6  # Assuming 6 seats per row
            rows = tc.capacity // seats_per_row
            
            for row in range(1, rows + 1):
                for seat_num in range(1, seats_per_row + 1):
                    seat_letter = chr(64 + seat_num)  # A, B, C, D, E, F
                    seat_id = f"{flight.flight_id}-{row}{seat_letter}"
                    
                    SeatDetails.objects.update_or_create(
                        seat_id=seat_id,
                        defaults={
                            'travel_class': tc,
                            'flight': flight
                        }
                    )
    
    # -----------------------------
    # 6. Service Offerings
    # -----------------------------
    service_offerings = {
        'ECO': ['MEAL'],  # Economy gets meal only
        'BUS': ['MEAL', 'WIFI', 'PRI'],  # Business gets meal, wifi, priority
        'FIR': ['MEAL', 'WIFI', 'ENT', 'EXL', 'PRI']  # First gets all services
    }
    
    for tc in TravelClass.objects.all():
        offered_services = service_offerings.get(tc.travel_class_id, [])
        for svc_id in offered_services:
            svc = FlightService.objects.get(service_id=svc_id)
            ServiceOffering.objects.update_or_create(
                travel_class=tc,
                service=svc,
                defaults={
                    'offered_yn': 'Y',
                    'from_date': datetime(2025, 11, 1).date(),
                    'to_date': datetime(2025, 12, 31).date()
                }
            )
    
    # -----------------------------
    # 7. Sample Passengers
    # -----------------------------
    passengers = [
        ('P001', 'Ali', 'Khan', 'ali.khan@example.com', '03001234567', 'House 10', 'Karachi', 'Sindh', '74400', 'Pakistan'),
        ('P002', 'Ayesha', 'Ahmed', 'ayesha.ahmed@example.com', '03007654321', 'House 5', 'Lahore', 'Punjab', '54000', 'Pakistan'),
        ('P003', 'Usman', 'Malik', 'usman.malik@example.com', '03009876543', 'Sector F-8', 'Islamabad', 'Federal', '44000', 'Pakistan'),
        ('P004', 'Fatima', 'Raza', 'fatima.raza@example.com', '03005556677', 'University Road', 'Peshawar', 'KPK', '25000', 'Pakistan'),
        ('P005', 'Bilal', 'Shah', 'bilal.shah@example.com', '03003334455', 'Jinnah Road', 'Quetta', 'Balochistan', '87300', 'Pakistan'),
        ('P006', 'Sara', 'Iqbal', 'sara.iqbal@example.com', '03002223344', 'Bosan Road', 'Multan', 'Punjab', '60000', 'Pakistan'),
    ]
    
    for pid, fname, lname, email, phone, addr, city, state, zipc, country in passengers:
        Passenger.objects.update_or_create(
            passenger_id=pid,
            defaults={
                'first_name': fname,
                'last_name': lname,
                'email': email,
                'phone_number': phone,
                'address': addr,
                'city': city,
                'state': state,
                'zipcode': zipc,
                'country': country
            }
        )
    
    # -----------------------------
    # 8. Sample Reservations and Payments
    # -----------------------------
    # Create sample bookings for different flights
    sample_bookings = [
        ('R001', 'P001', 'IAT101-1A', 150.00),  # Ali Khan on KHI->LHE
        ('R002', 'P002', 'IAT102-2A', 150.00),  # Ayesha Ahmed on LHE->KHI
        ('R003', 'P003', 'IAT103-1B', 200.00),  # Usman Malik on KHI->ISB
        ('R004', 'P004', 'IAT104-3C', 180.00),  # Fatima Raza on ISB->KHI
    ]
    
    for res_id, pass_id, seat_id, amount in sample_bookings:
        try:
            passenger = Passenger.objects.get(passenger_id=pass_id)
            seat = SeatDetails.objects.get(seat_id=seat_id)
            
            reservation = Reservation.objects.update_or_create(
                reservation_id=res_id,
                defaults={
                    'passenger': passenger,
                    'seat': seat,
                    'date_of_reservation': datetime.now().date()
                }
            )[0]
            
            PaymentStatus.objects.update_or_create(
                payment_id=f'PAY{res_id[1:]}',  # PAY001, PAY002, etc.
                defaults={
                    'payment_status_yn': 'Y',
                    'payment_due_date': datetime.now().date() + timedelta(days=2),
                    'payment_amount': amount,
                    'reservation': reservation
                }
            )
        except Exception as e:
            print(f"Could not create reservation {res_id}: {e}")
    
    # -----------------------------
    # 9. Flight Costs for All Seats
    # -----------------------------
    base_prices = {
        'ECO': 100.00,   # Economy base price
        'BUS': 300.00,   # Business base price
        'FIR': 500.00    # First class base price
    }
    
    # Add some price variation based on route popularity
    route_multipliers = {
        ('KHI', 'ISB'): 1.2,  # Popular route - 20% more expensive
        ('KHI', 'LHE'): 1.1,  # Slightly popular - 10% more
        ('LHE', 'ISB'): 1.0,  # Standard price
    }
    
    for seat in SeatDetails.objects.all():
        base_price = base_prices.get(seat.travel_class.travel_class_id, 100.00)
        
        # Check if this route has a multiplier
        route_key = (seat.flight.source_airport.airport_id, seat.flight.destination_airport.airport_id)
        multiplier = route_multipliers.get(route_key, 1.0)
        
        final_price = base_price * multiplier
        
        FlightCost.objects.update_or_create(
            seat=seat,
            valid_from_date=datetime(2025, 11, 1).date(),
            defaults={
                'valid_to_date': datetime(2025, 12, 31).date(),
                'cost': final_price
            }
        )

print("Complete database populated successfully for IAT Airlines!")
print(f"Created flights between all cities for November 10-11, 2025")
print(f"Total flights created: {FlightDetails.objects.count()}")
print(f"Total seats created: {SeatDetails.objects.count()}")
print(f"Sample routes available:")
print("- Karachi to Islamabad (multiple flights)")
print("- Lahore to Islamabad") 
print("- Karachi to Lahore")
print("- And all other city combinations!")