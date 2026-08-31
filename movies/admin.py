from django.contrib import admin
from .models import Movie, Theater, Seat, Booking, Review, Payment, MovieImage


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'genre',
        'language',
        'rating',
        'age_certification',
        'duration',
        'release_date',
        'popularity',
    )

    list_filter = (
        'genre',
        'language',
        'age_certification',
    )

    search_fields = (
        'name',
        'cast',
    )


@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'movie',
        'city',
        'screen',
        'time',
    )

    list_filter = (
        'city',
        'screen',
    )

    search_fields = (
        'name',
        'movie__name',
    )


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = (
        'seat_number',
        'theater',
        'status',
        'reserved_by',
        'reserved_until',
    )

    list_filter = (
        'status',
        'theater',
    )

    search_fields = (
        'seat_number',
        'theater__name',
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_id',
        'user',
        'movie',
        'theater',
        'seat',
        'payment_reference',
        'booked_at',
    )

    search_fields = (
        'booking_id',
        'payment_reference',
        'user__username',
        'movie__name',
    )

@admin.register(MovieImage)
class MovieImageAdmin(admin.ModelAdmin):
    list_display = (
        'movie',
        'image',
    )

    list_filter = (
        'movie',
    )

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        'movie',
        'user',
        'rating',
        'is_reported',
        'created_at',
    )

    list_filter = (
        'rating',
        'is_reported',
        'created_at',
    )

    search_fields = (
        'movie__name',
        'user__username',
        'comment',
    )

admin.site.register(Payment)