# routes/management.py
# Booking management routes - verify, cancel, reschedule

from flask import Blueprint, render_template, request, redirect, session, url_for
from db import get_connection
from datetime import datetime
from utils import clear_reschedule_session, generate_sequential_id
import re

management_bp = Blueprint('management', __name__)


@management_bp.route('/manage-bookings')
def manage_bookings():
    return render_template('manage_bookings.html')


@management_bp.route('/verify-booking', methods=['POST'])
def verify_booking():
    booking_id = request.form.get('booking_id')
    email = request.form.get('email')
    action_type = request.form.get('action_type')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verify booking exists and email matches
        cursor.execute("""
            SELECT b.Booking_ID, b.Booking_Status, b.Contact_Email, b.Emergency_Phone
            FROM Booking b
            WHERE b.Booking_ID = :booking_id 
            AND (b.Contact_Email = :email OR b.Emergency_Phone = :email)
        """, booking_id=booking_id, email=email)
        
        booking = cursor.fetchone()
        if not booking:
            return render_template('error.html', error="Booking not found or contact information doesn't match")
        
        # Get all reservations for this booking
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
                   fi.Departure_Time, fi.Arrival_Time,
                   a1.Airport_Name as Departure_Airport, a2.Airport_Name as Arrival_Airport,
                   c1.City_Name as Departure_City, c2.City_Name as Arrival_City,
                   arc.Class_ID as Travel_Class
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
            WHERE r.Booking_ID = :booking_id
            ORDER BY fi.Departure_Time
        """, booking_id=booking_id)
        
        reservations = cursor.fetchall()
        
        # Convert to list of dictionaries for easier template handling
        reservation_list = []
        for res in reservations:
            reservation_list.append({
                'reservation_id': res[0],
                'passenger_id': res[1],
                'instance_id': res[2],
                'row_number': res[3],
                'seat_letter': res[4],
                'seat_cost': float(res[5]),
                'passenger_name': f"{res[6]} {res[7]}",
                'title': res[8],
                'nationality': res[9],
                'departure_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[11].strftime('%d-%b-%Y %H:%M'),
                'departure_airport': res[12],
                'arrival_airport': res[13],
                'departure_city': res[14],
                'arrival_city': res[15],
                'travel_class': res[16],
                'seat_number': f"{res[3]}{res[4]}"
            })
        
        booking_info = {
            'booking_id': booking[0],
            'booking_status': booking[1],
            'contact_email': booking[2],
            'contact_phone': booking[3]
        }
        
        # Store in session for next steps
        session['manage_booking_info'] = {
            'email': email,
            'booking_id': booking_id,
            'action_type': action_type
        }
        
        return render_template('booking_actions.html',
                             booking_info=booking_info,
                             reservations=reservation_list,
                             email=email,
                             action_type=action_type)
        
    except Exception as e:
        print("Error verifying booking:", e)
        return render_template('error.html', error="Error retrieving booking details")
    finally:
        cursor.close()
        conn.close()


@management_bp.route('/process-booking-action', methods=['POST'])
def process_booking_action():
    email = request.form.get('email')
    booking_id = request.form.get('booking_id')
    action_type = request.form.get('action_type')
    selected_reservations = request.form.getlist('selected_reservations')
    
    if not selected_reservations:
        return render_template('error.html', error="No reservations selected")
    
    session['selected_reservations'] = selected_reservations
    session['action_booking_id'] = booking_id
    session['action_email'] = email
    
    if action_type == 'cancel':
        return cancel_reservations(selected_reservations, booking_id, email)
    elif action_type == 'reschedule':
        return redirect_to_reschedule(selected_reservations[0])


def cancel_reservations(reservation_ids, booking_id, email):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        total_refund = 0
        
        for res_id in reservation_ids:
            # Get reservation details for cancellation log
            cursor.execute("""
                SELECT r.Price_Charged, r.Passenger_ID, r.Instance_ID
                FROM Reservation r
                WHERE r.Reservation_ID = :res_id
            """, res_id=res_id)
            
            res_details = cursor.fetchone()
            if res_details:
                seat_cost = float(res_details[0])
                passenger_id = res_details[1]
                instance_id = res_details[2]
                
                # Calculate refund (80% refund if cancelled more than 24 hours before flight)
                cursor.execute("""
                    SELECT Departure_Time FROM Flight_Instance WHERE Instance_ID = :instance_id
                """, instance_id=instance_id)
                departure_time = cursor.fetchone()[0]
                hours_until_flight = (departure_time - datetime.now()).total_seconds() / 3600
                
                refund_eligible = 'Y' if hours_until_flight > 24 else 'N'
                refund_amount = seat_cost * 0.8 if refund_eligible == 'Y' else 0
                total_refund += refund_amount
                
                # Delete reservation
                cursor.execute("""
                    DELETE FROM Reservation 
                    WHERE Reservation_ID = :res_id
                """, res_id=res_id)
                
                # Log cancellation
                cursor.execute("SELECT COUNT(*) FROM Cancellation_Log")
                log_id = cursor.fetchone()[0] + 1
                
                cursor.execute("""
                    INSERT INTO Cancellation_Log 
                    (Log_ID, Booking_ID, Cancel_Date, Reason)
                    VALUES (:log_id, :booking_id, SYSTIMESTAMP, 'Customer initiated cancellation')
                """, log_id=log_id, booking_id=booking_id)
        
        # Update booking status if all reservations are cancelled
        cursor.execute("""
            SELECT COUNT(*) FROM Reservation 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        active_reservations = cursor.fetchone()[0]
        if active_reservations == 0:
            cursor.execute("""
                UPDATE Booking SET Booking_Status = 'CANCELLED' 
                WHERE Booking_ID = :booking_id
            """, booking_id=booking_id)
        
        conn.commit()
        
        # Clear session
        session.pop('selected_reservations', None)
        session.pop('action_booking_id', None)
        session.pop('action_email', None)
        
        return render_template('cancellation_confirmation.html',
                             booking_id=booking_id,
                             cancelled_count=len(reservation_ids),
                             total_refund=total_refund)
        
    except Exception as e:
        conn.rollback()
        print("Error during cancellation:", e)
        return render_template('error.html', error="Cancellation failed")
    finally:
        cursor.close()
        conn.close()


def redirect_to_reschedule(reservation_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get original reservation details for rescheduling
        cursor.execute("""
            SELECT r.Reservation_ID, r.Booking_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
                   fi.Model_ID, fr.Source_Airport, fr.Dest_Airport,
                   fi.Departure_Time, fi.Arrival_Time,
                   a1.Airport_Name as Departure_Airport, a2.Airport_Name as Arrival_Airport,
                   c1.City_Name as Departure_City, c2.City_Name as Arrival_City,
                   arc.Class_ID as Travel_Class
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
            WHERE r.Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        original_flight = cursor.fetchone()
        
        if not original_flight:
            return render_template('error.html', error="Reservation not found")
        
        original_flight_info = {
            'reservation_id': original_flight[0],
            'booking_id': original_flight[1],
            'passenger_id': original_flight[2],
            'instance_id': original_flight[3],
            'row_number': original_flight[4],
            'seat_letter': original_flight[5],
            'price_charged': float(original_flight[6]),
            'passenger_name': f"{original_flight[7]} {original_flight[8]}",
            'title': original_flight[9],
            'nationality': original_flight[10],
            'model_id': original_flight[11],
            'departure_airport_id': original_flight[12],
            'arrival_airport_id': original_flight[13],
            'departure_time': original_flight[14].strftime('%d-%b-%Y %H:%M'),
            'arrival_time': original_flight[15].strftime('%d-%b-%Y %H:%M'),
            'departure_airport': original_flight[16],
            'arrival_airport': original_flight[17],
            'departure_city': original_flight[18],
            'arrival_city': original_flight[19],
            'travel_class': original_flight[20],
            'departure_date': original_flight[14].strftime('%Y-%m-%d')
        }
        
        # Store the original booking ID in session for seat exclusion
        session['reschedule_original_booking'] = original_flight[1]
        
        return render_template('reschedule_flights.html',
                             original_flight=original_flight_info,
                             reservation_id=reservation_id,
                             original_booking_id=original_flight[1],
                             min_date=datetime.now().strftime('%Y-%m-%d'))
        
    except Exception as e:
        print("Error preparing reschedule:", e)
        return render_template('error.html', error="Error preparing reschedule")
    finally:
        cursor.close()
        conn.close()


@management_bp.route('/search-reschedule-flights', methods=['POST'])
def search_reschedule_flights():
    from routes.flights import search_flights
    
    reservation_id = request.form.get('reservation_id')
    original_booking_id = request.form.get('original_booking_id')
    
    # Store reschedule context in session
    session['reschedule_context'] = {
        'reservation_id': reservation_id,
        'original_booking_id': original_booking_id
    }
    
    # Use the existing search_flights logic but with reschedule context
    return search_flights()


@management_bp.route('/select-reschedule-flight/<flight_id>')
def select_reschedule_flight(flight_id):
    # Get reschedule context from session
    reschedule_context = session.get('reschedule_context', {})
    reservation_id = reschedule_context.get('reservation_id')
    original_booking_id = reschedule_context.get('original_booking_id')
    
    if not reservation_id:
        return render_template('error.html', error="Reschedule session expired")
    
    # Store the new flight selection for reschedule
    session['reschedule_new_flight'] = flight_id
    session['reschedule_reservation_id'] = reservation_id
    session['reschedule_original_booking'] = original_booking_id
    
    # Redirect to seat selection for the new flight
    return redirect(url_for('booking.seat_selection'))


@management_bp.route('/booking-actions')
def booking_actions():
    """Route to handle booking actions page"""
    # Get booking info from session
    manage_booking_info = session.get('manage_booking_info', {})
    
    if not manage_booking_info:
        return redirect(url_for('management.manage_bookings'))
    
    email = manage_booking_info.get('email')
    booking_id = manage_booking_info.get('booking_id')
    action_type = manage_booking_info.get('action_type')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get booking info
        cursor.execute("""
            SELECT Booking_ID, Booking_Status, Contact_Email, Emergency_Phone 
            FROM Booking 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        booking = cursor.fetchone()
        if not booking:
            return render_template('error.html', error="Booking not found")
        
        # Get all reservations for this booking
        cursor.execute("""
            SELECT r.Reservation_ID, r.Passenger_ID, r.Instance_ID, r.Row_Number, r.Seat_Letter, r.Price_Charged,
                   p.First_Name, p.Last_Name, p.Title, p.Nationality,
                   fi.Departure_Time, fi.Arrival_Time,
                   a1.Airport_Name as Departure_Airport, a2.Airport_Name as Arrival_Airport,
                   c1.City_Name as Departure_City, c2.City_Name as Arrival_City,
                   arc.Class_ID as Travel_Class
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
            WHERE r.Booking_ID = :booking_id
            ORDER BY fi.Departure_Time
        """, booking_id=booking_id)
        
        reservations = cursor.fetchall()
        
        # Convert to list of dictionaries
        reservation_list = []
        for res in reservations:
            reservation_list.append({
                'reservation_id': res[0],
                'passenger_id': res[1],
                'instance_id': res[2],
                'row_number': res[3],
                'seat_letter': res[4],
                'seat_cost': float(res[5]),
                'passenger_name': f"{res[6]} {res[7]}",
                'title': res[8],
                'nationality': res[9],
                'departure_time': res[10].strftime('%d-%b-%Y %H:%M'),
                'arrival_time': res[11].strftime('%d-%b-%Y %H:%M'),
                'departure_airport': res[12],
                'arrival_airport': res[13],
                'departure_city': res[14],
                'arrival_city': res[15],
                'travel_class': res[16],
                'seat_number': f"{res[3]}{res[4]}"
            })
        
        booking_info = {
            'booking_id': booking[0],
            'booking_status': booking[1],
            'contact_email': booking[2],
            'contact_phone': booking[3]
        }
        
        return render_template('booking_actions.html',
                             booking_info=booking_info,
                             reservations=reservation_list,
                             email=email,
                             action_type=action_type)
        
    except Exception as e:
        print("Error loading booking actions:", e)
        return render_template('error.html', error="Error loading booking details")
    finally:
        cursor.close()
        conn.close()


@management_bp.route('/complete-reschedule', methods=['POST'])
def complete_reschedule():
    """Complete the reschedule process after seat selection"""
    reservation_id = session.get('reschedule_reservation_id')
    new_flight_id = session.get('reschedule_new_flight')
    selected_seats = request.form.getlist('selected_outbound_seats')
    
    if not reservation_id or not new_flight_id or not selected_seats:
        return render_template('error.html', error="Reschedule session expired or no seats selected")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get original reservation details including booking info
        cursor.execute("""
            SELECT r.Booking_ID, r.Passenger_ID, r.Price_Charged, r.Instance_ID,
                   fi.Model_ID as Old_Model_ID, fi.Route_ID as Old_Route_ID,
                   b.Booking_Status
            FROM Reservation r
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            JOIN Booking b ON r.Booking_ID = b.Booking_ID
            WHERE r.Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        original_res = cursor.fetchone()
        if not original_res:
            return render_template('error.html', error="Original reservation not found")
        
        booking_id = original_res[0]
        passenger_id = original_res[1]
        old_price = float(original_res[2])
        old_instance_id = original_res[3]
        old_model_id = original_res[4]
        old_route_id = original_res[5]
        
        # Delete old reservation FIRST to free up the seat
        print(f"DEBUG - Deleting old reservation: {reservation_id}")
        cursor.execute("""
            DELETE FROM Reservation 
            WHERE Reservation_ID = :res_id
        """, res_id=reservation_id)
        
        # COMMIT the deletion immediately to free up the seat
        conn.commit()
        print(f"DEBUG - Old reservation {reservation_id} deleted and committed")
        
        # Now proceed with creating the new reservation
        cursor.execute("""
            SELECT fi.Model_ID, fr.Route_ID 
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            WHERE fi.Instance_ID = :flight_id
        """, flight_id=new_flight_id)
        new_flight_info = cursor.fetchone()
        new_model_id = new_flight_info[0]
        new_route_id = new_flight_info[1]
        
        # Get new seat price using the correct travel class
        cursor.execute("""
            SELECT Base_Price FROM Route_Pricing 
            WHERE Route_ID = :route_id 
            AND Class_ID = :class_id
            AND SYSDATE BETWEEN Valid_From AND Valid_To
        """, route_id=new_route_id, class_id=session.get('travel_class', 'ECO'))
        
        new_price_result = cursor.fetchone()
        new_price = new_price_result[0] if new_price_result else old_price
        
        # Parse new seat information
        new_seat_simple = selected_seats[0]
        row_match = re.search(r'\d+', new_seat_simple)
        letter_match = re.search(r'[A-Z]', new_seat_simple)
        
        if not row_match or not letter_match:
            return render_template('error.html', error="Invalid seat format")
        
        new_row_num = int(row_match.group())
        new_seat_letter = letter_match.group()
        
        # Verify new seat exists
        cursor.execute("""
            SELECT 1 FROM Aircraft_Seat_Map 
            WHERE Model_ID = :model_id 
            AND Row_Number = :row_num 
            AND Seat_Letter = :seat_letter
        """, model_id=new_model_id, row_num=new_row_num, seat_letter=new_seat_letter)
        
        if not cursor.fetchone():
            return render_template('error.html', error="New seat not found in aircraft")
        
        # Check if the new seat is actually available
        cursor.execute("""
            SELECT 1 FROM Reservation 
            WHERE Instance_ID = :instance_id 
            AND Row_Number = :row_num 
            AND Seat_Letter = :seat_letter
        """, instance_id=new_flight_id, row_num=new_row_num, seat_letter=new_seat_letter)
        
        if cursor.fetchone():
            return render_template('error.html', error="Selected seat is no longer available. Please choose a different seat.")
        
        # Calculate price difference and change fee
        price_difference = new_price - old_price
        change_fee = 500  # Fixed change fee
        
        # Generate new reservation ID
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_reservation_id = f"RES{timestamp}"
        
        print(f"DEBUG - Creating new reservation:")
        print(f"  New Reservation: {new_reservation_id}")
        print(f"  Booking ID: {booking_id}")
        print(f"  New Flight: {new_flight_id}")
        print(f"  New Seat: {new_row_num}{new_seat_letter}")
        
        # Create new reservation
        cursor.execute("""
            INSERT INTO Reservation 
            (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged)
            VALUES (:res_id, :booking_id, :passenger_id, :instance_id, :row_num, :seat_letter, :price)
        """, 
        res_id=new_reservation_id,
        booking_id=booking_id,
        passenger_id=passenger_id,
        instance_id=new_flight_id,
        row_num=new_row_num,
        seat_letter=new_seat_letter,
        price=new_price)
        
        print(f"DEBUG - New reservation {new_reservation_id} created for booking {booking_id}")
        
        # Update booking status to CONFIRMED
        cursor.execute("""
            UPDATE Booking SET Booking_Status = 'CONFIRMED' 
            WHERE Booking_ID = :booking_id
        """, booking_id=booking_id)
        
        conn.commit()
        
        print(f"DEBUG - Reschedule completed successfully:")
        print(f"  Booking ID: {booking_id} (UPDATED)")
        print(f"  Old Reservation: {reservation_id} (DELETED)")
        print(f"  New Reservation: {new_reservation_id} (CREATED)")
        
        # Clear ALL session data to prevent stale data
        clear_reschedule_session(session)
        
        return render_template('reschedule_confirmation.html',
                             booking_id=booking_id,
                             new_reservation_id=new_reservation_id,
                             new_flight_id=new_flight_id,
                             price_difference=price_difference,
                             change_fee=change_fee)
        
    except Exception as e:
        conn.rollback()
        print("Error during reschedule:", e)
        print("Error type:", type(e).__name__)
        import traceback
        traceback.print_exc()
        return render_template('error.html', error=f"Reschedule failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()
