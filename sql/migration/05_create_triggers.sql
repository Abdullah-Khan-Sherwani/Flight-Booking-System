-- ============================================
-- 05_CREATE_TRIGGERS.SQL
-- Flight Booking System - Database Triggers
-- Business rule enforcement and automation
-- ============================================

SET SERVEROUTPUT ON;

BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('CREATING TRIGGERS');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

-- ==========================================
-- VALIDATION TRIGGERS
-- ==========================================

-- CNIC Format Validation
CREATE OR REPLACE TRIGGER TRG_VALIDATE_CNIC_FORMAT
BEFORE INSERT OR UPDATE ON Passenger
FOR EACH ROW
BEGIN
    IF NOT REGEXP_LIKE(:NEW.CNIC, '^\d{5}-\d{7}-\d$') THEN
        RAISE_APPLICATION_ERROR(-20010, 
            'Invalid CNIC format. Must be: 12345-1234567-1');
    END IF;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ TRG_VALIDATE_CNIC_FORMAT created');
END;
/

-- ==========================================
-- BUSINESS RULE TRIGGERS
-- ==========================================

-- Prevent Double Booking
CREATE OR REPLACE TRIGGER TRG_PREVENT_DOUBLE_BOOKING
BEFORE INSERT ON Reservation
FOR EACH ROW
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM Reservation
    WHERE Seat_ID = :NEW.Seat_ID
      AND Reservation_Status = 'ACTIVE';
    
    IF v_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20011, 
            'Seat already booked. Please select a different seat.');
    END IF;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ TRG_PREVENT_DOUBLE_BOOKING created');
END;
/

-- Auto-Update Booking Total Amount
CREATE OR REPLACE TRIGGER TRG_UPDATE_BOOKING_TOTAL
AFTER INSERT OR UPDATE OR DELETE ON Reservation
FOR EACH ROW
DECLARE
    v_booking_id VARCHAR2(20);
    v_total NUMBER;
BEGIN
    -- Get booking_id from inserted, updated, or deleted row
    IF INSERTING OR UPDATING THEN
        v_booking_id := :NEW.Booking_ID;
    ELSE
        v_booking_id := :OLD.Booking_ID;
    END IF;
    
    -- Calculate total from active reservations
    SELECT NVL(SUM(Seat_Cost), 0) INTO v_total
    FROM Reservation
    WHERE Booking_ID = v_booking_id
      AND Reservation_Status = 'ACTIVE';
    
    -- Update booking total
    UPDATE Booking
    SET Total_Amount = v_total
    WHERE Booking_ID = v_booking_id;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ TRG_UPDATE_BOOKING_TOTAL created');
END;
/

-- ==========================================
-- AUTO-ID GENERATION TRIGGERS
-- ==========================================

-- Auto-Generate Booking ID
CREATE OR REPLACE TRIGGER TRG_AUTO_BOOKING_ID
BEFORE INSERT ON Booking
FOR EACH ROW
BEGIN
    IF :NEW.Booking_ID IS NULL THEN
        :NEW.Booking_ID := 'BKG' || TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS');
    END IF;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ TRG_AUTO_BOOKING_ID created');
END;
/

-- Auto-Generate Reservation ID
CREATE OR REPLACE TRIGGER TRG_AUTO_RESERVATION_ID
BEFORE INSERT ON Reservation
FOR EACH ROW
BEGIN
    IF :NEW.Reservation_ID IS NULL THEN
        :NEW.Reservation_ID := 'RES' || TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS');
    END IF;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ TRG_AUTO_RESERVATION_ID created');
END;
/

-- Auto-Generate Cancellation ID
CREATE OR REPLACE TRIGGER TRG_AUTO_CANCELLATION_ID
BEFORE INSERT ON Cancellation_Log
FOR EACH ROW
BEGIN
    IF :NEW.Cancellation_ID IS NULL THEN
        :NEW.Cancellation_ID := 'CXL' || TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS');
    END IF;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ TRG_AUTO_CANCELLATION_ID created');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('✓ All triggers created successfully');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

-- Verify Triggers
BEGIN
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('TRIGGER VERIFICATION:');
END;
/

SELECT trigger_name, status, triggering_event, table_name
FROM user_triggers
WHERE trigger_name LIKE 'TRG_%'
ORDER BY table_name, trigger_name;

COMMIT;
