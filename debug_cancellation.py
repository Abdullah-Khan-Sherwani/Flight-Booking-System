#!/usr/bin/env python3
"""
Debug cancellation issue with app_user and infant
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN
from datetime import datetime, timedelta

def debug_cancellation():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*80)
        print("DEBUGGING CANCELLATION ISSUE")
        print("="*80)
        
        # Find bookings with app_user and infant
        print("\n1. Finding bookings with app_user and infant passengers...")
        cursor.execute("""
            SELECT DISTINCT b.Booking_ID, b.User_ID, p.Passenger_ID, p.Passenger_Type
            FROM Booking b
            JOIN Reservation r ON b.Booking_ID = r.Booking_ID
            JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
            WHERE p.Passenger_Type = 'INFANT'
            AND rownum <= 5
        """)
        
        bookings = cursor.fetchall()
        if not bookings:
            print("   ✗ No bookings with infants found")
            return
        
        print(f"   ✓ Found {len(bookings)} bookings with infants")
        
        for booking_id, user_id, passenger_id, ptype in bookings:
            print(f"\n   Booking {booking_id} (User {user_id}, Passenger {passenger_id}, Type: {ptype})")
            
            # Get reservations for this booking
            cursor.execute("""
                SELECT Reservation_ID, Passenger_ID, Price_Charged, Instance_ID
                FROM Reservation
                WHERE Booking_ID = :bid
            """, {"bid": booking_id})
            
            reservations = cursor.fetchall()
            print(f"   Reservations in booking: {len(reservations)}")
            
            for res_id, pass_id, price, inst_id in reservations:
                print(f"     - Res {res_id}: Passenger {pass_id}, Price {price}, Instance {inst_id}")
        
        # Try to cancel a reservation with infant
        print("\n2. Testing cancellation of infant reservation...")
        
        test_booking_id, test_user_id, test_pass_id, test_ptype = bookings[0]
        
        # Get first reservation in this booking
        cursor.execute("""
            SELECT Reservation_ID, Instance_ID
            FROM Reservation
            WHERE Booking_ID = :bid
            AND rownum = 1
        """, {"bid": test_booking_id})
        
        result = cursor.fetchone()
        if result:
            test_res_id, test_inst_id = result
            print(f"   Testing with Reservation {test_res_id} from Booking {test_booking_id}")
            
            # Get flight details
            cursor.execute("""
                SELECT Departure_Time FROM Flight_Instance WHERE Instance_ID = :iid
            """, {"iid": test_inst_id})
            
            departure = cursor.fetchone()[0]
            hours_left = (departure - datetime.now()).total_seconds() / 3600
            print(f"   Flight departs in {hours_left:.2f} hours")
            
            # Try to delete the reservation
            print("\n   Attempting DELETE...")
            try:
                cursor.execute("""
                    DELETE FROM Reservation 
                    WHERE Reservation_ID = :res_id
                """, {"res_id": test_res_id})
                
                print(f"   ✓ DELETE succeeded ({cursor.rowcount} rows)")
                
                # Try to commit
                print("   Attempting COMMIT...")
                conn.commit()
                print("   ✓ COMMIT succeeded")
                
            except Exception as del_err:
                print(f"   ✗ DELETE failed: {del_err}")
                conn.rollback()
                
                # Check for constraints
                print("\n3. Checking constraints on Reservation table...")
                cursor.execute("""
                    SELECT constraint_name, constraint_type, table_name
                    FROM user_constraints
                    WHERE table_name = 'RESERVATION'
                """)
                
                for cname, ctype, tname in cursor.fetchall():
                    print(f"   - {cname} ({ctype}) on {tname}")
                
                # Check for foreign keys pointing to Reservation
                print("\n4. Checking foreign keys referencing Reservation...")
                cursor.execute("""
                    SELECT constraint_name, table_name, r_constraint_name
                    FROM user_constraints
                    WHERE r_constraint_name IN (
                        SELECT constraint_name FROM user_constraints WHERE table_name = 'RESERVATION'
                    )
                """)
                
                fks = cursor.fetchall()
                if fks:
                    for cname, tname, r_cname in fks:
                        print(f"   - {cname} on {tname} references {r_cname}")
                else:
                    print("   No foreign keys found")
                
                # Check for triggers on Reservation
                print("\n5. Checking triggers on Reservation table...")
                cursor.execute("""
                    SELECT trigger_name, triggering_event, status
                    FROM user_triggers
                    WHERE table_name = 'RESERVATION'
                """)
                
                triggers = cursor.fetchall()
                if triggers:
                    for tname, event, status in triggers:
                        print(f"   - {tname}: {event} ({status})")
                else:
                    print("   No triggers found")
        
        print("\n" + "="*80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_cancellation()
