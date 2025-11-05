from django.shortcuts import render

def home(request):
    return render(request, 'index.html')

def contact(request):
    return render(request, 'contact.html')

def destination(request):
    return render(request, 'destination.html')

def pricing(request):
    return render(request, 'pricing.html')
