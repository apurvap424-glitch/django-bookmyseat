import os
import json
import csv
import razorpay

from datetime import timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User

from django.db import models, transaction
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncHour

from django.utils import timezone
from django.utils.dateparse import parse_date

from django.views.decorators.csrf import csrf_exempt

from .models import Movie, Theater, Seat, Booking, Review, Payment
from .tasks import generate_and_send_ticket

# =========================================================
# MOVIE LIST
# =========================================================

def movie_list(request):

    movies = Movie.objects.all()

    # GET FILTER VALUES

    search = request.GET.get('search')
    genre = request.GET.get('genre')
    language = request.GET.get('language')
    city = request.GET.get('city')
    theater_name = request.GET.get('theater')
    rating = request.GET.get('rating')
    release_date = request.GET.get('release_date')
    time_filter = request.GET.get('time')
    sort = request.GET.get('sort')


    # SEARCH

    if search:
        movies = movies.filter(
            name__icontains=search
        )


    # FILTERS

    if genre:
        movies = movies.filter(
            genre=genre
        )

    if language:
        movies = movies.filter(
            language=language
        )

    if city:
        movies = movies.filter(
            theaters__city__iexact=city
        ).distinct()

    if theater_name:
        movies = movies.filter(
            theaters__name__iexact=theater_name
        ).distinct()

    if rating:
        movies = movies.filter(
            rating__gte=float(rating)
    )

    if release_date:
        movies = movies.filter(
            release_date=release_date
        )


    # SHOW TIME FILTER

    if time_filter == "morning":

        movies = movies.filter(
            theaters__time__hour__gte=6,
            theaters__time__hour__lt=12
        ).distinct()

    elif time_filter == "afternoon":

        movies = movies.filter(
            theaters__time__hour__gte=12,
            theaters__time__hour__lt=17
        ).distinct()

    elif time_filter == "evening":

        movies = movies.filter(
            theaters__time__hour__gte=17,
            theaters__time__hour__lt=21
        ).distinct()

    elif time_filter == "night":

        movies = movies.filter(
            theaters__time__hour__gte=21,
            theaters__time__hour__lt=24
        ).distinct()


    # SORTING

    if sort == "rating":

        movies = movies.order_by(
            "-rating"
        )

    elif sort == "newest":

        movies = movies.order_by(
            "-release_date"
        )

    elif sort == "price":

        movies = movies.order_by(
            "ticket_price"
        )

    elif sort == "popular":

        movies = movies.order_by(
            "-popularity"
        )


    # RECENTLY VIEWED MOVIES

    recently_viewed = request.session.get(
        "recently_viewed",
        []
    )

    recently_viewed_movies = Movie.objects.filter(
        id__in=recently_viewed
    )


    # RECOMMENDED MOVIES

    recommended_movies = Movie.objects.none()

    if request.user.is_authenticated:

        # Movies booked by the user

        booked_movies = Movie.objects.filter(
            bookings__user=request.user
        ).distinct()


        # Get genres from booked movies

        booked_genres = booked_movies.values_list(
            "genre",
            flat=True
        )


        # Get genres from recently viewed movies

        viewed_genres = recently_viewed_movies.values_list(
            "genre",
            flat=True
        )


        # Combine booked and recently viewed genres

        preferred_genres = list(booked_genres) + list(
            viewed_genres
        )


        # Recommended movies based on preferences

        if preferred_genres:

            recommended_movies = Movie.objects.filter(
                genre__in=preferred_genres
            ).exclude(
                id__in=booked_movies.values_list(
                    "id",
                    flat=True
                )
            ).exclude(
                id__in=recently_viewed_movies.values_list(
                    "id",
                    flat=True
                )
            ).distinct().order_by(
                "-rating"
            )[:6]


    # REMOVE MOVIES ALREADY SHOWN ABOVE
    # This avoids repetition in the main movie list

    

    # MOVIE COUNT AFTER FILTERING

    movie_count = movies.count()


    # PAGINATION

    paginator = Paginator(
        movies,
        6
    )

    page_number = request.GET.get(
        "page"
    )

    movies = paginator.get_page(
        page_number
    )

    print("Selected city:", city)

    for theater in Theater.objects.all():
      print(
          "THEATER:", theater.name,
          "| CITY:", repr(theater.city),
          "| MOVIE:", theater.movie.name
      )

    return render(
        request,
        "movies/movie_list.html",
        {
            "movies": movies,
            "movie_count": movie_count,
            "recommended_movies": recommended_movies,
            "recently_viewed_movies": recently_viewed_movies
        }
    )


# =========================================================
# THEATER AND MOVIE DETAILS
# =========================================================

def theater(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    theaters = Theater.objects.filter(
        movie=movie
    )

    # Recently viewed
    recently_viewed = request.session.get(
        'recently_viewed',
        []
    )

    if movie.id in recently_viewed:
        recently_viewed.remove(movie.id)

    recently_viewed.insert(0, movie.id)

    recently_viewed = recently_viewed[:5]

    request.session['recently_viewed'] = recently_viewed

    # Reviews
    reviews = Review.objects.filter(
        movie=movie,
        is_reported=False
    ).select_related(
        'user'
    ).order_by(
        '-created_at'
    )

    for review in reviews:

        review.is_verified = Booking.objects.filter(
            user=review.user,
            movie=movie
        ).exists()

    average_rating = reviews.aggregate(
        average=models.Avg('rating')
    )['average']

    user_review = None

    if request.user.is_authenticated:

        user_review = Review.objects.filter(
            movie=movie,
            user=request.user
        ).first()

    # Similar movies
    similar_movies = Movie.objects.filter(
        genre=movie.genre
    ).exclude(
        id=movie.id
    ).order_by(
        '-rating'
    )[:6]

    if similar_movies.count() < 6:

        extra_similar = Movie.objects.filter(
            language=movie.language
        ).exclude(
            id=movie.id
        ).exclude(
            id__in=similar_movies.values_list(
                'id',
                flat=True
            )
        ).order_by(
            '-rating'
        )[:6 - similar_movies.count()]

        similar_movies = (
            list(similar_movies)
            + list(extra_similar)
        )

    trending_movies = Movie.objects.exclude(
        id=movie.id
    ).order_by(
        '-popularity',
        '-rating'
    )[:6]

    recently_released = Movie.objects.exclude(
        id=movie.id
    ).filter(
        release_date__isnull=False
    ).order_by(
        '-release_date'
    )[:6]

    return render(
        request,
        'movies/theater_list.html',
        {
            'movie': movie,
            'theaters': theaters,
            'reviews': reviews,
            'average_rating': average_rating,
            'user_review': user_review,
            'similar_movies': similar_movies,
            'trending_movies': trending_movies,
            'recently_released': recently_released,
        }
    )


# =========================================================
# RELEASE EXPIRED SEATS
# =========================================================

def release_expired_seats():

    Seat.objects.filter(
        status='reserved',
        reserved_until__lte=timezone.now()
    ).update(
        status='available',
        reserved_by=None,
        reserved_until=None
    )


# =========================================================
# SEAT SELECTION AND 2-MINUTE RESERVATION
# =========================================================

@login_required(login_url='/login/')
def book_Seats(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    # Release expired reservations
    release_expired_seats()

    seats = Seat.objects.filter(
        theater=theater
    ).order_by('id')

    if request.method == 'POST':

        selected_seats = request.POST.getlist(
            'seats'
        )

        if not selected_seats:

            return render(
                request,
                'movies/seat_selection.html',
                {
                    'theater': theater,
                    'seats': seats,
                    'error_message':
                        'Please select at least one seat.'
                }
            )

        try:

            with transaction.atomic():

                selected_seat_objects = []

                # Lock every selected seat
                for seat_id in selected_seats:

                    seat = Seat.objects.select_for_update().get(
                        id=seat_id,
                        theater=theater
                    )

                    # Release expired reservation
                    if (
                        seat.status == 'reserved'
                        and seat.reserved_until
                        and seat.reserved_until <= timezone.now()
                    ):

                        seat.status = 'available'
                        seat.reserved_by = None
                        seat.reserved_until = None
                        seat.save()

                    # Already booked
                    if seat.status == 'booked':

                        raise ValueError(
                            f'Seat {seat.seat_number} is already booked.'
                        )

                    # Reserved by another user
                    if (
                        seat.status == 'reserved'
                        and seat.reserved_by_id != request.user.id
                    ):

                        raise ValueError(
                            f'Seat {seat.seat_number} is temporarily reserved by another user.'
                        )

                    selected_seat_objects.append(seat)

                # Reserve for 2 minutes
                reservation_until = (
                    timezone.now()
                    + timedelta(minutes=2)
                )

                for seat in selected_seat_objects:

                    seat.status = 'reserved'

                    seat.reserved_by = request.user

                    seat.reserved_until = reservation_until

                    seat.save(
                        update_fields=[
                            'status',
                            'reserved_by',
                            'reserved_until'
                        ]
                    )

                # Total amount
                total_amount = (
                    theater.movie.ticket_price
                    * len(selected_seat_objects)
                )

                # Razorpay client
                client = razorpay.Client(
                    auth=(
                        settings.RAZORPAY_KEY_ID,
                        settings.RAZORPAY_KEY_SECRET
                    )
                )

                # Create Razorpay order
                razorpay_order = client.order.create({
                    'amount': int(total_amount * 100),
                    'currency': 'INR',
                    'payment_capture': 1
                })

                # Create Payment record BEFORE payment
                payment = Payment.objects.create(
                    booking=None,
                    user=request.user,
                    amount=total_amount,
                    razorpay_order_id=razorpay_order['id'],
                    status='created'
                )

                # Store data in session
                request.session['selected_seats'] = [
                    seat.id
                    for seat in selected_seat_objects
                ]

                request.session['theater_id'] = theater.id

                request.session['payment_id'] = payment.id

                request.session['reservation_until'] = (
                    reservation_until.isoformat()
                )

            return render(
                request,
                'movies/payment.html',
                {
                    'theater': theater,
                    'seats': selected_seat_objects,
                    'total_amount': total_amount,
                    'razorpay_order_id':
                        razorpay_order['id'],
                    'razorpay_key_id':
                        settings.RAZORPAY_KEY_ID,
                    'reservation_until':
                        reservation_until.isoformat()
                }
            )

        except ValueError as e:

            seats = Seat.objects.filter(
                theater=theater
            ).order_by('id')

            return render(
                request,
                'movies/seat_selection.html',
                {
                    'theater': theater,
                    'seats': seats,
                    'error_message': str(e)
                }
            )

        except Exception as e:

            return render(
                request,
                'movies/seat_selection.html',
                {
                    'theater': theater,
                    'seats': seats,
                    'error_message':
                        f'Unable to reserve seats: {str(e)}'
                }
            )

    return render(
        request,
        'movies/seat_selection.html',
        {
            'theater': theater,
            'seats': seats
        }
    )


# =========================================================
# PAYMENT SUCCESS
# =========================================================

@csrf_exempt
@login_required(login_url='/login/')
def payment_success(request):

    if request.method != 'POST':

        return HttpResponse(
            "Invalid request."
        )

    razorpay_payment_id = request.POST.get(
        'razorpay_payment_id'
    )

    razorpay_order_id = request.POST.get(
        'razorpay_order_id'
    )

    razorpay_signature = request.POST.get(
        'razorpay_signature'
    )

    if (
        not razorpay_payment_id
        or not razorpay_order_id
        or not razorpay_signature
    ):

        return HttpResponse(
            "Payment details missing."
        )

    try:

        with transaction.atomic():

            # Lock payment record
            payment = Payment.objects.select_for_update().get(
                razorpay_order_id=razorpay_order_id,
                user=request.user
            )

            # Prevent duplicate confirmation
            if payment.status == 'success':

                return HttpResponse(
                    "Payment already processed."
                )

            # Verify Razorpay signature
            client = razorpay.Client(
                auth=(
                    settings.RAZORPAY_KEY_ID,
                    settings.RAZORPAY_KEY_SECRET
                )
            )

            client.utility.verify_payment_signature({
                'razorpay_order_id':
                    razorpay_order_id,

                'razorpay_payment_id':
                    razorpay_payment_id,

                'razorpay_signature':
                    razorpay_signature
            })

            selected_seats = request.session.get(
                'selected_seats',
                []
            )

            theater_id = request.session.get(
                'theater_id'
            )

            if not selected_seats:

                raise Exception(
                    "Selected seats not found."
                )

            if not theater_id:

                raise Exception(
                    "Theater information missing."
                )

            theater = get_object_or_404(
                Theater,
                id=theater_id
            )

            created_booking = None

            # Lock and book seats
            for seat_id in selected_seats:

                seat = Seat.objects.select_for_update().get(
                    id=seat_id,
                    theater=theater
                )

                # Already booked
                if seat.status == 'booked':

                    raise Exception(
                        f'Seat {seat.seat_number} is already booked.'
                    )

                # Reservation belongs to another user
                if (
                    seat.status == 'reserved'
                    and seat.reserved_by_id != request.user.id
                ):

                    raise Exception(
                        f'Seat {seat.seat_number} is reserved by another user.'
                    )

                # Reservation expired
                if (
                    seat.reserved_until
                    and seat.reserved_until < timezone.now()
                ):

                    raise Exception(
                        f'Reservation for seat {seat.seat_number} has expired.'
                    )

                # Confirm booking
                seat.status = 'booked'

                seat.reserved_by = None

                seat.reserved_until = None

                seat.save(
                    update_fields=[
                        'status',
                        'reserved_by',
                        'reserved_until'
                    ]
                )

                booking = Booking.objects.create(
                    user=request.user,
                    seat=seat,
                    movie=theater.movie,
                    theater=theater
                )

                if created_booking is None:
                    created_booking = booking

                booking_id = booking.id
                transaction.on_commit(
                     lambda booking_id=booking_id:
                     generate_and_send_ticket.delay(booking_id)
                )

            # Update payment
            payment.booking = created_booking

            payment.razorpay_payment_id = (
                razorpay_payment_id
            )

            payment.razorpay_signature = (
                razorpay_signature
            )

            payment.status = 'success'

            payment.save()

        # Clear session
        request.session.pop(
            'selected_seats',
            None
        )

        request.session.pop(
            'theater_id',
            None
        )

        request.session.pop(
            'payment_id',
            None
        )

        request.session.pop(
            'reservation_until',
            None
        )

        return redirect(
            'booking_success'
        )

    except Payment.DoesNotExist:

        return HttpResponse(
            "Payment order not found."
        )

    except razorpay.errors.SignatureVerificationError:

        return HttpResponse(
            "Payment verification failed."
        )

    except Exception as e:

        return HttpResponse(
            f"Payment error: {str(e)}"
        )


# =========================================================
# PAYMENT FAILED / CANCELLED
# =========================================================

@csrf_exempt
@login_required(login_url='/login/')
def payment_failed(request):

    if request.method != 'POST':

        return HttpResponse(
            "Invalid request."
        )

    razorpay_order_id = request.POST.get(
        'razorpay_order_id'
    )

    razorpay_payment_id = request.POST.get(
        'razorpay_payment_id'
    )

    if not razorpay_order_id:

        return HttpResponse(
            "Order ID missing."
        )

    try:

        with transaction.atomic():

            payment = Payment.objects.select_for_update().filter(
                razorpay_order_id=razorpay_order_id,
                user=request.user
            ).first()

            if not payment:

                return HttpResponse(
                    "Payment transaction not found."
                )

            # Never change successful payment
            if payment.status == 'success':

                return HttpResponse(
                    "Payment already successful."
                )

            payment.status = 'failed'

            if razorpay_payment_id:

                payment.razorpay_payment_id = (
                    razorpay_payment_id
                )

            payment.save()

            # Release reserved seats
            selected_seats = request.session.get(
                'selected_seats',
                []
            )

            if selected_seats:

                Seat.objects.select_for_update().filter(
                    id__in=selected_seats,
                    reserved_by=request.user,
                    status='reserved'
                ).update(
                    status='available',
                    reserved_by=None,
                    reserved_until=None
                )

        # Clear session
        request.session.pop(
            'selected_seats',
            None
        )

        request.session.pop(
            'theater_id',
            None
        )

        request.session.pop(
            'payment_id',
            None
        )

        request.session.pop(
            'reservation_until',
            None
        )

        request.session.modified = True

        return HttpResponse(
            "PAYMENT FAILED - SEATS RELEASED"
        )

    except Exception as e:

        return HttpResponse(
            f"Payment error: {str(e)}"
        )


@csrf_exempt
@login_required(login_url='/login/')
def payment_cancelled(request):

    if request.method != 'POST':
        return HttpResponse("Invalid request.")

    razorpay_order_id = request.POST.get(
        'razorpay_order_id'
    )

    if not razorpay_order_id:
        return HttpResponse(
            "Order ID missing."
        )

    try:

        payment = Payment.objects.filter(
            razorpay_order_id=razorpay_order_id,
            user=request.user
        ).first()

        if not payment:
            return HttpResponse(
                "Payment transaction not found."
            )

        # Never cancel a successful payment
        if payment.status == 'success':
            return HttpResponse(
                "Payment already successful."
            )

        # Mark payment as cancelled
        payment.status = 'cancelled'
        payment.save()

        # Release reserved seats
        selected_seats = request.session.get(
            'selected_seats',
            []
        )

        if selected_seats:

            with transaction.atomic():

                Seat.objects.select_for_update().filter(
                    id__in=selected_seats,
                    reserved_by=request.user,
                    status='reserved'
                ).update(
                    status='available',
                    reserved_by=None,
                    reserved_until=None
                )

        # Clear session
        request.session.pop('selected_seats', None)
        request.session.pop('theater_id', None)
        request.session.pop('payment_id', None)

        request.session.modified = True

        return HttpResponse(
            "PAYMENT CANCELLED - SEATS RELEASED"
        )

    except Exception as e:

        return HttpResponse(
            f"Payment cancellation error: {str(e)}"
        )


# =========================================================
# RAZORPAY WEBHOOK
# =========================================================

@csrf_exempt
def razorpay_webhook(request):

    if request.method != 'POST':

        return HttpResponse(
            "Invalid request.",
            status=405
        )

    webhook_signature = request.headers.get(
        'X-Razorpay-Signature'
    )

    if not webhook_signature:

        return HttpResponse(
            "Webhook signature missing.",
            status=400
        )

    try:

        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            )
        )

        # Verify webhook signature
        client.utility.verify_webhook_signature(
            request.body.decode('utf-8'),
            webhook_signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )

    except razorpay.errors.SignatureVerificationError:

        return HttpResponse(
            "Invalid webhook signature.",
            status=400
        )

    except Exception as e:

        return HttpResponse(
            f"Webhook verification error: {str(e)}",
            status=400
        )

    try:

        data = json.loads(
            request.body.decode('utf-8')
        )

        event = data.get('event')

        payment_entity = (
            data.get('payload', {})
            .get('payment', {})
            .get('entity', {})
        )

        razorpay_payment_id = payment_entity.get(
            'id'
        )

        razorpay_order_id = payment_entity.get(
            'order_id'
        )

        if not razorpay_order_id:

            return HttpResponse(
                "Order ID missing.",
                status=400
            )

        with transaction.atomic():

            payment = Payment.objects.select_for_update().filter(
                razorpay_order_id=razorpay_order_id
            ).first()

            if not payment:

                # Return 200 so Razorpay does not keep retrying
                return HttpResponse(
                    "Payment record not found.",
                    status=200
                )

            # Payment failed
            if event == 'payment.failed':

                # Do not overwrite success
                if payment.status != 'success':

                    payment.status = 'failed'

                    if razorpay_payment_id:

                        payment.razorpay_payment_id = (
                            razorpay_payment_id
                        )

                    payment.save()

            # Payment captured
            elif event == 'payment.captured':

                # Store transaction ID.
                # Booking confirmation is handled by
                # payment_success after signature verification.
                if razorpay_payment_id:

                    payment.razorpay_payment_id = (
                        razorpay_payment_id
                    )

                    payment.save(
                        update_fields=[
                            'razorpay_payment_id',
                            'updated_at'
                        ]
                    )

        return HttpResponse(
            "Webhook received.",
            status=200
        )

    except Exception as e:

        return HttpResponse(
            f"Webhook error: {str(e)}",
            status=400
        )


# =========================================================
# BOOKING SUCCESS
# =========================================================

@login_required(login_url='/login/')
def booking_success(request):

    return HttpResponse(
        "PAYMENT SUCCESSFUL - BOOKING CONFIRMED"
    )


# =========================================================
# BOOKING HISTORY
# =========================================================

@login_required(login_url='/login/')
def booking_history(request):

    bookings = Booking.objects.filter(
        user=request.user
    ).select_related(
        'movie',
        'theater',
        'seat'
    ).order_by(
        '-booked_at'
    )

    payments = Payment.objects.filter(
        user=request.user
    ).select_related(
        'booking'
    ).order_by(
        '-created_at'
    )

    return render(
        request,
        'movies/booking_history.html',
        {
            'bookings': bookings,
            'payments': payments
        }
    )


# =========================================================
# DOWNLOAD TICKET
# =========================================================

@login_required(login_url='/login/')
def download_ticket(request, booking_id):

    booking = get_object_or_404(
        Booking,
        booking_id=booking_id,
        user=request.user
    )

    ticket_path = os.path.join(
        settings.MEDIA_ROOT,
        'tickets',
        f'ticket_{booking.booking_id}.pdf'
    )

    if not os.path.exists(ticket_path):

        return HttpResponse(
            "Ticket PDF not found."
        )

    with open(
        ticket_path,
        'rb'
    ) as ticket_file:

        response = HttpResponse(
            ticket_file.read(),
            content_type='application/pdf'
        )

    response['Content-Disposition'] = (
        f'attachment; filename="ticket_{booking.booking_id}.pdf"'
    )

    return response


# =========================================================
# ADD / UPDATE REVIEW
# =========================================================

@login_required(login_url='/login/')
def add_review(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    has_booked = Booking.objects.filter(
        user=request.user,
        movie=movie
    ).exists()

    if not has_booked:

        return HttpResponse(
            "You can review this movie only after booking it."
        )

    existing_review = Review.objects.filter(
        user=request.user,
        movie=movie
    ).first()

    if request.method == 'POST':

        rating = request.POST.get(
            'rating'
        )

        comment = request.POST.get(
            'comment'
        )

        if not rating or not comment:

            return HttpResponse(
                "Please provide both rating and review."
            )

        if existing_review:

            existing_review.rating = rating
            existing_review.comment = comment
            existing_review.save()

        else:

            Review.objects.create(
                movie=movie,
                user=request.user,
                rating=rating,
                comment=comment
            )

        return redirect(
            'theater',
            movie_id=movie.id
        )

    return render(
        request,
        'movies/add_review.html',
        {
            'movie': movie,
            'existing_review': existing_review
        }
    )


# =========================================================
# REPORT REVIEW
# =========================================================

@login_required(login_url='/login/')
def report_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id
    )

    if request.method == 'POST':

        review.is_reported = True
        review.save()

    return redirect(
        'theater',
        movie_id=review.movie.id
    )

@staff_member_required(login_url='/admin/login/')
def admin_dashboard(request):

    # -----------------------------------
    # DATE FILTER
    # -----------------------------------

    today = timezone.localdate()

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = parse_date(start_date_str) if start_date_str else None
    end_date = parse_date(end_date_str) if end_date_str else None

    # -----------------------------------
    # SUCCESSFUL PAYMENTS
    # -----------------------------------

    successful_payments = Payment.objects.filter(
        status='success'
    )

    if start_date:
        successful_payments = successful_payments.filter(
            created_at__date__gte=start_date
        )

    if end_date:
        successful_payments = successful_payments.filter(
            created_at__date__lte=end_date
        )

    # -----------------------------------
    # TOTAL REVENUE
    # -----------------------------------

    total_revenue = (
        successful_payments.aggregate(
            total=Sum('amount')
        )['total'] or 0
    )

    daily_revenue = (
        Payment.objects.filter(
            status='success',
            created_at__date=today
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
    )

    week_start = today - timedelta(days=today.weekday())

    weekly_revenue = (
        Payment.objects.filter(
            status='success',
            created_at__date__gte=week_start
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
    )

    monthly_revenue = (
        Payment.objects.filter(
            status='success',
            created_at__year=today.year,
            created_at__month=today.month
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
    )

    yearly_revenue = (
        Payment.objects.filter(
            status='success',
            created_at__year=today.year
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
    )

    # -----------------------------------
    # BOOKINGS WITH DATE FILTER
    # -----------------------------------

    bookings = Booking.objects.all()

    if start_date:
        bookings = bookings.filter(
            booked_at__date__gte=start_date
        )

    if end_date:
        bookings = bookings.filter(
            booked_at__date__lte=end_date
        )

    total_bookings = bookings.count()

    # -----------------------------------
    # CSV EXPORT
    # -----------------------------------
    
    if request.GET.get('export') == 'csv':
        response = HttpResponse(
            content_type='text/csv'
        )

        response[
            'Content-Disposition'
        ] = 'attachment; filename="admin_dashboard_report.csv"'

        writer = csv.writer(response)

        writer.writerow([
            'Booking ID',
            'User',
            'Movie',
            'Theater',
            'Seat',
            'Booking Date'
       ])

        for booking in bookings.select_related(
            'user',
            'movie',
            'theater',
            'seat'
       ):

            writer.writerow([
                booking.booking_id,
                booking.user.username,
                booking.movie.name,
                booking.theater.name,
                booking.seat.seat_number,
                booking.booked_at.strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
           ])

        return response
    

    # -----------------------------------
    # BOOKING TRENDS
    # -----------------------------------

    booking_trends = (
        bookings.annotate(
            date=TruncDate('booked_at')
        )
        .values('date')
        .annotate(
            total=Count('id')
        )
        .order_by('date')
    )

    # -----------------------------------
    # MOST BOOKED MOVIES
    # -----------------------------------

    most_booked_movies = (
        bookings.values('movie__name')
        .annotate(
            total_bookings=Count('id')
        )
        .order_by('-total_bookings')[:10]
    )

    # -----------------------------------
    # TOP PERFORMING THEATERS
    # -----------------------------------

    top_theaters = (
        bookings.values(
            'theater__name',
            'theater__city'
        )
        .annotate(
            total_bookings=Count('id')
        )
        .order_by('-total_bookings')[:10]
    )

    # -----------------------------------
    # THEATER OCCUPANCY
    # -----------------------------------

    theater_occupancy = []

    theaters = Theater.objects.annotate(
        total_seats=Count(
            'seats',
            distinct=True
        ),
        booked_seats=Count(
            'seats__booking',
            distinct=True
        )
    )

    for theater in theaters:

        if theater.total_seats > 0:
            occupancy = (
                theater.booked_seats
                / theater.total_seats
            ) * 100
        else:
            occupancy = 0

        theater_occupancy.append({
            'name': theater.name,
            'city': theater.city,
            'total_seats': theater.total_seats,
            'booked_seats': theater.booked_seats,
            'occupancy_percentage': round(occupancy, 2)
        })

    theater_occupancy = sorted(
        theater_occupancy,
        key=lambda x: x['occupancy_percentage'],
        reverse=True
    )

    # -----------------------------------
    # PEAK BOOKING HOURS
    # -----------------------------------

    peak_booking_hours = (
        bookings.annotate(
            hour=TruncHour('booked_at')
        )
        .values('hour')
        .annotate(
            total=Count('id')
        )
        .order_by('-total')[:10]
    )

    # -----------------------------------
    # PAYMENT STATISTICS
    # -----------------------------------

    all_payments = Payment.objects.all()

    if start_date:
        all_payments = all_payments.filter(
            created_at__date__gte=start_date
        )

    if end_date:
        all_payments = all_payments.filter(
            created_at__date__lte=end_date
        )

    payment_stats = (
        all_payments.values('status')
        .annotate(
            total=Count('id')
        )
        .order_by('status')
    )

    failed_payments = all_payments.filter(
        status='failed'
    ).count()

    cancelled_payments = all_payments.filter(
        status='cancelled'
    ).count()

    successful_payments_count = all_payments.filter(
        status='success'
    ).count()

    # -----------------------------------
    # USER GROWTH
    # -----------------------------------

    users = User.objects.all()

    if start_date:
        users = users.filter(
            date_joined__date__gte=start_date
        )

    if end_date:
        users = users.filter(
            date_joined__date__lte=end_date
        )

    total_users = users.count()

    user_growth = (
        users.annotate(
            date=TruncDate('date_joined')
        )
        .values('date')
        .annotate(
            total=Count('id')
        )
        .order_by('date')
    )

    new_users_count = users.count()

    # -----------------------------------
    # SEND DATA TO TEMPLATE
    # -----------------------------------

    context = {
        'start_date': start_date,
        'end_date': end_date,

        'total_revenue': total_revenue,
        'daily_revenue': daily_revenue,
        'weekly_revenue': weekly_revenue,
        'monthly_revenue': monthly_revenue,
        'yearly_revenue': yearly_revenue,

        'total_bookings': total_bookings,
        'total_users': total_users,
        'new_users_count': new_users_count,

        'booking_trends': booking_trends,
        'most_booked_movies': most_booked_movies,
        'top_theaters': top_theaters,
        'theater_occupancy': theater_occupancy,
        'peak_booking_hours': peak_booking_hours,
        'payment_stats': payment_stats,

        'failed_payments': failed_payments,
        'cancelled_payments': cancelled_payments,
        'successful_payments_count': successful_payments_count,

        'user_growth': user_growth,
    }

    return render(
        request,
        'movies/admin_dashboard.html',
        context
    )