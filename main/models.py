from django.db import models

# 1. Airport
class Airport(models.Model):
    airport_id = models.CharField(max_length=20, primary_key=True)
    airport_city = models.CharField(max_length=50)
    airport_country = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.airport_city} ({self.airport_id})"


# 2. Flight_Details
class FlightDetails(models.Model):
    flight_id = models.CharField(max_length=20, primary_key=True)
    source_airport = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='flights_from')
    destination_airport = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='flights_to')
    departure_date_time = models.DateTimeField()
    arrival_date_time = models.DateTimeField()
    airplane_type = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.flight_id}: {self.source_airport} -> {self.destination_airport}"


# 3. Passenger
class Passenger(models.Model):
    passenger_id = models.CharField(max_length=20, primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=200)
    phone_number = models.CharField(max_length=20)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    zipcode = models.CharField(max_length=20)
    country = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# 4. Travel_Class
class TravelClass(models.Model):
    travel_class_id = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=50)
    capacity = models.IntegerField()

    def __str__(self):
        return self.name


# 5. Seat_Details
class SeatDetails(models.Model):
    seat_id = models.CharField(max_length=20, primary_key=True)
    travel_class = models.ForeignKey(TravelClass, on_delete=models.CASCADE, related_name='seats')
    flight = models.ForeignKey(FlightDetails, on_delete=models.CASCADE, related_name='seats')

    def __str__(self):
        return f"{self.seat_id} ({self.flight})"


# 6. Reservation
class Reservation(models.Model):
    reservation_id = models.CharField(max_length=20, primary_key=True)
    passenger = models.ForeignKey(Passenger, on_delete=models.CASCADE, related_name='reservations')
    seat = models.ForeignKey(SeatDetails, on_delete=models.CASCADE, related_name='reservations')
    date_of_reservation = models.DateField()

    def __str__(self):
        return f"Reservation {self.reservation_id} for {self.passenger}"


# 7. Payment_Status
class PaymentStatus(models.Model):
    payment_id = models.CharField(max_length=20, primary_key=True)
    payment_status_yn = models.CharField(max_length=1, choices=[('Y','Yes'),('N','No')])
    payment_due_date = models.DateField()
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='payment')

    def __str__(self):
        return f"Payment {self.payment_id}: {self.payment_status_yn}"


# 8. Flight_Service
class FlightService(models.Model):
    service_id = models.CharField(max_length=20, primary_key=True)
    service_name = models.CharField(max_length=50)

    def __str__(self):
        return self.service_name


# 9. Service_Offering
class ServiceOffering(models.Model):
    travel_class = models.ForeignKey(TravelClass, on_delete=models.CASCADE, related_name='service_offerings')
    service = models.ForeignKey(FlightService, on_delete=models.CASCADE, related_name='service_offerings')
    offered_yn = models.CharField(max_length=1, choices=[('Y','Yes'),('N','No')])
    from_date = models.DateField()
    to_date = models.DateField()

    class Meta:
        unique_together = ('travel_class', 'service')

    def __str__(self):
        return f"{self.travel_class} - {self.service}"


# 10. Flight_Cost
class FlightCost(models.Model):
    seat = models.ForeignKey(SeatDetails, on_delete=models.CASCADE, related_name='flight_costs')
    valid_from_date = models.DateField()
    valid_to_date = models.DateField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('seat', 'valid_from_date')

    def __str__(self):
        return f"Cost {self.cost} for {self.seat}"
