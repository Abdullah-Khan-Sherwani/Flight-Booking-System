from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='index'),
    path('contact/', views.contact, name='contact'),
    path('destination/', views.destination, name='destination'),
    path('pricing/', views.pricing, name='pricing'),
    path('search-flights/', views.search_flights, name='search_flights'),
]