from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
import os

from .models import Booking
from .ticket import generate_ticket


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3}
)
def generate_and_send_ticket(self, booking_id):

    booking = Booking.objects.get(id=booking_id)

    
    ticket_dir = os.path.join(
        settings.MEDIA_ROOT,
        'tickets'
    )

    os.makedirs(ticket_dir, exist_ok=True)

   
    ticket_path = os.path.join(
        ticket_dir,
        f'ticket_{booking.booking_id}.pdf'
    )

   
    generate_ticket(
        booking,
        ticket_path
    )

    
    email = EmailMessage(
        subject="Your BookMySeat Ticket",
        body=f"""
Hello {booking.user.username},

Your movie ticket has been booked successfully!

Movie: {booking.movie.name}
Theater: {booking.theater.name}
Seat: {booking.seat.seat_number}
Booking ID: {booking.booking_id}

Thank you for booking with BookMySeat.
""",
        from_email="bookmyseat@example.com",
        to=[booking.user.email],
    )

  
    with open(ticket_path, "rb") as ticket_file:
        email.attach(
            f"ticket_{booking.booking_id}.pdf",
            ticket_file.read(),
            "application/pdf"
        )

   
    email.send()

    return f"Ticket sent for booking {booking.booking_id}"