import uuid
import random
from django.db import models
from django.contrib.auth.models import User 


class Movie(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    cast = models.TextField()
    description = models.TextField(blank=True, null=True)

    genre = models.CharField(max_length=100, default="Action")
    language = models.CharField(max_length=50, default="English")
    release_date = models.DateField(null=True, blank=True)
    ticket_price = models.DecimalField(max_digits=8, decimal_places=2, default=200)
    popularity = models.IntegerField(default=0)

    trailer_url = models.URLField(blank=True, null=True)
    age_certification = models.CharField(max_length=10,default="U")
    duration = models.PositiveIntegerField(default=120,help_text="Duration in minutes")

    def __str__(self):
        return self.name

class MovieImage(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='posters'
    )

    image = models.ImageField(
        upload_to='movie_posters/'
    )

    def __str__(self):
        return f'{self.movie.name} Poster'
    
class Theater(models.Model):
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100, default="Mumbai")
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='theaters'
    )
    screen = models.CharField(max_length=50, default="Screen 1")
    time = models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

class Seat(models.Model):

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('booked', 'Booked'),
    ]

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='seats'
    )

    seat_number = models.CharField(max_length=10)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )

    reserved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reserved_seats'
    )

    reserved_until = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'

class Booking(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    booking_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    payment_reference = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        editable=False
    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE,
        related_name="bookings"
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE
    )

    booked_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.payment_reference:
            self.payment_reference = f"PAY-{random.randint(100000, 999999)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Booking by {self.user.username} for {self.seat.seat_number} at {self.theater.name}'

    class Meta:
        indexes = [
            models.Index(fields=['booked_at']),
            models.Index(fields=['movie', 'booked_at']),
            models.Index(fields=['theater', 'booked_at']),
            models.Index(fields=['user', 'booked_at']),
        ]


class Review(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='movie_reviews'
    )

    rating = models.PositiveIntegerField(
        choices=[
            (1, '1 Star'),
            (2, '2 Stars'),
            (3, '3 Stars'),
            (4, '4 Stars'),
            (5, '5 Stars'),
        ]
    )

    comment = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_reported = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.movie.name} - {self.user.username} - {self.rating} Stars'


class Payment(models.Model):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='payment',
        null=True,
        blank=True
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    razorpay_order_id = models.CharField(
        max_length=100,
        unique=True
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    razorpay_signature = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='created'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.status}"

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
        ]