from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import qrcode


def generate_ticket(booking, file_path):

    c = canvas.Canvas(file_path, pagesize=A4)

    width, height = A4

    

    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(
        width / 2,
        height - 35 * mm,
        "BOOKMYSEAT"
    )

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(
        width / 2,
        height - 48 * mm,
        "MOVIE TICKET"
    )

    

    c.setFont("Helvetica", 12)

    y = height - 75 * mm

    details = [
        f"Booking ID: {booking.booking_id}",
        f"Payment Reference: {booking.payment_reference}",
        f"Movie: {booking.movie.name}",
        f"Theater: {booking.theater.name}",
        f"Screen: {booking.theater.screen}",
        f"Show Time: {booking.theater.time.strftime('%d-%m-%Y %I:%M %p')}",
        f"Seat: {booking.seat.seat_number}",
        f"Customer: {booking.user.username}",
        f"Booked At: {booking.booked_at.strftime('%d-%m-%Y %I:%M %p')}",
    ]

    for detail in details:
        c.drawString(35 * mm, y, detail)
        y -= 10 * mm

    

    qr_data = (
        f"Booking ID: {booking.booking_id}\n"
        f"Payment Reference: {booking.payment_reference}\n"
        f"Movie: {booking.movie.name}\n"
        f"Seat: {booking.seat.seat_number}"
    )

    qr = qrcode.make(qr_data)

    qr_path = f"{file_path}_qr.png"
    qr.save(qr_path)

    c.drawImage(
        qr_path,
        width - 70 * mm,
        35 * mm,
        width=40 * mm,
        height=40 * mm
    )

    

    c.setFont("Helvetica-Bold", 11)

    c.drawString(
        35 * mm,
        40 * mm,
        "Scan QR code to verify your booking."
    )

    c.setFont("Helvetica", 10)

    c.drawString(
        35 * mm,
        30 * mm,
        "Thank you for booking with BookMySeat!"
    )

    c.save()