from django.shortcuts import render, redirect
from django.db.models import Q
from .models import Airport, FlightDetails
from datetime import datetime

def home(request):
    return render(request, 'index.html')

def contact(request):
    return render(request, 'contact.html')

def destination(request):
    return render(request, 'destination.html')

def pricing(request):
    return render(request, 'pricing.html')

def search_flights(request):
    if request.method == 'POST':
        departure_city = request.POST.get('departure_city')
        arrival_city = request.POST.get('arrival_city')
        departure_date = request.POST.get('departure_date')
        travel_class = request.POST.get('travel_class')
        passengers = request.POST.get('passengers')
        
        print(f"Searching flights: {departure_city} to {arrival_city} on {departure_date}")
        
        # Convert date string to datetime for filtering
        try:
            departure_datetime = datetime.strptime(departure_date, '%Y-%m-%d')
            
            # Search for flights
            flights = FlightDetails.objects.filter(
                source_airport_id=departure_city,
                destination_airport_id=arrival_city,
                departure_date_time__date=departure_datetime.date()
            ).select_related('source_airport', 'destination_airport')
            
            context = {
                'flights': flights,
                'search_criteria': {
                    'departure_city': Airport.objects.get(airport_id=departure_city),
                    'arrival_city': Airport.objects.get(airport_id=arrival_city),
                    'date': departure_date,
                    'travel_class': travel_class,
                    'passengers': passengers
                }
            }
            return render(request, 'search_results.html', context)
            
        except Exception as e:
            print(f"Error: {e}")
            # Handle any errors
            airports = Airport.objects.all()
            return render(request, 'search_results.html', {
                'flights': [],
                'error': 'No flights found or invalid search criteria'
            })
    
    # If GET request, redirect to home
    return redirect('index')