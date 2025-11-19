-- ============================================
-- 06_CREATE_INDEXES.SQL
-- Flight Booking System - Performance Indexes
-- Optimizes query performance for common lookups
-- ============================================

SET SERVEROUTPUT ON;

BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('CREATING INDEXES');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

-- Booking table indexes
CREATE INDEX idx_booking_lead_cnic ON Booking(Lead_Passenger_CNIC);
CREATE INDEX idx_booking_date ON Booking(Booking_Date);
CREATE INDEX idx_booking_status ON Booking(Booking_Status, Payment_Status);

-- Reservation table indexes
CREATE INDEX idx_reservation_booking ON Reservation(Booking_ID);
CREATE INDEX idx_reservation_passenger ON Reservation(Passenger_CNIC);
CREATE INDEX idx_reservation_flight ON Reservation(Flight_ID);
CREATE INDEX idx_reservation_seat ON Reservation(Seat_ID);
CREATE INDEX idx_reservation_status ON Reservation(Reservation_Status);

-- Cancellation_Log indexes
CREATE INDEX idx_cancellation_booking ON Cancellation_Log(Booking_ID);
CREATE INDEX idx_cancellation_passenger ON Cancellation_Log(Cancelled_By_CNIC);

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ All indexes created successfully');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

COMMIT;
