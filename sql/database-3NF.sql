-- ============================================
-- UNIFIED FLIGHT BOOKING SYSTEM - 3NF SCHEMA
-- (Oracle / ORCLPDB)
-- ============================================

-- If needed, you can fix the schema:
-- ALTER SESSION SET CURRENT_SCHEMA = flight_admin;

------------------------------------------------
-- 0. (OPTIONAL) DROP OLD TABLES IN SAFE ORDER
------------------------------------------------
 DROP TABLE Flight_Change_Log CASCADE CONSTRAINTS;
 DROP TABLE Cancellation_Log CASCADE CONSTRAINTS;
 DROP TABLE Payment CASCADE CONSTRAINTS;
 DROP TABLE Reservation CASCADE CONSTRAINTS;
 DROP TABLE Booking CASCADE CONSTRAINTS;
 DROP TABLE Flight_Cost CASCADE CONSTRAINTS;
 DROP TABLE Service_Offering CASCADE CONSTRAINTS;
 DROP TABLE Flight_Service CASCADE CONSTRAINTS;
 DROP TABLE Seat_Details CASCADE CONSTRAINTS;
 DROP TABLE Travel_Class CASCADE CONSTRAINTS;
 DROP TABLE Flight_Details CASCADE CONSTRAINTS;
 DROP TABLE Airport CASCADE CONSTRAINTS;
 DROP TABLE Passenger CASCADE CONSTRAINTS;


------------------------------------------------
-- 1. AIRPORT
------------------------------------------------
CREATE TABLE Airport (
    Airport_ID      VARCHAR2(10)  PRIMARY KEY,
    AirportCity     VARCHAR2(50)  NOT NULL,
    AirportCountry  VARCHAR2(50)  NOT NULL
);

COMMENT ON TABLE Airport IS 'Master data for airports';
COMMENT ON COLUMN Airport.Airport_ID IS 'Surrogate code for airport (e.g., LHE, DXB)';


------------------------------------------------
-- 2. FLIGHT_DETAILS
------------------------------------------------
CREATE TABLE Flight_Details (
    Flight_ID              VARCHAR2(10)  PRIMARY KEY,
    Source_Airport_ID      VARCHAR2(10)  NOT NULL
        REFERENCES Airport(Airport_ID),
    Destination_Airport_ID VARCHAR2(10)  NOT NULL
        REFERENCES Airport(Airport_ID),
    Departure_Date_Time    DATE          NOT NULL,
    Arrival_Date_Time      DATE          NOT NULL,
    Airplane_Type          VARCHAR2(50)
);

COMMENT ON TABLE Flight_Details IS 'Individual flight legs between two airports';


------------------------------------------------
-- 3. TRAVEL_CLASS
------------------------------------------------
CREATE TABLE Travel_Class (
    Travel_Class_ID       VARCHAR2(10)  PRIMARY KEY,
    Travel_Class_Name     VARCHAR2(50)  NOT NULL,
    Travel_Class_Capacity NUMBER        NOT NULL
);

COMMENT ON TABLE Travel_Class IS 'Different cabin classes (Economy, Business, etc.)';


------------------------------------------------
-- 4. SEAT_DETAILS
--    Seat is specific to (Flight, Row, Seat Letter, Class)
------------------------------------------------
CREATE TABLE Seat_Details (
    Seat_ID         VARCHAR2(20)  PRIMARY KEY,
    Travel_Class_ID VARCHAR2(10)  NOT NULL
        REFERENCES Travel_Class(Travel_Class_ID),
    Flight_ID       VARCHAR2(10)  NOT NULL
        REFERENCES Flight_Details(Flight_ID),
    Row_Number      NUMBER        NOT NULL,   -- 1..N
    Seat_Letter     CHAR(1)       NOT NULL    -- A..F
);

-- Avoid duplicate seats within same flight
ALTER TABLE Seat_Details
    ADD CONSTRAINT UQ_Flight_Row_Seat
        UNIQUE (Flight_ID, Row_Number, Seat_Letter);

COMMENT ON TABLE Seat_Details IS 'Physical seats on a specific flight, by row and seat letter';


------------------------------------------------
-- 5. FLIGHT_SERVICE (EX: MEAL, WIFI, BAGGAGE)
------------------------------------------------
CREATE TABLE Flight_Service (
    Service_ID   VARCHAR2(10)  PRIMARY KEY,
    Service_Name VARCHAR2(50)  NOT NULL
);

COMMENT ON TABLE Flight_Service IS 'Catalog of services that can be offered in a class';


------------------------------------------------
-- 6. SERVICE_OFFERING (WHICH CLASS OFFERS WHICH SERVICE, AND WHEN)
------------------------------------------------
CREATE TABLE Service_Offering (
    Travel_Class_ID VARCHAR2(10) NOT NULL
        REFERENCES Travel_Class(Travel_Class_ID),
    Service_ID      VARCHAR2(10) NOT NULL
        REFERENCES Flight_Service(Service_ID),
    Offered_YN      CHAR(1)      NOT NULL
        CHECK (Offered_YN IN ('Y','N')),
    From_Date       DATE         NOT NULL,
    To_Date         DATE,
    CONSTRAINT PK_Service_Offering PRIMARY KEY (Travel_Class_ID, Service_ID, From_Date)
);

COMMENT ON TABLE Service_Offering IS 'Time-bound mapping of which services are offered in which class';


------------------------------------------------
-- 7. FLIGHT_COST (TIME-DEPENDENT SEAT PRICING)
------------------------------------------------
CREATE TABLE Flight_Cost (
    Seat_ID         VARCHAR2(20) NOT NULL
        REFERENCES Seat_Details(Seat_ID),
    Valid_From_Date DATE         NOT NULL,
    Valid_To_Date   DATE,
    Cost            NUMBER(10,2) NOT NULL,
    CONSTRAINT PK_Flight_Cost PRIMARY KEY (Seat_ID, Valid_From_Date)
);

COMMENT ON TABLE Flight_Cost IS 'Historical cost of a seat over date ranges';


------------------------------------------------
-- 8. PASSENGER (CNIC-BASED, FROM NEW DESIGN)
------------------------------------------------
CREATE TABLE Passenger (
    CNIC           VARCHAR2(15)  PRIMARY KEY,
    P_FirstName    VARCHAR2(50)  NOT NULL,
    P_LastName     VARCHAR2(50)  NOT NULL,
    P_Email        VARCHAR2(100),
    P_PhoneNumber  VARCHAR2(20),
    P_Address      VARCHAR2(200),
    P_City         VARCHAR2(50),
    P_State        VARCHAR2(50),
    P_Zipcode      VARCHAR2(10),
    P_Country      VARCHAR2(50),
    Date_Of_Birth  DATE,
    Gender         CHAR(1)       CHECK (Gender IN ('M', 'F', 'O')),
    CONSTRAINT chk_cnic_format
        CHECK (REGEXP_LIKE(CNIC, '^\d{5}-\d{7}-\d$'))
);

COMMENT ON TABLE Passenger IS 'Stores passenger information with CNIC as primary key';
COMMENT ON COLUMN Passenger.CNIC IS 'Pakistani CNIC format: 12345-1234567-1';


------------------------------------------------
-- 9. BOOKING (TOP-LEVEL PNR / ORDER)
------------------------------------------------
CREATE TABLE Booking (
    Booking_ID           VARCHAR2(20)  PRIMARY KEY,
    Lead_Passenger_CNIC  VARCHAR2(15)  NOT NULL
        REFERENCES Passenger(CNIC),
    Booking_Date         TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
    Total_Amount         NUMBER(10,2)  DEFAULT 0 NOT NULL,
    Booking_Status       VARCHAR2(20)  DEFAULT 'CONFIRMED'
        CHECK (Booking_Status IN ('CONFIRMED', 'CANCELLED', 'COMPLETED')),
    Pay_Option           VARCHAR2(20)
        CHECK (Pay_Option IN ('PAY_NOW', 'PAY_LATER')),
    Trip_Type            VARCHAR2(10)
        CHECK (Trip_Type IN ('ONE_WAY', 'ROUND_TRIP'))
);

COMMENT ON TABLE Booking IS 'Groups multiple passengers and flights into one booking (PNR)';
COMMENT ON COLUMN Booking.Lead_Passenger_CNIC IS 'Main contact / owner of booking';


------------------------------------------------
-- 10. PAYMENT (NORMALIZED OUT OF BOOKING / OLD PAYMENT_STATUS)
------------------------------------------------
CREATE TABLE Payment (
    Payment_ID      VARCHAR2(20) PRIMARY KEY,
    Booking_ID      VARCHAR2(20) NOT NULL
        REFERENCES Booking(Booking_ID) ON DELETE CASCADE,
    Payment_Amount  NUMBER(10,2) NOT NULL,
    Payment_Due_Date DATE,
    Payment_Status  VARCHAR2(20) NOT NULL
        CHECK (Payment_Status IN ('UNPAID','PAID','REFUNDED','CANCELLED')),
    Payment_Method  VARCHAR2(50),
    Payment_Date    TIMESTAMP
);

COMMENT ON TABLE Payment IS 'Payment records for bookings (can support partial/multiple payments)';


------------------------------------------------
-- 11. RESERVATION (PASSENGER x SEAT UNDER A BOOKING)
--     NOTE: Flight_ID is NOT stored here to avoid redundancy;
--           it can be derived via Seat_Details -> Flight_Details.
------------------------------------------------
CREATE TABLE Reservation (
    Reservation_ID      VARCHAR2(20) PRIMARY KEY,
    Booking_ID          VARCHAR2(20) NOT NULL
        REFERENCES Booking(Booking_ID) ON DELETE CASCADE,
    Passenger_CNIC      VARCHAR2(15) NOT NULL
        REFERENCES Passenger(CNIC),
    Seat_ID             VARCHAR2(20) NOT NULL
        REFERENCES Seat_Details(Seat_ID),
    Date_Of_Reservation TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
    Reservation_Status  VARCHAR2(20)  DEFAULT 'ACTIVE'
        CHECK (Reservation_Status IN ('ACTIVE', 'CANCELLED', 'CHANGED')),
    Seat_Cost           NUMBER(10,2)  NOT NULL,
    Is_Outbound         CHAR(1)       DEFAULT 'Y'
        CHECK (Is_Outbound IN ('Y','N')),
    CONSTRAINT uq_booking_seat UNIQUE (Booking_ID, Seat_ID)
);

COMMENT ON TABLE Reservation IS 'One passenger on one seat, belonging to a booking';
COMMENT ON COLUMN Reservation.Is_Outbound IS 'Y = outbound leg, N = return leg';


------------------------------------------------
-- 12. CANCELLATION_LOG (AUDIT FOR CANCELLATIONS)
------------------------------------------------
CREATE TABLE Cancellation_Log (
    Cancellation_ID     VARCHAR2(20) PRIMARY KEY,
    Booking_ID          VARCHAR2(20) NOT NULL
        REFERENCES Booking(Booking_ID),
    Cancellation_Date   TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
    Cancelled_By_CNIC   VARCHAR2(15)  NOT NULL
        REFERENCES Passenger(CNIC),
    Reason              VARCHAR2(500),
    Original_Amount     NUMBER(10,2),
    Refund_Eligible     CHAR(1)       DEFAULT 'N'
        CHECK (Refund_Eligible IN ('Y','N')),
    Hours_Since_Booking NUMBER
);

COMMENT ON TABLE Cancellation_Log IS 'Audit trail for booking cancellations';


------------------------------------------------
-- 13. FLIGHT_CHANGE_LOG (AUDIT FOR CHANGES)
--     We log seat changes; flight can be derived via Seat_Details.
------------------------------------------------
CREATE TABLE Flight_Change_Log (
    Change_ID        VARCHAR2(20) PRIMARY KEY,
    Booking_ID       VARCHAR2(20) NOT NULL
        REFERENCES Booking(Booking_ID),
    Change_Date      TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
    Changed_By_CNIC  VARCHAR2(15) NOT NULL
        REFERENCES Passenger(CNIC),
    Old_Seat_ID      VARCHAR2(20),
    New_Seat_ID      VARCHAR2(20),
    Price_Difference NUMBER(10,2),
    Change_Fee       NUMBER(10,2) DEFAULT 0
);

COMMENT ON TABLE Flight_Change_Log IS 'Audit trail for seat changes within a booking';


------------------------------------------------
-- 14. FINAL MESSAGE
------------------------------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('Unified 3NF schema created successfully');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

COMMIT;