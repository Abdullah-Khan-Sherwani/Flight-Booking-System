-- ============================================
-- Flight Management System - Core Tables
-- Schema: flight_admin (in ORCLPDB)
-- ============================================

-- 1. Airport
CREATE TABLE Airport (
    Airport_ID VARCHAR2(10) PRIMARY KEY,
    AirportCity VARCHAR2(50),
    AirportCountry VARCHAR2(50)
);

-- 2. Flight_Details
CREATE TABLE Flight_Details (
    Flight_ID VARCHAR2(10) PRIMARY KEY,
    Source_Airport_ID VARCHAR2(10) REFERENCES Airport(Airport_ID),
    Destination_Airport_ID VARCHAR2(10) REFERENCES Airport(Airport_ID),
    Departure_Date_Time DATE,
    Arrival_Date_Time DATE,
    Airplane_Type VARCHAR2(50)
);

-- 3. Passenger
CREATE TABLE Passenger (
    Passenger_ID VARCHAR2(10) PRIMARY KEY,
    P_FirstName VARCHAR2(50),
    P_LastName VARCHAR2(50),
    P_Email VARCHAR2(100),
    P_PhoneNumber VARCHAR2(20),
    P_Address VARCHAR2(200),
    P_City VARCHAR2(50),
    P_State VARCHAR2(50),
    P_Zipcode VARCHAR2(10),
    P_Country VARCHAR2(50)
);

-- 4. Travel_Class
CREATE TABLE Travel_Class (
    Travel_Class_ID VARCHAR2(10) PRIMARY KEY,
    Travel_Class_Name VARCHAR2(50),
    Travel_Class_Capacity NUMBER
);

-- 5. Seat_Details
CREATE TABLE Seat_Details (
    Seat_ID VARCHAR2(10) PRIMARY KEY,
    Travel_Class_ID VARCHAR2(10) REFERENCES Travel_Class(Travel_Class_ID),
    Flight_ID VARCHAR2(10) REFERENCES Flight_Details(Flight_ID)
);

-- 6. Reservation
CREATE TABLE Reservation (
    Reservation_ID VARCHAR2(10) PRIMARY KEY,
    Passenger_ID VARCHAR2(10) REFERENCES Passenger(Passenger_ID),
    Seat_ID VARCHAR2(10) REFERENCES Seat_Details(Seat_ID),
    Date_Of_Reservation DATE
);

-- 7. Payment_Status
CREATE TABLE Payment_Status (
    Payment_ID VARCHAR2(10) PRIMARY KEY,
    Payment_Status_YN CHAR(1) CHECK (Payment_Status_YN IN ('Y','N')),
    Payment_Due_Date DATE,
    Payment_Amount NUMBER(10,2),
    Reservation_ID VARCHAR2(10) UNIQUE REFERENCES Reservation(Reservation_ID)
);

-- 8. Flight_Service
CREATE TABLE Flight_Service (
    Service_ID VARCHAR2(10) PRIMARY KEY,
    Service_Name VARCHAR2(50)
);

-- 9. Service_Offering
CREATE TABLE Service_Offering (
    Travel_Class_ID VARCHAR2(10) REFERENCES Travel_Class(Travel_Class_ID),
    Service_ID VARCHAR2(10) REFERENCES Flight_Service(Service_ID),
    Offered_YN CHAR(1) CHECK (Offered_YN IN ('Y','N')),
    From_Date DATE,
    To_Date DATE,
    PRIMARY KEY (Travel_Class_ID, Service_ID)
);

-- 10. Flight_Cost
CREATE TABLE Flight_Cost (
    Seat_ID VARCHAR2(10) REFERENCES Seat_Details(Seat_ID),
    Valid_From_Date DATE,
    Valid_To_Date DATE,
    Cost NUMBER(10,2),
    PRIMARY KEY (Seat_ID, Valid_From_Date)
);

ALTER TABLE Seat_Details MODIFY (Seat_ID VARCHAR2(20));


SELECT * FROM AIRPORT;