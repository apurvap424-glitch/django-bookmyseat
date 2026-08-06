from django.urls import path
from . import views

urlpatterns = [
    path('', views.movie_list, name='movie_list'),
    path('<int:movie_id>/theaters/', views.theater, name='theater'),
    path('theater/<int:theater_id>/seats/book/', views.book_Seats, name='book_seats'),

    
    path('booking-success/', views.booking_success, name='booking_success'),
]