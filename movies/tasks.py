from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from io import BytesIO
import cloudinary.uploader

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

    # Generate PDF in memory
    pdf_buffer = BytesIO()

    generate_ticket(
        booking,
        pdf_buffer
    )

    pdf_buffer.seek(0)

    # Upload PDF to Cloudinary
    upload_result = cloudinary.uploader.upload(
        pdf_buffer,
        resource_type="raw",
        public_id=f"tickets/ticket_{booking.booking_id}"
    )

    ticket_url = upload_result.get("secure_url")

    booking.ticket_url = ticket_url
    booking.save(update_fields=["ticket_url"])

    # Send email with PDF attachment
    pdf_buffer.seek(0)

    email = EmailMessage(
        subject="Your BookMySeat Ticket",
        body=f"""
Hello {booking.user.username},

Your movie ticket has been booked successfully!

Movie: {booking.movie.name}
Theater: {booking.theater.name}
Seat: {booking.seat.seat_number}
Booking ID: {booking.booking_id}

Your ticket is also available here:
{ticket_url}

Thank you for booking with BookMySeat.
""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[booking.user.email],
    )

    email.attach(
        f"ticket_{booking.booking_id}.pdf",
        pdf_buffer.read(),
        "application/pdf"
    )

    email.send()

    return f"Ticket uploaded and sent for booking {booking.booking_id}"