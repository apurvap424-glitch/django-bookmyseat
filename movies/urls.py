from django.urls import path
from . import views

urlpatterns = [

    path(
        '',
        views.movie_list,
        name='movie_list'
    ),

    path(
        '<int:movie_id>/theaters/',
        views.theater,
        name='theater'
    ),

    path(
        'theater/<int:theater_id>/seats/book/',
        views.book_Seats,
        name='book_seats'
    ),

    # PAYMENT
    path(
        'payment/success/',
        views.payment_success,
        name='payment_success'
    ),

    path(
        'payment/failed/',
        views.payment_failed,
        name='payment_failed'
    ),

    path(
        'payment-cancelled/',
        views.payment_cancelled,
        name='payment_cancelled'
    ),

    path(
        'razorpay/webhook/',
         views.razorpay_webhook,
         name='razorpay_webhook'
    ),

    # BOOKING
    path(
        'booking-success/',
        views.booking_success,
        name='booking_success'
    ),

    path(
        'booking-history/',
        views.booking_history,
        name='booking_history'
    ),

    path(
        'booking-history/<uuid:booking_id>/download/',
        views.download_ticket,
        name='download_ticket'
    ),

    # REVIEWS
    path(
        'movie/<int:movie_id>/review/',
        views.add_review,
        name='add_review'
    ),

    path(
        'review/<int:review_id>/report/',
        views.report_review,
        name='report_review'
    ),


    path(
        'admin-dashboard/',
         views.admin_dashboard,
         name='admin_dashboard'
    ),
]