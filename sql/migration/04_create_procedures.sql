-- ============================================
-- 04_CREATE_PROCEDURES.SQL
-- Flight Booking System - Stored Procedures
-- CRUD operations for Passenger, Booking, Reservation
-- ============================================

SET SERVEROUTPUT ON;

BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('CREATING STORED PROCEDURES');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

-- ==========================================
-- PASSENGER CRUD PROCEDURES
-- ==========================================

-- CREATE PASSENGER
CREATE OR REPLACE PROCEDURE SP_CREATE_PASSENGER(
    p_cnic IN VARCHAR2,
    p_fname IN VARCHAR2,
    p_lname IN VARCHAR2,
    p_email IN VARCHAR2,
    p_phone IN VARCHAR2,
    p_address IN VARCHAR2 DEFAULT NULL,
    p_city IN VARCHAR2 DEFAULT NULL,
    p_state IN VARCHAR2 DEFAULT NULL,
    p_zipcode IN VARCHAR2 DEFAULT NULL,
    p_country IN VARCHAR2 DEFAULT NULL,
    p_dob IN DATE DEFAULT NULL,
    p_gender IN CHAR DEFAULT NULL
) AS
BEGIN
    INSERT INTO Passenger 
    (CNIC, P_FirstName, P_LastName, P_Email, P_PhoneNumber, P_Address, 
     P_City, P_State, P_Zipcode, P_Country, Date_Of_Birth, Gender)
    VALUES 
    (p_cnic, p_fname, p_lname, p_email, p_phone, p_address,
     p_city, p_state, p_zipcode, p_country, p_dob, p_gender);
    
    COMMIT;
EXCEPTION
    WHEN DUP_VAL_ON_INDEX THEN
        -- CNIC already exists, update instead
        UPDATE Passenger SET
            P_FirstName = p_fname,
            P_LastName = p_lname,
            P_Email = p_email,
            P_PhoneNumber = p_phone,
            P_Address = p_address,
            P_City = p_city,
            P_State = p_state,
            P_Zipcode = p_zipcode,
            P_Country = p_country,
            Date_Of_Birth = p_dob,
            Gender = p_gender
        WHERE CNIC = p_cnic;
        COMMIT;
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20001, 'Error creating passenger: ' || SQLERRM);
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_CREATE_PASSENGER created');
END;
/

-- READ PASSENGER
CREATE OR REPLACE PROCEDURE SP_GET_PASSENGER(
    p_cnic IN VARCHAR2,
    p_cursor OUT SYS_REFCURSOR
) AS
BEGIN
    OPEN p_cursor FOR
    SELECT * FROM Passenger WHERE CNIC = p_cnic;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_GET_PASSENGER created');
END;
/

-- UPDATE PASSENGER
CREATE OR REPLACE PROCEDURE SP_UPDATE_PASSENGER(
    p_cnic IN VARCHAR2,
    p_email IN VARCHAR2 DEFAULT NULL,
    p_phone IN VARCHAR2 DEFAULT NULL,
    p_address IN VARCHAR2 DEFAULT NULL
) AS
BEGIN
    UPDATE Passenger SET
        P_Email = NVL(p_email, P_Email),
        P_PhoneNumber = NVL(p_phone, P_PhoneNumber),
        P_Address = NVL(p_address, P_Address)
    WHERE CNIC = p_cnic;
    
    IF SQL%ROWCOUNT = 0 THEN
        RAISE_APPLICATION_ERROR(-20002, 'Passenger not found');
    END IF;
    
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_UPDATE_PASSENGER created');
END;
/

-- ==========================================
-- BOOKING CRUD PROCEDURES
-- ==========================================

-- CREATE BOOKING
CREATE OR REPLACE PROCEDURE SP_CREATE_BOOKING(
    p_booking_id IN VARCHAR2,
    p_lead_cnic IN VARCHAR2,
    p_total_amount IN NUMBER,
    p_pay_option IN VARCHAR2,
    p_trip_type IN VARCHAR2
) AS
BEGIN
    INSERT INTO Booking 
    (Booking_ID, Lead_Passenger_CNIC, Total_Amount, Pay_Option, Trip_Type, Payment_Status)
    VALUES 
    (p_booking_id, p_lead_cnic, p_total_amount, p_pay_option, p_trip_type, 'UNPAID');
    
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20003, 'Error creating booking: ' || SQLERRM);
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_CREATE_BOOKING created');
END;
/

-- UPDATE PAYMENT STATUS
CREATE OR REPLACE PROCEDURE SP_UPDATE_PAYMENT_STATUS(
    p_booking_id IN VARCHAR2,
    p_payment_status IN VARCHAR2,
    p_payment_method IN VARCHAR2 DEFAULT NULL
) AS
BEGIN
    UPDATE Booking SET
        Payment_Status = p_payment_status,
        Payment_Method = p_payment_method,
        Payment_Date = CASE WHEN p_payment_status = 'PAID' THEN SYSTIMESTAMP ELSE NULL END
    WHERE Booking_ID = p_booking_id;
    
    IF SQL%ROWCOUNT = 0 THEN
        RAISE_APPLICATION_ERROR(-20004, 'Booking not found');
    END IF;
    
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_UPDATE_PAYMENT_STATUS created');
END;
/

-- CANCEL BOOKING
CREATE OR REPLACE PROCEDURE SP_CANCEL_BOOKING(
    p_booking_id IN VARCHAR2,
    p_cnic IN VARCHAR2,
    p_reason IN VARCHAR2,
    p_refund_eligible OUT CHAR
) AS
    v_booking_date TIMESTAMP;
    v_hours_diff NUMBER;
    v_original_amount NUMBER;
    v_payment_status VARCHAR2(20);
    v_cancellation_id VARCHAR2(20);
BEGIN
    -- Get booking details
    SELECT Booking_Date, Total_Amount, Payment_Status 
    INTO v_booking_date, v_original_amount, v_payment_status
    FROM Booking 
    WHERE Booking_ID = p_booking_id;
    
    -- Calculate hours since booking
    v_hours_diff := (SYSTIMESTAMP - v_booking_date) * 24;
    
    -- Determine refund eligibility (24-hour rule)
    IF v_hours_diff <= 24 THEN
        p_refund_eligible := 'Y';
    ELSE
        p_refund_eligible := 'N';
    END IF;
    
    -- Update booking status
    UPDATE Booking SET
        Booking_Status = 'CANCELLED',
        Payment_Status = 'CANCELLED',
        Cancellation_Date = SYSTIMESTAMP,
        Cancellation_Reason = p_reason
    WHERE Booking_ID = p_booking_id;
    
    -- Update all reservations
    UPDATE Reservation SET
        Reservation_Status = 'CANCELLED'
    WHERE Booking_ID = p_booking_id;
    
    -- Log cancellation
    v_cancellation_id := 'CXL' || TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS');
    INSERT INTO Cancellation_Log 
    (Cancellation_ID, Booking_ID, Cancelled_By_CNIC, Reason, 
     Original_Amount, Refund_Eligible, Hours_Since_Booking)
    VALUES 
    (v_cancellation_id, p_booking_id, p_cnic, p_reason,
     v_original_amount, p_refund_eligible, v_hours_diff);
    
    COMMIT;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20005, 'Booking not found');
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_CANCEL_BOOKING created');
END;
/

-- DELETE UNPAID BOOKINGS (User selects from past bookings)
CREATE OR REPLACE PROCEDURE SP_DELETE_UNPAID_BOOKINGS(
    p_cnic IN VARCHAR2,
    p_booking_ids IN VARCHAR2  -- Comma-separated: 'BKG001,BKG002,BKG003'
) AS
    v_booking_id VARCHAR2(20);
    v_payment_status VARCHAR2(20);
    v_pos NUMBER;
    v_ids VARCHAR2(4000);
    v_deleted_count NUMBER := 0;
BEGIN
    v_ids := p_booking_ids || ',';
    
    -- Loop through comma-separated booking IDs
    LOOP
        v_pos := INSTR(v_ids, ',');
        EXIT WHEN v_pos = 0;
        
        v_booking_id := TRIM(SUBSTR(v_ids, 1, v_pos - 1));
        v_ids := SUBSTR(v_ids, v_pos + 1);
        
        IF v_booking_id IS NOT NULL THEN
            -- Check if booking exists and is UNPAID
            BEGIN
                SELECT Payment_Status INTO v_payment_status
                FROM Booking
                WHERE Booking_ID = v_booking_id
                  AND (Lead_Passenger_CNIC = p_cnic 
                       OR Booking_ID IN (SELECT Booking_ID FROM Reservation WHERE Passenger_CNIC = p_cnic));
                
                IF v_payment_status = 'UNPAID' THEN
                    -- Delete booking (CASCADE deletes reservations)
                    DELETE FROM Booking WHERE Booking_ID = v_booking_id;
                    v_deleted_count := v_deleted_count + 1;
                    DBMS_OUTPUT.PUT_LINE('Deleted booking: ' || v_booking_id);
                ELSE
                    DBMS_OUTPUT.PUT_LINE('Skipped ' || v_booking_id || ' (Payment Status: ' || v_payment_status || ')');
                END IF;
            EXCEPTION
                WHEN NO_DATA_FOUND THEN
                    DBMS_OUTPUT.PUT_LINE('Booking ' || v_booking_id || ' not found or not authorized');
            END;
        END IF;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Total bookings deleted: ' || v_deleted_count);
    
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20006, 'Error deleting bookings: ' || SQLERRM);
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_DELETE_UNPAID_BOOKINGS created');
END;
/

-- ==========================================
-- RESERVATION CRUD PROCEDURES
-- ==========================================

-- CREATE RESERVATION
CREATE OR REPLACE PROCEDURE SP_CREATE_RESERVATION(
    p_res_id IN VARCHAR2,
    p_booking_id IN VARCHAR2,
    p_cnic IN VARCHAR2,
    p_seat_id IN VARCHAR2,
    p_flight_id IN VARCHAR2,
    p_seat_cost IN NUMBER,
    p_is_outbound IN CHAR
) AS
BEGIN
    INSERT INTO Reservation
    (Reservation_ID, Booking_ID, Passenger_CNIC, Seat_ID, Flight_ID, Seat_Cost, Is_Outbound)
    VALUES
    (p_res_id, p_booking_id, p_cnic, p_seat_id, p_flight_id, p_seat_cost, p_is_outbound);
    
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20007, 'Error creating reservation: ' || SQLERRM);
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_CREATE_RESERVATION created');
END;
/

-- GET PASSENGER BOOKINGS
CREATE OR REPLACE PROCEDURE SP_GET_PASSENGER_BOOKINGS(
    p_cnic IN VARCHAR2,
    p_cursor OUT SYS_REFCURSOR
) AS
BEGIN
    OPEN p_cursor FOR
    SELECT DISTINCT b.*
    FROM Booking b
    LEFT JOIN Reservation r ON b.Booking_ID = r.Booking_ID
    WHERE b.Lead_Passenger_CNIC = p_cnic
       OR r.Passenger_CNIC = p_cnic
    ORDER BY b.Booking_Date DESC;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ SP_GET_PASSENGER_BOOKINGS created');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('✓ All stored procedures created successfully');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

COMMIT;
