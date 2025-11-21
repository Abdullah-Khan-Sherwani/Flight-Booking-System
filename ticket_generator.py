# ticket_generator.py
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os
from datetime import datetime

class TicketGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.ticket_style = ParagraphStyle(
            'TicketStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
        )
        self.header_style = ParagraphStyle(
            'HeaderStyle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        self.subheader_style = ParagraphStyle(
            'SubheaderStyle',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=6,
        )

    def generate_ticket(self, ticket_data, output_path):
        """Generate a single ticket PDF"""
        doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        
        # Header
        elements.append(Paragraph("IAT AIRLINES - BOARDING PASS", self.header_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Passenger Information
        passenger_info = [
            ["PASSENGER", ""],
            ["Name:", f"{ticket_data['passenger_first_name']} {ticket_data['passenger_last_name']}"],
            ["CNIC:", ticket_data['passenger_cnic']],
            ["Booking ID:", ticket_data['booking_id']],
            ["Reservation ID:", ticket_data['reservation_id']],
            ["Ticket ID:", ticket_data['ticket_id']],
        ]
        
        passenger_table = Table(passenger_info, colWidths=[2*inch, 3*inch])
        passenger_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(passenger_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Flight Information
        flight_info = [
            ["FLIGHT", "", "", ""],
            ["Flight No:", ticket_data['flight_number'], "Class:", ticket_data['travel_class']],
            ["From:", ticket_data['departure_city'], "To:", ticket_data['arrival_city']],
            ["Departure:", ticket_data['departure_time'], "Arrival:", ticket_data['arrival_time']],
            ["Date:", ticket_data['flight_date'], "Seat:", ticket_data['seat_number']],
            ["Aircraft:", ticket_data['aircraft_type'], "Flight Type:", ticket_data['flight_type']],
        ]
        
        flight_table = Table(flight_info, colWidths=[1.2*inch, 1.8*inch, 1.2*inch, 1.8*inch])
        flight_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(flight_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Fare Information
        fare_info = [
            ["FARE INFORMATION", ""],
            ["Base Fare:", f"Rs.{ticket_data['seat_cost']:.2f}"],
            ["Taxes & Fees:", f"Rs.{ticket_data['taxes']:.2f}"],
            ["Total Paid:", f"Rs.{ticket_data['total_amount']:.2f}"],
        ]
        
        fare_table = Table(fare_info, colWidths=[2*inch, 3*inch])
        fare_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d5f4e6')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(fare_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Important Notes
        notes = [
            "IMPORTANT NOTES:",
            "• Please arrive at the airport at least 2 hours before departure",
            "• Bring valid government-issued photo ID and this ticket",
            "• Baggage allowance: 1 carry-on (7kg) + 1 checked bag (23kg)",
            "• Ticket is non-transferable and valid only for the named passenger",
            f"• Ticket issued on: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
        
        for note in notes:
            if note.startswith("IMPORTANT NOTES:"):
                elements.append(Paragraph(note, self.subheader_style))
            else:
                elements.append(Paragraph(note, self.ticket_style))
        
        # Build PDF
        doc.build(elements)

    def generate_all_tickets(self, booking_data, output_dir="tickets"):
        """Generate tickets for all passengers in a booking"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        ticket_files = []
        
        for i, passenger in enumerate(booking_data['passengers']):
            ticket_id = f"TKT{datetime.now().strftime('%Y%m%d%H%M%S')}{i:03d}"
            
            ticket_data = {
                'ticket_id': ticket_id,
                'booking_id': booking_data['booking_id'],
                'reservation_id': passenger['reservation_id'],
                'passenger_first_name': passenger['first_name'],
                'passenger_last_name': passenger['last_name'],
                'passenger_cnic': passenger['cnic'],
                'flight_number': booking_data['flight_number'],
                'departure_city': booking_data['departure_city'],
                'arrival_city': booking_data['arrival_city'],
                'departure_time': booking_data['departure_time'],
                'arrival_time': booking_data['arrival_time'],
                'flight_date': booking_data['flight_date'],
                'seat_number': passenger['seat_number'],
                'travel_class': booking_data['travel_class'],
                'aircraft_type': booking_data['aircraft_type'],
                'flight_type': booking_data['flight_type'],
                'seat_cost': passenger['seat_cost'],
                'taxes': passenger.get('taxes', 0),
                'total_amount': passenger.get('total_amount', passenger['seat_cost']),
            }
            
            filename = f"{output_dir}/{ticket_data['booking_id']}_{ticket_data['passenger_last_name']}_{i+1}.pdf"
            self.generate_ticket(ticket_data, filename)
            ticket_files.append(filename)
            
            print(f"Generated ticket: {filename}")
        
        return ticket_files

    def create_ticket_zip(self, ticket_files, output_filename):
        """Create a zip file containing all tickets"""
        import zipfile
        
        with zipfile.ZipFile(output_filename, 'w') as zipf:
            for ticket_file in ticket_files:
                zipf.write(ticket_file, os.path.basename(ticket_file))
        
        return output_filename