from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from.models import Movie, Theater, Seat, Booking
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError

def movie_list(request):
    search_query = request.GET.get('search')

    if search_query:
        movies = Movie.objects.filter(name__icontains=search_query)
    else:
        movies = Movie.objects.all()

    return render(request, 'movies/movie_list.html', {'movies': movies})

def theater(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    theaters = Theater.objects.filter(movie=movie)

    return render(request, 'movies/theater_list.html', {
        'movie': movie,
        'theaters': theaters
    })



@login_required(login_url='/login/')
def book_Seats(request, theater_id):
    theater = get_object_or_404(Theater, id=theater_id)
    seats = Seat.objects.filter(theater=theater)
    if request.method == 'POST':
        selected_seats = request.POST.getlist('seats')
        if not selected_seats:
            return render(request, 'movies/seat_selection.html', {
                'theater': theater,
                'seats': seats,
                'error_message': 'Please select at least one seat.'
            })

        try:
            for seat_id in selected_seats:
                 seat = Seat.objects.get(id=seat_id)
                 seat.is_booked = True
                 seat.save()
                 Booking.objects.create(
                     user=request.user,
                     seat=seat,
                     movie=theater.movie,
                     theater=theater
                     )
            return HttpResponse("BOOKING SUCCESS")
        except IntegrityError:
            return render(request, 'movies/seat_selection.html', {
                'theater': theater,
                'seats': seats,
                'error_message': 'One or more selected seats are already booked. Please choose different seats.'
            })
    return render(request, 'movies/seat_selection.html', {
        'theater': theater,
        'seats': seats
    })


def booking_success(request):
    return HttpResponse("Booking Successful!")