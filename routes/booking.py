# routes/booking.py
# Booking flow routes - seat selection, passenger info, process booking, tickets

from flask import Blueprint, render_template, request, redirect, session, url_for, send_file
from db import get_connection
from datetime import datetime
from ticket_generator import TicketGenerator
from utils import generate_sequential_id, clear_booking_session
import re
import os
import zipfile
from io import BytesIO

booking_bp = Blueprint('booking', __name__)


@booking_bp.route('/seat-selection')
def seat_selection():
    # Check if this is a reschedule operation
    reschedule_reservation_id = session.get('reschedule_reservation_id')
    
    if reschedule_reservation_id:
        # This is a reschedule flow - use the reschedule flight
        flight_id = session.get('reschedule_new_flight')
        if not flight_id:
            return render_template('error.html', error="Reschedule flight not found")
        # Set other parameters as needed
        session['travel_class'] = session.get('search_travel_class', 'ECO')
        session['passengers'] = 1  # Reschedule is per reservation
        session['trip_type'] = 'one_way'
        session['selected_outbound_flight'] = flight_id
        
        # Store that this is a reschedule operation
        session['is_reschedule'] = True
    else:
        # Normal booking flow
        flight_id = session.get('selected_outbound_flight')
        if not flight_id:
            return render_template('error.html', error="No flight selected")
    
    return_flight_id = session.get('selected_return_flight')
    passengers = int(session.get('passengers', 1))
    travel_class = session.get('travel_class', 'ECO')
    trip_type = session.get('trip_type', 'one_way')
    
    print(f"DEBUG - travel_class from session: {travel_class}")
    print(f"DEBUG - passengers: {passengers}")
    print(f"DEBUG - trip_type: {trip_type}")
    print(f"DEBUG - Reschedule mode: {reschedule_reservation_id is not None}")
    print(f"DEBUG - Flight ID: {flight_id}")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get outbound flight details using new schema
        cursor.execute("""
            SELECT fi.Instance_ID, fi.Model_ID, 
                   c1.City_Name, c2.City_Name,
                   TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            WHERE fi.Instance_ID = :flight_id
        """, flight_id=flight_id)
        
        outbound_flight = cursor.fetchone()
        
        if not outbound_flight:
            return render_template('error.html', error="Outbound flight not found")
        
        return_flight = None
        if return_flight_id:
            cursor.execute("""
                SELECT fi.Instance_ID, fi.Model_ID, 
                       c1.City_Name, c2.City_Name,
                       TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                JOIN City c1 ON zm1.City_ID = c1.City_ID
                JOIN City c2 ON zm2.City_ID = c2.City_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=return_flight_id)
            return_flight = cursor.fetchone()
            
            if not return_flight:
                return render_template('error.html', error="Return flight not found")
        
        # Get available seats for outbound flight using new schema
        cursor.execute("""
            SELECT asm.Row_Number, asm.Seat_Letter, arc.Class_ID,
                   CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
            FROM Aircraft_Seat_Map asm
            JOIN Aircraft_Row_Class arc ON asm.Model_ID = arc.Model_ID AND asm.Row_Number = arc.Row_Number
            LEFT JOIN Reservation r ON asm.Model_ID = :model_id 
                AND asm.Row_Number = r.Row_Number 
                AND asm.Seat_Letter = r.Seat_Letter
                AND r.Instance_ID = :flight_id
            WHERE asm.Model_ID = :model_id
            AND arc.Class_ID = :travel_class
            ORDER BY asm.Row_Number, asm.Seat_Letter
        """, model_id=outbound_flight[1], flight_id=flight_id, travel_class=travel_class)
        
        outbound_seats = cursor.fetchall()
        
        # Get ALL booked seats for outbound flight (regardless of class) for the seat map
        cursor.execute("""
            SELECT r.Row_Number, r.Seat_Letter
            FROM Reservation r
            WHERE r.Instance_ID = :flight_id
            AND r.Booking_ID != COALESCE(:reschedule_booking_id, '0')
        """, flight_id=flight_id, reschedule_booking_id=session.get('reschedule_original_booking'))

        booked_outbound_seats = [f"{row[0]}{row[1]}" for row in cursor.fetchall()]
        print(f"DEBUG - Booked outbound seats (excluding reschedule): {booked_outbound_seats}")
        
        return_seats = []
        booked_return_seats = []
        
        if return_flight_id and return_flight:
            cursor.execute("""
                SELECT asm.Row_Number, asm.Seat_Letter, arc.Class_ID,
                       CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
                FROM Aircraft_Seat_Map asm
                JOIN Aircraft_Row_Class arc ON asm.Model_ID = arc.Model_ID AND asm.Row_Number = arc.Row_Number
                LEFT JOIN Reservation r ON asm.Model_ID = :model_id 
                    AND asm.Row_Number = r.Row_Number 
                    AND asm.Seat_Letter = r.Seat_Letter
                    AND r.Instance_ID = :flight_id
                WHERE asm.Model_ID = :model_id
                AND arc.Class_ID = :travel_class
                ORDER BY asm.Row_Number, asm.Seat_Letter
            """, model_id=return_flight[1], flight_id=return_flight_id, travel_class=travel_class)
            
            return_seats = cursor.fetchall()
            
            # Get ALL booked seats for return flight
            cursor.execute("""
                SELECT r.Row_Number, r.Seat_Letter
                FROM Reservation r
                WHERE r.Instance_ID = :flight_id
            """, flight_id=return_flight_id)
            
            booked_return_seats = [f"{row[0]}{row[1]}" for row in cursor.fetchall()]
            print(f"DEBUG - Booked return seats: {booked_return_seats}")
        
        # Ensure travel_class is one of the expected values
        if travel_class not in ['ECO', 'BUS', 'FIR']:
            travel_class = 'ECO'
        
        return render_template('seat_selection.html',
                            outbound_flight=outbound_flight,
                            return_flight=return_flight,
                            outbound_seats=outbound_seats,
                            return_seats=return_seats,
                            booked_outbound_seats=booked_outbound_seats,
                            booked_return_seats=booked_return_seats,
                            passengers=passengers,
                            travel_class=travel_class,
                            trip_type=trip_type,
                            is_reschedule=reschedule_reservation_id is not None)
        
    except Exception as e:
        print("Error in seat selection:", e)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error="Error loading seat selection")
        
    finally:
        cursor.close()
        conn.close()


@booking_bp.route('/passenger-info', methods=['GET', 'POST'])
def passenger_info():
    if request.method == 'POST':
        # Check if this is a reschedule operation
        if session.get('is_reschedule'):
            print("DEBUG - Detected reschedule operation, redirecting to complete_reschedule")
            return redirect(url_for('management.complete_reschedule'))
        
        # Handle form submission from seat selection for NORMAL booking
        selected_outbound_seats = request.form.getlist('selected_outbound_seats')
        selected_return_seats = request.form.getlist('selected_return_seats')
        
        # Store in session for booking processing
        session['selected_outbound_seats'] = selected_outbound_seats
        session['selected_return_seats'] = selected_return_seats
        
        # Get flight details
        flight_id = session.get('selected_outbound_flight')
        return_flight_id = session.get('selected_return_flight')
        passengers = int(session.get('passengers', 1))
        travel_class = session.get('travel_class', 'ECO')
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Get outbound flight details
            cursor.execute("""
                SELECT fi.Instance_ID, fi.Model_ID, 
                       c1.City_Name, c2.City_Name,
                       TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                JOIN City c1 ON zm1.City_ID = c1.City_ID
                JOIN City c2 ON zm2.City_ID = c2.City_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=flight_id)
            outbound_flight = cursor.fetchone()
            
            return_flight = None
            if return_flight_id:
                cursor.execute("""
                    SELECT fi.Instance_ID, fi.Model_ID, 
                           c1.City_Name, c2.City_Name,
                           TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI')
                    FROM Flight_Instance fi
                    JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                    JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
                    JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
                    JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
                    JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
                    JOIN City c1 ON zm1.City_ID = c1.City_ID
                    JOIN City c2 ON zm2.City_ID = c2.City_ID
                    WHERE fi.Instance_ID = :flight_id
                """, flight_id=return_flight_id)
                return_flight = cursor.fetchone()
            
            # Get user's contact information from session
            user_email = session.get('user_email', '')
            user_phone = session.get('user_phone', '')
            
            return render_template('passenger_info.html',
                                outbound_flight=outbound_flight,
                                return_flight=return_flight,
                                selected_outbound_seats=selected_outbound_seats,
                                selected_return_seats=selected_return_seats,
                                passengers=passengers,
                                travel_class=travel_class,
                                user_email=user_email,
                                user_phone=user_phone)
            
        except Exception as e:
            print("Error in passenger info:", e)
            return render_template('error.html', error="Error loading passenger information")
            
        finally:
            cursor.close()
            conn.close()
    
    else:
        # GET request - redirect to seat selection if no seats selected
        if 'selected_outbound_seats' not in session:
            return redirect('/seat-selection')
        
        return redirect('/seat-selection')


@booking_bp.route('/process-booking', methods=['POST'])
def process_booking():
    try:
        # Get passenger data from form
        passengers = int(session.get('passengers', 1))
        passenger_data = []
        
        # Get contact information from separate fields
        contact_email = request.form.get('contact_email')
        contact_phone = request.form.get('contact_phone')
        
        print(f"DEBUG - Contact Email: {contact_email}")
        print(f"DEBUG - Contact Phone: {contact_phone}")
        
        for i in range(passengers):
            passenger_data.append({
                'first_name': request.form.get(f'first_name_{i}'),
                'last_name': request.form.get(f'last_name_{i}'),
                'date_of_birth': request.form.get(f'date_of_birth_{i}'),
                'gender': request.form.get(f'gender_{i}'),
                'passport_number': request.form.get(f'passport_number_{i}', ''),
                'nationality': request.form.get(f'nationality_{i}', 'US'),
                'title': request.form.get(f'title_{i}', 'MR')
            })
        
        # Get seat selections
        selected_outbound_seats = request.form.getlist('selected_outbound_seats')
        selected_return_seats = request.form.getlist('selected_return_seats')
        outbound_flight_id = session.get('selected_outbound_flight')
        return_flight_id = session.get('selected_return_flight')
        trip_type = session.get('trip_type', 'one_way')
        travel_class = session.get('travel_class', 'ECO')
        
        print(f"DEBUG - Outbound flight: {outbound_flight_id}")
        print(f"DEBUG - Return flight: {return_flight_id}")
        print(f"DEBUG - Outbound seats: {selected_outbound_seats}")
        print(f"DEBUG - Return seats: {selected_return_seats}")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            total_amount = 0

            # Get flight details for pricing
            cursor.execute("""
                SELECT fi.Model_ID, fr.Route_ID 
                FROM Flight_Instance fi
                JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                WHERE fi.Instance_ID = :flight_id
            """, flight_id=outbound_flight_id)
            flight_info = cursor.fetchone()
            model_id = flight_info[0]
            route_id = flight_info[1]
            
            # Calculate total amount using Route_Pricing
            cursor.execute("""
                SELECT Base_Price FROM Route_Pricing 
                WHERE Route_ID = :route_id 
                AND Class_ID = :class_id
                AND SYSDATE BETWEEN Valid_From AND Valid_To
            """, route_id=route_id, class_id=travel_class)
            
            pricing_result = cursor.fetchone()
            if pricing_result:
                base_price = pricing_result[0]
                total_amount = base_price * len(selected_outbound_seats)
                print(f"DEBUG - Base price for {travel_class}: {base_price}")
            else:
                default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                base_price = default_costs.get(travel_class, 100)
                total_amount = base_price * len(selected_outbound_seats)
                print(f"DEBUG - Using default price for {travel_class}: {base_price}")
            
            # Add return flight cost if applicable
            if return_flight_id:
                cursor.execute("""
                    SELECT fr.Route_ID 
                    FROM Flight_Instance fi
                    JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                    WHERE fi.Instance_ID = :flight_id
                """, flight_id=return_flight_id)
                return_route_info = cursor.fetchone()
                return_route_id = return_route_info[0]
                
                cursor.execute("""
                    SELECT Base_Price FROM Route_Pricing 
                    WHERE Route_ID = :route_id 
                    AND Class_ID = :class_id
                    AND SYSDATE BETWEEN Valid_From AND Valid_To
                """, route_id=return_route_id, class_id=travel_class)
                
                return_pricing_result = cursor.fetchone()
                if return_pricing_result:
                    return_base_price = return_pricing_result[0]
                    total_amount += return_base_price * len(selected_return_seats)
                    print(f"DEBUG - Return base price: {return_base_price}")
                else:
                    default_costs = {'ECO': 100, 'BUS': 300, 'FIR': 500}
                    return_base_price = default_costs.get(travel_class, 100)
                    total_amount += return_base_price * len(selected_return_seats)
                    print(f"DEBUG - Using default return price: {return_base_price}")
            
            print(f"DEBUG - Total amount: {total_amount}")
            
            # Create booking (PNR will be auto-generated by trigger)
            print(f"DEBUG - Creating booking with contact: {contact_email}, {contact_phone}")
            cursor.execute("""
                INSERT INTO Booking 
                (Booking_Date, Booking_Status, Contact_Email, Emergency_Phone)
                VALUES (SYSTIMESTAMP, 'CONFIRMED', :email, :phone)
            """, 
            email=contact_email,
            phone=contact_phone)
            
            # Get the auto-generated booking ID
            cursor.execute("SELECT Booking_ID FROM Booking WHERE Contact_Email = :email AND Emergency_Phone = :phone ORDER BY Booking_Date DESC FETCH FIRST 1 ROW ONLY", 
                         email=contact_email, phone=contact_phone)
            booking_result = cursor.fetchone()
            booking_id = booking_result[0]
            print(f"DEBUG - Generated Booking ID: {booking_id}")
            
            # Insert passengers
            passenger_ids = []
            for i, passenger in enumerate(passenger_data):
                print(f"DEBUG - Inserting passenger {i}: {passenger['first_name']} {passenger['last_name']}")
                
                cursor.execute("""
                    INSERT INTO Passenger 
                    (First_Name, Last_Name, Date_Of_Birth, Gender, Nationality, Passport_Num, Title)
                    VALUES (:first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :nationality, :passport, :title)
                """, 
                first_name=passenger['first_name'],
                last_name=passenger['last_name'],
                dob=passenger['date_of_birth'],
                gender=passenger['gender'],
                nationality=passenger['nationality'],
                passport=passenger['passport_number'],
                title=passenger['title'])
                
                # Get the generated passenger ID
                cursor.execute("SELECT Passenger_ID FROM Passenger WHERE First_Name = :first_name AND Last_Name = :last_name AND Date_Of_Birth = TO_DATE(:dob, 'YYYY-MM-DD')", 
                             first_name=passenger['first_name'], last_name=passenger['last_name'], dob=passenger['date_of_birth'])
                passenger_result = cursor.fetchone()
                passenger_ids.append(passenger_result[0])
                print(f"DEBUG - Passenger {i} ID: {passenger_result[0]}")
            
            # Create reservations for outbound flight
            for i, seat_simple in enumerate(selected_outbound_seats):
                if i < len(passenger_ids):
                    # Parse seat information
                    row_match = re.search(r'\d+', seat_simple)
                    letter_match = re.search(r'[A-Z]', seat_simple)
                    
                    if not row_match or not letter_match:
                        print(f"ERROR - Invalid seat format: {seat_simple}")
                        continue
                    
                    row_num = int(row_match.group())
                    seat_letter = letter_match.group()
                    
                    # Verify seat exists in aircraft model
                    cursor.execute("""
                        SELECT 1 FROM Aircraft_Seat_Map 
                        WHERE Model_ID = :model_id 
                        AND Row_Number = :row_num 
                        AND Seat_Letter = :seat_letter
                    """, model_id=model_id, row_num=row_num, seat_letter=seat_letter)
                    
                    if not cursor.fetchone():
                        print(f"ERROR - Seat {seat_simple} not found in aircraft model {model_id}")
                        continue
                    
                    # Get seat price
                    cursor.execute("""
                        SELECT Base_Price FROM Route_Pricing 
                        WHERE Route_ID = :route_id 
                        AND Class_ID = :class_id
                        AND SYSDATE BETWEEN Valid_From AND Valid_To
                    """, route_id=route_id, class_id=travel_class)
                    
                    seat_price_result = cursor.fetchone()
                    seat_price = seat_price_result[0] if seat_price_result else base_price
                    
                    # Create reservation
                    res_id = generate_sequential_id("RES", "Reservation", "Reservation_ID", cursor)
                    
                    print(f"DEBUG - Creating outbound reservation {i}: {res_id} for seat {row_num}{seat_letter}")
                    
                    cursor.execute("""
                        INSERT INTO Reservation 
                        (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged)
                        VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price)
                    """, 
                    res_id=res_id,
                    booking_id=booking_id,
                    passenger_id=passenger_ids[i],
                    instance_id=outbound_flight_id,
                    row_num=row_num,
                    seat_letter=seat_letter,
                    price=seat_price)
                    print(f"DEBUG - Outbound reservation {i} created successfully")
            
            # Create reservations for return flight if applicable
            if return_flight_id:
                cursor.execute("""
                    SELECT fi.Model_ID, fr.Route_ID 
                    FROM Flight_Instance fi
                    JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
                    WHERE fi.Instance_ID = :flight_id
                """, flight_id=return_flight_id)
                return_flight_info = cursor.fetchone()
                return_model_id = return_flight_info[0]
                return_route_id = return_flight_info[1]
                
                for i, seat_simple in enumerate(selected_return_seats):
                    if i < len(passenger_ids):
                        # Parse seat information
                        row_match = re.search(r'\d+', seat_simple)
                        letter_match = re.search(r'[A-Z]', seat_simple)
                        
                        if not row_match or not letter_match:
                            print(f"ERROR - Invalid return seat format: {seat_simple}")
                            continue
                        
                        row_num = int(row_match.group())
                        seat_letter = letter_match.group()
                        
                        # Verify seat exists in return aircraft model
                        cursor.execute("""
                            SELECT 1 FROM Aircraft_Seat_Map 
                            WHERE Model_ID = :model_id 
                            AND Row_Number = :row_num 
                            AND Seat_Letter = :seat_letter
                        """, model_id=return_model_id, row_num=row_num, seat_letter=seat_letter)
                        
                        if not cursor.fetchone():
                            print(f"ERROR - Return seat {seat_simple} not found in aircraft model {return_model_id}")
                            continue
                        
                        # Get return seat price
                        cursor.execute("""
                            SELECT Base_Price FROM Route_Pricing 
                            WHERE Route_ID = :route_id 
                            AND Class_ID = :class_id
                            AND SYSDATE BETWEEN Valid_From AND Valid_To
                        """, route_id=return_route_id, class_id=travel_class)
                        
                        return_seat_price_result = cursor.fetchone()
                        return_seat_price = return_seat_price_result[0] if return_seat_price_result else base_price
                        
                        # Create return reservation
                        res_id = generate_sequential_id("RES", "Reservation", "Reservation_ID", cursor)
                        
                        print(f"DEBUG - Creating return reservation {i}: {res_id} for seat {row_num}{seat_letter}")
                        
                        cursor.execute("""
                            INSERT INTO Reservation 
                            (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged)
                            VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price)
                        """, 
                        res_id=res_id,
                        booking_id=booking_id,
                        passenger_id=passenger_ids[i],
                        instance_id=return_flight_id,
                        row_num=row_num,
                        seat_letter=seat_letter,
                        price=return_seat_price)
                        print(f"DEBUG - Return reservation {i} created successfully")
            
            # Create initial payment record
            payment_id = generate_sequential_id("PAY", "Payment", "Payment_ID", cursor)
            cursor.execute("""
                INSERT INTO Payment 
                (Payment_ID, Booking_ID, Amount_Paid, Payment_Date, Payment_Method)
                VALUES (:payment_id, :booking_id, :amount, SYSTIMESTAMP, 'CREDIT_CARD')
            """,
            payment_id=payment_id,
            booking_id=booking_id,
            amount=total_amount)
            
            conn.commit()
            print(f"DEBUG - All database operations completed successfully!")
            
            # Clear session data
            clear_booking_session(session)
            
            return redirect(url_for('booking.booking_confirmation', 
                        booking_id=booking_id, 
                        passenger_count=passengers,
                        total_amount=total_amount,
                        auto_download='true'))
            
        except Exception as e:
            conn.rollback()
            print("Database error during booking:", e)
            print("Error type:", type(e).__name__)
            
            error_msg = f"Booking failed: {str(e)}"
            if "unique constraint" in str(e):
                error_msg += ". This usually means the booking reference already exists. Please try again."
            elif "parent key not found" in str(e):
                error_msg += ". This usually means a seat or passenger reference is invalid."
            return render_template('error.html', error=error_msg)
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print("Booking processing error:", e)
        return render_template('error.html', error="Booking processing failed.")


@booking_bp.route('/booking-confirmation')
def booking_confirmation():
    """Display booking confirmation page and trigger automatic download"""
    booking_id = request.args.get('booking_id')
    passenger_count = request.args.get('passenger_count')
    total_amount = request.args.get('total_amount')
    auto_download = request.args.get('auto_download', 'true')
    
    if not booking_id:
        return render_template('error.html', error="Booking confirmation data missing")
    
    # Store booking info in session for auto-download detection
    session['last_booking_id'] = booking_id
    session['auto_download'] = auto_download == 'true'
    
    return render_template('booking_confirmation.html', 
                          booking_id=booking_id,
                          passenger_count=passenger_count,
                          total_amount=total_amount,
                          auto_download=auto_download == 'true')


@booking_bp.route('/download-tickets/<booking_id>')
def download_tickets(booking_id):
    """Download all tickets for a booking as a ZIP file"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get booking and passenger details using new schema
        cursor.execute("""
            SELECT b.Booking_ID, 
                   p.Passenger_ID, p.First_Name, p.Last_Name, p.Title, p.Nationality,
                   r.Reservation_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   fi.Instance_ID, fi.Model_ID,
                   TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI'),
                   TO_CHAR(fi.Arrival_Time, 'DD-MON-YYYY HH24:MI'),
                   a1.Airport_Name, a2.Airport_Name,
                   c1.City_Name, c2.City_Name,
                   arc.Class_ID
            FROM Booking b
            JOIN Reservation r ON b.Booking_ID = r.Booking_ID
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND r.Row_Number = arc.Row_Number
            WHERE b.Booking_ID = :booking_id
            ORDER BY fi.Departure_Time, p.Last_Name
        """, booking_id=booking_id)
        
        booking_data = cursor.fetchall()
        
        if not booking_data:
            return render_template('error.html', error="Booking not found")
        
        # Organize data for ticket generation
        passengers_data = []
        booking_info = {
            'booking_id': booking_data[0][0],
            'total_amount': sum(float(row[9]) for row in booking_data),
            'flight_number': booking_data[0][10],
            'aircraft_type': booking_data[0][11],
            'departure_time': booking_data[0][12],
            'arrival_time': booking_data[0][13],
            'departure_airport': booking_data[0][14],
            'arrival_airport': booking_data[0][15],
            'departure_city': booking_data[0][16],
            'arrival_city': booking_data[0][17],
            'travel_class': booking_data[0][18],
        }
        
        # Extract flight date from departure time
        flight_date = booking_data[0][12].split(' ')[0]
        booking_info['flight_date'] = flight_date
        
        for row in booking_data:
            passenger = {
                'passenger_id': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'title': row[4],
                'nationality': row[5],
                'reservation_id': row[6],
                'row_number': row[7],
                'seat_letter': row[8],
                'seat_number': f"{row[7]}{row[8]}",
                'seat_cost': float(row[9]),
            }
            passengers_data.append(passenger)
        
        # Generate tickets
        booking_info['passengers'] = passengers_data
        booking_info['flight_type'] = 'ONE-WAY'
        
        ticket_gen = TicketGenerator()
        all_tickets = ticket_gen.generate_all_tickets(booking_info, "temp_tickets")
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for ticket_file in all_tickets:
                zipf.write(ticket_file, os.path.basename(ticket_file))
        
        zip_buffer.seek(0)
        
        # Clean up temporary files
        for ticket_file in all_tickets:
            try:
                os.remove(ticket_file)
            except:
                pass
        
        # Send ZIP file
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'tickets_{booking_id}.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        print("Error generating tickets:", e)
        return render_template('error.html', error="Error generating tickets")
    
    finally:
        cursor.close()
        conn.close()


@booking_bp.route('/view-ticket/<reservation_id>')
def view_ticket(reservation_id):
    """View a single ticket"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT r.Reservation_ID, r.Booking_ID, r.Passenger_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
                   fi.Instance_ID, fi.Model_ID,
                   TO_CHAR(fi.Departure_Time, 'DD-MON-YYYY HH24:MI'),
                   TO_CHAR(fi.Arrival_Time, 'DD-MON-YYYY HH24:MI'),
                   a1.Airport_Name, a2.Airport_Name,
                   c1.City_Name, c2.City_Name,
                   arc.Class_ID
            FROM Reservation r
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            JOIN Airport a1 ON fr.Source_Airport = a1.Airport_ID
            JOIN Airport a2 ON fr.Dest_Airport = a2.Airport_ID
            JOIN Zip_Master zm1 ON a1.Zipcode = zm1.Zipcode
            JOIN Zip_Master zm2 ON a2.Zipcode = zm2.Zipcode
            JOIN City c1 ON zm1.City_ID = c1.City_ID
            JOIN City c2 ON zm2.City_ID = c2.City_ID
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND r.Row_Number = arc.Row_Number
            WHERE r.Reservation_ID = :reservation_id
        """, reservation_id=reservation_id)
        
        ticket_data = cursor.fetchone()
        
        if not ticket_data:
            return render_template('error.html', error="Ticket not found")
        
        # Prepare data for ticket template
        context = {
            'reservation_id': ticket_data[0],
            'booking_id': ticket_data[1],
            'passenger_id': ticket_data[2],
            'row_number': ticket_data[3],
            'seat_letter': ticket_data[4],
            'seat_cost': float(ticket_data[5]),
            'passenger_name': f"{ticket_data[6]} {ticket_data[7]}",
            'title': ticket_data[8],
            'nationality': ticket_data[9],
            'seat_number': f"{ticket_data[3]}{ticket_data[4]}",
            'flight_number': ticket_data[10],
            'aircraft_type': ticket_data[11],
            'departure_time': ticket_data[12],
            'arrival_time': ticket_data[13],
            'departure_airport': ticket_data[14],
            'arrival_airport': ticket_data[15],
            'departure_city': ticket_data[16],
            'arrival_city': ticket_data[17],
            'travel_class': ticket_data[18],
            'flight_date': ticket_data[12].split(' ')[0],
            'ticket_id': f"TKT{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }
        
        return render_template('ticket_template.html', **context)
        
    except Exception as e:
        print("Error viewing ticket:", e)
        return render_template('error.html', error="Error loading ticket")
    
    finally:
        cursor.close()
        conn.close()
