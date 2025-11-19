-- ============================================
-- 03_CREATE_NEW_SCHEMA.SQL
-- Flight Booking System - Database Migration
-- Creates new CNIC-based schema with Booking table
-- ============================================

SET SERVEROUTPUT ON;

BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('CREATING NEW SCHEMA');
    DBMS_OUTPUT.PUT_LINE('Tables: Passenger, Booking, Reservation,');
    DBMS_OUTPUT.PUT_LINE('        Cancellation_Log, Flight_Change_Log');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

-- ==================
-- PASSENGER TABLE
-- ==================
CREATE TABLE Passenger (
    CNIC VARCHAR2(15) PRIMARY KEY,
    P_FirstName VARCHAR2(50) NOT NULL,
    P_LastName VARCHAR2(50) NOT NULL,
    P_Email VARCHAR2(100),
    P_PhoneNumber VARCHAR2(20),
    P_Address VARCHAR2(200),
    P_City VARCHAR2(50),
    P_State VARCHAR2(50),
    P_Zipcode VARCHAR2(10),
    P_Country VARCHAR2(50),
    Date_Of_Birth DATE,
    Gender CHAR(1) CHECK (Gender IN ('M', 'F', 'O')),
    CONSTRAINT chk_cnic_format CHECK (REGEXP_LIKE(CNIC, '^\d{5}-\d{7}-\d$'))
);

COMMENT ON TABLE Passenger IS 'Stores passenger information with CNIC as primary key';
COMMENT ON COLUMN Passenger.CNIC IS 'Pakistani CNIC format: 12345-1234567-1';

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ Passenger table created');
END;
/

-- ==================
-- BOOKING TABLE
-- ==================
CREATE TABLE Booking (
    Booking_ID VARCHAR2(20) PRIMARY KEY,
    Lead_Passenger_CNIC VARCHAR2(15) NOT NULL REFERENCES Passenger(CNIC),
    Booking_Date TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    Total_Amount NUMBER(10,2) DEFAULT 0 NOT NULL,
    Payment_Status VARCHAR2(20) DEFAULT 'UNPAID' CHECK (Payment_Status IN ('UNPAID', 'PAID', 'CANCELLED')),
    Booking_Status VARCHAR2(20) DEFAULT 'CONFIRMED' CHECK (Booking_Status IN ('CONFIRMED', 'CANCELLED', 'COMPLETED')),
    Pay_Option VARCHAR2(20) CHECK (Pay_Option IN ('PAY_NOW', 'PAY_LATER')),
    Trip_Type VARCHAR2(10) CHECK (Trip_Type IN ('ONE_WAY', 'ROUND_TRIP')),
    Payment_Method VARCHAR2(50),
    Payment_Date TIMESTAMP,
    Cancellation_Date TIMESTAMP,
    Cancellation_Reason VARCHAR2(500)
);

COMMENT ON TABLE Booking IS 'Groups multiple passengers under single booking';
COMMENT ON COLUMN Booking.Lead_Passenger_CNIC IS 'Contact person for the booking';
COMMENT ON COLUMN Booking.Pay_Option IS 'PAY_NOW redirects to payment, PAY_LATER creates UNPAID booking';

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ Booking table created');
END;
/

-- ==================
-- RESERVATION TABLE
-- ==================
CREATE TABLE Reservation (
    Reservation_ID VARCHAR2(20) PRIMARY KEY,
    Booking_ID VARCHAR2(20) NOT NULL REFERENCES Booking(Booking_ID) ON DELETE CASCADE,
    Passenger_CNIC VARCHAR2(15) NOT NULL REFERENCES Passenger(CNIC),
    Seat_ID VARCHAR2(20) NOT NULL REFERENCES Seat_Details(Seat_ID),
    Flight_ID VARCHAR2(10) NOT NULL REFERENCES Flight_Details(Flight_ID),
    Date_Of_Reservation TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    Reservation_Status VARCHAR2(20) DEFAULT 'ACTIVE' CHECK (Reservation_Status IN ('ACTIVE', 'CANCELLED', 'CHANGED')),
    Seat_Cost NUMBER(10,2) NOT NULL,
    Is_Outbound CHAR(1) DEFAULT 'Y' CHECK (Is_Outbound IN ('Y', 'N')),
    CONSTRAINT uq_booking_seat UNIQUE (Booking_ID, Seat_ID)
);

COMMENT ON TABLE Reservation IS 'Links passengers to seats within a booking';
COMMENT ON COLUMN Reservation.Is_Outbound IS 'Y for outbound, N for return flight';
COMMENT ON COLUMN Reservation.Reservation_Status IS 'ACTIVE seats count toward booking total';

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ Reservation table created');
END;
/

-- ==================
-- CANCELLATION_LOG TABLE
-- ==================
CREATE TABLE Cancellation_Log (
    Cancellation_ID VARCHAR2(20) PRIMARY KEY,
    Booking_ID VARCHAR2(20) NOT NULL REFERENCES Booking(Booking_ID),
    Cancellation_Date TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    Cancelled_By_CNIC VARCHAR2(15) NOT NULL REFERENCES Passenger(CNIC),
    Reason VARCHAR2(500),
    Original_Amount NUMBER(10,2),
    Refund_Eligible CHAR(1) DEFAULT 'N' CHECK (Refund_Eligible IN ('Y', 'N')),
    Hours_Since_Booking NUMBER
);

COMMENT ON TABLE Cancellation_Log IS 'Audit trail for booking cancellations';
COMMENT ON COLUMN Cancellation_Log.Refund_Eligible IS 'Y if within 24 hours, N otherwise';

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ Cancellation_Log table created');
END;
/

-- ==================
-- FLIGHT_CHANGE_LOG TABLE
-- ==================
CREATE TABLE Flight_Change_Log (
    Change_ID VARCHAR2(20) PRIMARY KEY,
    Booking_ID VARCHAR2(20) NOT NULL REFERENCES Booking(Booking_ID),
    Change_Date TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    Changed_By_CNIC VARCHAR2(15) NOT NULL REFERENCES Passenger(CNIC),
    Old_Flight_ID VARCHAR2(10),
    New_Flight_ID VARCHAR2(10),
    Old_Seat_ID VARCHAR2(20),
    New_Seat_ID VARCHAR2(20),
    Price_Difference NUMBER(10,2),
    Change_Fee NUMBER(10,2) DEFAULT 0
);

COMMENT ON TABLE Flight_Change_Log IS 'Audit trail for flight/seat changes';
COMMENT ON COLUMN Flight_Change_Log.Change_Fee IS 'Fee for changing (0 if within 24hrs)';

BEGIN
    DBMS_OUTPUT.PUT_LINE('✓ Flight_Change_Log table created');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('✓ All tables created successfully');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

COMMIT;
