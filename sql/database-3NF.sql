-- Drop existing user objects (excluding system-generated sequences)
BEGIN
    FOR t IN (SELECT table_name FROM user_tables) LOOP
        EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS';
    END LOOP;
END;
/

BEGIN
    FOR s IN (SELECT sequence_name FROM user_sequences WHERE sequence_name NOT LIKE '%$%') LOOP
        EXECUTE IMMEDIATE 'DROP SEQUENCE ' || s.sequence_name;
    END LOOP;
END;
/

BEGIN
    FOR trg IN (SELECT trigger_name FROM user_triggers) LOOP
        EXECUTE IMMEDIATE 'DROP TRIGGER ' || trg.trigger_name;
    END LOOP;
END;
/

--------------------------------------------------------------------------------
-- 1. GEOGRAPHIC & AIRPORT MASTER DATA
--------------------------------------------------------------------------------
CREATE TABLE Country (
    Country_ID    NUMBER PRIMARY KEY,
    Country_Name  VARCHAR2(50) NOT NULL UNIQUE
);

CREATE TABLE State_Province (
    State_ID      NUMBER PRIMARY KEY,
    State_Name    VARCHAR2(50) NOT NULL,
    Country_ID    NUMBER NOT NULL REFERENCES Country(Country_ID),
    CONSTRAINT UQ_State_Country UNIQUE (State_Name, Country_ID)
);

CREATE TABLE City (
    City_ID       NUMBER PRIMARY KEY,
    City_Name     VARCHAR2(50) NOT NULL,
    State_ID      NUMBER NOT NULL REFERENCES State_Province(State_ID),
    CONSTRAINT UQ_City_State UNIQUE (City_Name, State_ID)
);

CREATE TABLE Zip_Master (
    Zipcode       VARCHAR2(10) PRIMARY KEY,
    City_ID       NUMBER NOT NULL REFERENCES City(City_ID)
);

CREATE TABLE Airport (
    Airport_ID    VARCHAR2(10) PRIMARY KEY, -- IATA Code (e.g., JFK)
    Airport_Name  VARCHAR2(100) NOT NULL,
    Zipcode       VARCHAR2(10) REFERENCES Zip_Master(Zipcode)
);

--------------------------------------------------------------------------------
-- 2. AIRCRAFT & SEAT CONFIGURATION
--------------------------------------------------------------------------------
CREATE TABLE Aircraft_Model (
    Model_ID      VARCHAR2(20) PRIMARY KEY, -- e.g., B737-800
    Model_Name    VARCHAR2(100) NOT NULL,
    Manufacturer  VARCHAR2(50)
);

CREATE TABLE Travel_Class (
    Class_ID      VARCHAR2(10) PRIMARY KEY, -- e.g., ECO, BUS
    Class_Name    VARCHAR2(50) NOT NULL
);

-- Intersect Table: Defines which rows belong to which class on a specific plane
CREATE TABLE Aircraft_Row_Class (
    Model_ID      VARCHAR2(20) NOT NULL REFERENCES Aircraft_Model(Model_ID),
    Row_Number    NUMBER NOT NULL,
    Class_ID      VARCHAR2(10) NOT NULL REFERENCES Travel_Class(Class_ID),
    CONSTRAINT PK_Row_Class PRIMARY KEY (Model_ID, Row_Number),
    CONSTRAINT CK_Row_Pos CHECK (Row_Number > 0)
);

-- Detail Table: Specific seats (A, B, C) in a row
CREATE TABLE Aircraft_Seat_Map (
    Model_ID      VARCHAR2(20) NOT NULL,
    Row_Number    NUMBER NOT NULL,
    Seat_Letter   CHAR(1) NOT NULL,
    CONSTRAINT PK_Seat_Map PRIMARY KEY (Model_ID, Row_Number, Seat_Letter),
    CONSTRAINT FK_Seat_Row FOREIGN KEY (Model_ID, Row_Number)
        REFERENCES Aircraft_Row_Class(Model_ID, Row_Number)
);

--------------------------------------------------------------------------------
-- 3. FLIGHT OPERATIONS & PRICING
--------------------------------------------------------------------------------
CREATE TABLE Flight_Route (
    Route_ID       VARCHAR2(10) PRIMARY KEY,
    Source_Airport VARCHAR2(10) NOT NULL REFERENCES Airport(Airport_ID),
    Dest_Airport   VARCHAR2(10) NOT NULL REFERENCES Airport(Airport_ID),
    Base_Duration  NUMBER, -- Minutes
    CONSTRAINT CK_Diff_Airports CHECK (Source_Airport <> Dest_Airport)
);

--------------------------------------------------------------------------------
-- 4. SERVICES & OFFERINGS
--------------------------------------------------------------------------------
CREATE TABLE Flight_Service (
    Service_ID    VARCHAR2(10) PRIMARY KEY, -- e.g., WIFI
    Service_Name  VARCHAR2(50) NOT NULL
);

-- Logic: Services are defined by the ROUTE and CLASS.
CREATE TABLE Service_Offering (
    Route_ID         VARCHAR2(10) NOT NULL REFERENCES Flight_Route(Route_ID),
    Class_ID         VARCHAR2(10) NOT NULL REFERENCES Travel_Class(Class_ID),
    Service_ID       VARCHAR2(10) NOT NULL REFERENCES Flight_Service(Service_ID),
    
    -- Temporal Validity (Service availability changes over time)
    Valid_From       DATE NOT NULL,
    Valid_To         DATE, -- Nullable means "Indefinitely valid"
    
    Is_Complimentary CHAR(1) DEFAULT 'Y' CHECK (Is_Complimentary IN ('Y', 'N')),
    Cost_If_Paid     NUMBER(10, 2) DEFAULT 0 CHECK (Cost_If_Paid >= 0),
    
    -- PRIMARY KEY MUST INCLUDE Valid_From to allow historical records
    CONSTRAINT PK_Route_Service PRIMARY KEY (Route_ID, Class_ID, Service_ID, Valid_From),
    
    -- Logical Rule: End date must be after start date
    CONSTRAINT CK_Service_Dates CHECK (Valid_To IS NULL OR Valid_To >= Valid_From)
);

CREATE TABLE Route_Pricing (
    Pricing_ID     NUMBER PRIMARY KEY,
    Route_ID       VARCHAR2(10) NOT NULL REFERENCES Flight_Route(Route_ID),
    Class_ID       VARCHAR2(10) NOT NULL REFERENCES Travel_Class(Class_ID),
    Valid_From     DATE NOT NULL,
    Valid_To       DATE NOT NULL,
    Base_Price     NUMBER(10, 2) NOT NULL CHECK (Base_Price >= 0),
    CONSTRAINT CK_Pricing_Dates CHECK (Valid_To >= Valid_From)
);

CREATE TABLE Flight_Instance (
    Instance_ID    VARCHAR2(20) PRIMARY KEY, -- e.g., FL101-20241010
    Route_ID       VARCHAR2(10) NOT NULL REFERENCES Flight_Route(Route_ID),
    Model_ID       VARCHAR2(20) NOT NULL REFERENCES Aircraft_Model(Model_ID),
    Departure_Time TIMESTAMP NOT NULL,
    Arrival_Time   TIMESTAMP NOT NULL,
    Flight_Status  VARCHAR2(20) DEFAULT 'SCHEDULED' 
                   CHECK (Flight_Status IN ('SCHEDULED','DELAYED','CANCELLED','LANDED')),
    Price_Multiplier NUMBER(3,2) DEFAULT 1.00, -- Per-flight pricing adjustment (e.g., 1.25 = 25% more expensive)
    CONSTRAINT CK_Arrival_After_Dep CHECK (Arrival_Time > Departure_Time),
    CONSTRAINT CK_Price_Multiplier CHECK (Price_Multiplier > 0)
);

-- APP USER (The Account Holder)
-- This table handles authentication and login sessions.
-- It is distinct from the Passenger table (Physical Traveler).
CREATE TABLE App_User (
    User_ID        NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    Email          VARCHAR2(100) NOT NULL UNIQUE, -- Serves as the Login ID
    Password_Hash  VARCHAR2(256) NOT NULL,        -- Security best practice: Store hash, not text
    Phone_Number   VARCHAR2(20),
    Created_At     TIMESTAMP DEFAULT SYSTIMESTAMP,
    
    -- Basic email validation check
    CONSTRAINT CK_User_Email CHECK (Email LIKE '%@%.%')
);

--------------------------------------------------------------------------------
-- 5. BOOKING & PNR SYSTEM
--------------------------------------------------------------------------------

-- BOOKING (The Transaction)
-- Represents the financial "Folder" or PNR containing the trip details.
CREATE TABLE Booking (
    Booking_ID       VARCHAR2(6) PRIMARY KEY, -- The PNR (e.g., 'A7F3E9')
    
    -- THE FINANCIAL OWNER (Lead User):
    -- This is who logged in to make the booking.
    -- Even if they aren't flying, they own the record.
    Lead_User_ID     NUMBER REFERENCES App_User(User_ID) ON DELETE SET NULL,
    
    Booking_Date     TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    Booking_Status   VARCHAR2(20) DEFAULT 'CONFIRMED' 
                     CHECK (Booking_Status IN ('CONFIRMED','CANCELLED','COMPLETED')),
    
    -- Contact details specific to THIS trip (in case User profile email is old)
    Contact_Email    VARCHAR2(100) NOT NULL,
    Emergency_Phone  VARCHAR2(20)
);


-- PASSENGER (The Person Profile)
-- This represents a human being. It is NOT a snapshot per flight.
-- It is a reusable profile linked to an App_User (if they have an account).
CREATE SEQUENCE Passenger_Seq START WITH 1 INCREMENT BY 1;

-- RESERVATION ID SEQUENCE
-- Generates unique ticket numbers in airline format: IAT-YYYYMMDD-NNNNNN
-- IAT = IAT Airlines code, YYYYMMDD = date, NNNNNN = 6-digit sequential number
CREATE SEQUENCE Reservation_Seq START WITH 100001 INCREMENT BY 1 MAXVALUE 999999 CYCLE NOCACHE;

-- BOOKING ID SEQUENCE
-- Generates sequential booking IDs (PNRs) in deterministic format
-- Used by Generate_PNR function for guaranteed unique booking IDs
CREATE SEQUENCE Booking_Seq START WITH 1 INCREMENT BY 1 MAXVALUE 999999 CYCLE NOCACHE;

CREATE TABLE Passenger (
    Passenger_ID   NUMBER DEFAULT Passenger_Seq.NEXTVAL PRIMARY KEY,
    
    -- THE CRITICAL LINK:
    -- If NULL: This is a Guest/Child/Dependent without their own account.
    -- If NOT NULL: This passenger IS that App_User.
    -- UNIQUE ensures one User cannot have multiple "Self" profiles.
    Linked_User_ID NUMBER UNIQUE REFERENCES App_User(User_ID) ON DELETE SET NULL,
    
    -- Core Demographics
    Title          VARCHAR2(10) CHECK (Title IN ('MR', 'MS', 'MRS', 'DR', 'MX', 'CHD', 'INF')),
    First_Name     VARCHAR2(50) NOT NULL,
    Last_Name      VARCHAR2(50) NOT NULL,
    Gender         VARCHAR2(20) CHECK (Gender IN ('MALE', 'FEMALE', 'OTHER')),
    Date_Of_Birth  DATE NOT NULL,
    
    -- Passport Logic: 
    -- Unique ensures we don't accidentally create duplicate profiles for the same person.
    -- LIKELY NOT NEEDED
    Passport_Num   VARCHAR2(20)
);

--------------------------------------------------------------------------------
-- 6. RESERVATION & TRANSACTIONS
--------------------------------------------------------------------------------

-- RESERVATION (The Junction / Ticket)
-- Connects a Person (Passenger) to a Trip (Instance) within a Folder (Booking).
CREATE TABLE Reservation (
    Reservation_ID VARCHAR2(20) PRIMARY KEY, -- Ticket Number
    
    -- Relationships
    Booking_ID     VARCHAR2(6) NOT NULL REFERENCES Booking(Booking_ID),
    Passenger_ID   NUMBER NOT NULL REFERENCES Passenger(Passenger_ID),
    Instance_ID    VARCHAR2(20) NOT NULL REFERENCES Flight_Instance(Instance_ID),
    
    -- Seat Assignment
    -- NULL = Infant (On Lap) or Pending Assignment.
    Row_Number     NUMBER,
    Seat_Letter    CHAR(1),
    Price_Charged  NUMBER(10, 2) NOT NULL CHECK (Price_Charged >= 0),
    
    -- Passenger Type for THIS reservation (determines pricing and seat rules)
    -- ADULT: Regular passenger, requires seat, full price
    -- LAP_INFANT: Infant on adult's lap, no seat, FREE
    -- SEATED_INFANT: Extra infant needing own seat, 50% price
    Passenger_Type VARCHAR2(20) DEFAULT 'ADULT'
                   CHECK (Passenger_Type IN ('ADULT', 'LAP_INFANT', 'SEATED_INFANT')),
    
    Ticket_Status  VARCHAR2(20) DEFAULT 'ISSUED'
                   CHECK (Ticket_Status IN ('ISSUED', 'CHECKED_IN', 'BOARDED', 'NO_SHOW', 'CANCELLED')),

    -- LOGICAL RULES:
    -- Unique Constraint handles NULLs intelligently in Oracle.
    -- It prevents two people from having "Row 10, Seat A".
    -- But it allows multiple Infants to have "NULL, NULL" (because NULL != NULL).

    -- 1. No Double Booking: A seat on a specific flight can only be held once.
    CONSTRAINT UQ_Seat_Instance UNIQUE (Instance_ID, Row_Number, Seat_Letter),
    
    -- 2. No Duplicate Traveler: The same person cannot be on the same flight twice.
    CONSTRAINT UQ_Pass_Instance UNIQUE (Passenger_ID, Instance_ID)
);

CREATE TABLE Payment (
    Payment_ID     VARCHAR2(20) PRIMARY KEY,
    Booking_ID     VARCHAR2(6) NOT NULL REFERENCES Booking(Booking_ID),
    Amount_Paid    NUMBER(10, 2) NOT NULL CHECK (Amount_Paid >= 0),
    Payment_Date   TIMESTAMP DEFAULT SYSTIMESTAMP,
    Payment_Method VARCHAR2(50)
);

CREATE TABLE Cancellation_Log (
    Log_ID         NUMBER PRIMARY KEY,
    Booking_ID     VARCHAR2(6) NOT NULL REFERENCES Booking(Booking_ID),
    Cancel_Date    TIMESTAMP DEFAULT SYSTIMESTAMP,
    Reason         VARCHAR2(255)
);

--------------------------------------------------------------------------------
-- 7. BUSINESS LOGIC (Triggers)
--------------------------------------------------------------------------------

-- A. PNR Generator (Random 6-character Alphanumeric String)
CREATE OR REPLACE FUNCTION Generate_PNR RETURN VARCHAR2 IS
    v_pnr VARCHAR2(6);
    v_count NUMBER;
    c_chars CONSTANT VARCHAR2(36) := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
BEGIN
    LOOP
        v_pnr := '';
        FOR i IN 1..6 LOOP
            v_pnr := v_pnr || SUBSTR(c_chars, ROUND(DBMS_RANDOM.VALUE(1, 36)), 1);
        END LOOP;
        SELECT COUNT(*) INTO v_count FROM Booking WHERE Booking_ID = v_pnr;
        EXIT WHEN v_count = 0;
    END LOOP;
    RETURN v_pnr;
END;
/

CREATE OR REPLACE TRIGGER TRG_Generate_Booking_PNR
BEFORE INSERT ON Booking
FOR EACH ROW
BEGIN
    IF :NEW.Booking_ID IS NULL THEN
        :NEW.Booking_ID := Generate_PNR();
    END IF;
END;
/

-- B. Ghost Seat Prevention (Verify seat exists on the specific Aircraft Model)
-- Supports NULL seats for infants (on lap)
CREATE OR REPLACE TRIGGER TRG_Validate_Seat_Exists
BEFORE INSERT OR UPDATE ON Reservation
FOR EACH ROW
DECLARE
    v_Model_ID VARCHAR2(20);
    v_Count    NUMBER;
BEGIN
    -- 1. If it's an Infant (NULL seat), skip validation. It's always valid.
    IF :NEW.Row_Number IS NULL THEN
        RETURN;
    END IF;

    -- 2. Find out which Aircraft Model is being used for this Flight Instance
    SELECT Model_ID INTO v_Model_ID
    FROM Flight_Instance
    WHERE Instance_ID = :NEW.Instance_ID;

    -- 3. Check if the requested Seat exists in the Seat Map for that Model
    SELECT COUNT(*) INTO v_Count
    FROM Aircraft_Seat_Map
    WHERE Model_ID = v_Model_ID
      AND Row_Number = :NEW.Row_Number
      AND Seat_Letter = :NEW.Seat_Letter;

    -- 4. If count is 0, the seat does not exist physically. REJECT IT.
    IF v_Count = 0 THEN
        RAISE_APPLICATION_ERROR(-20010, 
            'Invalid Seat Selection: Row ' || :NEW.Row_Number || 
            ' Seat ' || :NEW.Seat_Letter || 
            ' does not exist on aircraft ' || v_Model_ID);
    END IF;
END;
/

-- Keeping Counts (For Display): Do NOT add a column like Seats_Remaining to the Flight_Instance table. That violates 3NF (because it is a calculated value derived from other tables). If you store it, it will eventually get out of sync.

-- Instead, create a VIEW. This acts like a virtual table that calculates availability live.
CREATE OR REPLACE VIEW View_Flight_Availability AS
SELECT 
    F.Instance_ID,
    F.Route_ID,
    F.Departure_Time,
    
    -- 1. Get Total Capacity (Count seats in the aircraft model)
    (SELECT COUNT(*) FROM Aircraft_Seat_Map WHERE Model_ID = F.Model_ID) AS Total_Capacity,
    
    -- 2. Get Booked Seats (Count rows in Reservation where seat is not null)
    (SELECT COUNT(*) FROM Reservation WHERE Instance_ID = F.Instance_ID AND Row_Number IS NOT NULL) AS Seats_Booked,
    
    -- 3. Calculate Remaining
    (SELECT COUNT(*) FROM Aircraft_Seat_Map WHERE Model_ID = F.Model_ID) - 
    (SELECT COUNT(*) FROM Reservation WHERE Instance_ID = F.Instance_ID AND Row_Number IS NOT NULL) AS Seats_Remaining

FROM Flight_Instance F;

-- 2. Handling Skipped Seat Selection (The "Random" Solution)
-- Should you assign a random seat? YES. If an adult passenger skips selection, you should auto-assign a seat immediately. Leaving it NULL (Pending) creates operational headaches later (e.g., overbooking, family separation at the gate).

-- How to implement this: Do not do this in your Java/Python code. It is too slow. Use a PL/SQL Procedure.

-- This procedure represents the "Smart Booking Logic." It says: "If they picked a seat, try to give it to them. If they didn't, find a random empty one."
CREATE OR REPLACE PROCEDURE USP_Make_Reservation (
    p_Booking_ID   IN VARCHAR2,
    p_Passenger_ID IN NUMBER,
    p_Instance_ID  IN VARCHAR2,
    p_Req_Row      IN NUMBER DEFAULT NULL,   -- User's choice (Optional)
    p_Req_Seat     IN CHAR DEFAULT NULL      -- User's choice (Optional)
) AS
    v_Final_Row  NUMBER;
    v_Final_Seat CHAR(1);
    v_Title      VARCHAR2(10);
BEGIN
    -- 1. Check if Passenger is an Infant (Infants MUST be NULL/Lap)
    SELECT Title INTO v_Title FROM Passenger WHERE Passenger_ID = p_Passenger_ID;
    
    IF v_Title IN ('INF', 'CHD') THEN
        v_Final_Row := NULL;
        v_Final_Seat := NULL;
        
    -- 2. If User SELECTED a seat manually
    ELSIF p_Req_Row IS NOT NULL AND p_Req_Seat IS NOT NULL THEN
        v_Final_Row := p_Req_Row;
        v_Final_Seat := p_Req_Seat;
        
    -- 3. If User SKIPPED SELECTION (Auto-Assign Random)
    ELSE
        BEGIN
            SELECT Row_Number, Seat_Letter
            INTO v_Final_Row, v_Final_Seat
            FROM (
                -- A. Get ALL seats on this plane model
                SELECT S.Row_Number, S.Seat_Letter
                FROM Flight_Instance F
                JOIN Aircraft_Seat_Map S ON F.Model_ID = S.Model_ID
                WHERE F.Instance_ID = p_Instance_ID
                
                MINUS -- B. Subtract seats ALREADY BOOKED on this flight
                
                SELECT Row_Number, Seat_Letter
                FROM Reservation
                WHERE Instance_ID = p_Instance_ID
                  AND Row_Number IS NOT NULL
            )
            -- C. Randomize and pick the first one
            ORDER BY DBMS_RANDOM.VALUE
            FETCH FIRST 1 ROW ONLY;
            
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE_APPLICATION_ERROR(-20020, 'Flight is fully booked! Cannot auto-assign.');
        END;
    END IF;

    -- 4. Insert the Reservation
    INSERT INTO Reservation (
        Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, 
        Row_Number, Seat_Letter, Price_Charged, Ticket_Status
    ) VALUES (
        'IAT-' || TO_CHAR(SYSDATE, 'YYYYMMDD') || '-' || LPAD(Reservation_Seq.NEXTVAL, 6, '0'),
        p_Booking_ID, p_Passenger_ID, p_Instance_ID, 
        v_Final_Row, v_Final_Seat, 150.00, 'ISSUED'
    );

    COMMIT;
END;
/

--------------------------------------------------------------------------------
-- C. INFANT BOOKING RULES (Business Logic Triggers)
--------------------------------------------------------------------------------

-- Trigger: Validate and Enforce Infant Booking Rules
-- Rules:
-- 1. LAP_INFANT must have NULL seat and Price_Charged = 0 (FREE)
-- 2. SEATED_INFANT must have a seat and Price_Charged = 50% of base
-- 3. ADULT must have a seat (or auto-assign)
-- 4. Only passengers with Title='INF' can be LAP_INFANT or SEATED_INFANT

CREATE OR REPLACE TRIGGER TRG_Infant_Booking_Rules
BEFORE INSERT OR UPDATE ON Reservation
FOR EACH ROW
DECLARE
    v_Title VARCHAR2(10);
    v_Route_ID VARCHAR2(10);
    v_Class_ID VARCHAR2(10);
    v_Base_Price NUMBER(10,2);
BEGIN
    -- Get passenger title
    SELECT Title INTO v_Title 
    FROM Passenger 
    WHERE Passenger_ID = :NEW.Passenger_ID;
    
    -- RULE 1: Only infants can be LAP_INFANT or SEATED_INFANT
    IF :NEW.Passenger_Type IN ('LAP_INFANT', 'SEATED_INFANT') AND v_Title != 'INF' THEN
        RAISE_APPLICATION_ERROR(-20030, 
            'Only passengers with Title INF can have Passenger_Type of LAP_INFANT or SEATED_INFANT');
    END IF;
    
    -- RULE 2: Infants (Title=INF) must have appropriate Passenger_Type
    IF v_Title = 'INF' AND :NEW.Passenger_Type = 'ADULT' THEN
        RAISE_APPLICATION_ERROR(-20031, 
            'Infant passengers must have Passenger_Type of LAP_INFANT or SEATED_INFANT, not ADULT');
    END IF;
    
    -- RULE 3: LAP_INFANT must have NULL seat
    IF :NEW.Passenger_Type = 'LAP_INFANT' AND :NEW.Row_Number IS NOT NULL THEN
        RAISE_APPLICATION_ERROR(-20032, 
            'Lap infants cannot have a seat assigned. Set Row_Number and Seat_Letter to NULL.');
    END IF;
    
    -- RULE 4: LAP_INFANT must be FREE (Price_Charged = 0) - AUTO-CORRECT
    IF :NEW.Passenger_Type = 'LAP_INFANT' THEN
        :NEW.Price_Charged := 0;
    END IF;
    
    -- RULE 5: SEATED_INFANT must have a seat
    IF :NEW.Passenger_Type = 'SEATED_INFANT' AND :NEW.Row_Number IS NULL THEN
        RAISE_APPLICATION_ERROR(-20033, 
            'Seated infants must have a seat assigned. Please select a seat.');
    END IF;
    
    -- RULE 6: SEATED_INFANT price = 50% of base price - AUTO-CALCULATE
    IF :NEW.Passenger_Type = 'SEATED_INFANT' AND :NEW.Row_Number IS NOT NULL THEN
        BEGIN
            -- Get route from flight instance
            SELECT fr.Route_ID INTO v_Route_ID
            FROM Flight_Instance fi
            JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
            WHERE fi.Instance_ID = :NEW.Instance_ID;
            
            -- Get class from seat row
            SELECT arc.Class_ID INTO v_Class_ID
            FROM Flight_Instance fi
            JOIN Aircraft_Row_Class arc ON fi.Model_ID = arc.Model_ID AND arc.Row_Number = :NEW.Row_Number
            WHERE fi.Instance_ID = :NEW.Instance_ID;
            
            -- Get base price and set to 50%
            SELECT Base_Price INTO v_Base_Price
            FROM Route_Pricing
            WHERE Route_ID = v_Route_ID 
            AND Class_ID = v_Class_ID
            AND SYSDATE BETWEEN Valid_From AND Valid_To
            AND ROWNUM = 1;
            
            :NEW.Price_Charged := v_Base_Price * 0.5;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                NULL; -- Keep app-provided price if pricing not found
        END;
    END IF;
END;
/

-- Function: Calculate Infant Type based on booking context
-- Returns 'LAP_INFANT' if this infant qualifies for lap (free), 'SEATED_INFANT' otherwise
CREATE OR REPLACE FUNCTION FN_Get_Infant_Type(
    p_Booking_ID   IN VARCHAR2,
    p_Instance_ID  IN VARCHAR2,
    p_Passenger_ID IN NUMBER
) RETURN VARCHAR2 IS
    v_Adult_Count NUMBER;
    v_Lap_Infant_Count NUMBER;
    v_Title VARCHAR2(10);
BEGIN
    -- Check if passenger is actually an infant
    SELECT Title INTO v_Title FROM Passenger WHERE Passenger_ID = p_Passenger_ID;
    IF v_Title != 'INF' THEN
        RETURN 'ADULT';
    END IF;
    
    -- Count adults in this booking for this flight
    SELECT COUNT(*) INTO v_Adult_Count
    FROM Reservation r
    JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
    WHERE r.Booking_ID = p_Booking_ID
    AND r.Instance_ID = p_Instance_ID
    AND p.Title NOT IN ('INF', 'CHD')
    AND r.Passenger_Type = 'ADULT';
    
    -- Count existing lap infants in this booking for this flight
    SELECT COUNT(*) INTO v_Lap_Infant_Count
    FROM Reservation r
    WHERE r.Booking_ID = p_Booking_ID
    AND r.Instance_ID = p_Instance_ID
    AND r.Passenger_Type = 'LAP_INFANT';
    
    -- If we have room for another lap infant (1 per adult), return LAP_INFANT
    IF v_Lap_Infant_Count < v_Adult_Count THEN
        RETURN 'LAP_INFANT';
    ELSE
        RETURN 'SEATED_INFANT';
    END IF;
END;
/

-- Function: Get infant price based on type
-- LAP_INFANT = 0 (FREE)
-- SEATED_INFANT = 50% of base price
CREATE OR REPLACE FUNCTION FN_Get_Infant_Price(
    p_Instance_ID  IN VARCHAR2,
    p_Infant_Type  IN VARCHAR2,
    p_Class_ID     IN VARCHAR2 DEFAULT 'ECO'
) RETURN NUMBER IS
    v_Base_Price NUMBER(10,2);
    v_Route_ID VARCHAR2(10);
BEGIN
    -- LAP_INFANT is always FREE
    IF p_Infant_Type = 'LAP_INFANT' THEN
        RETURN 0;
    END IF;
    
    -- For SEATED_INFANT, calculate 50% of base price
    IF p_Infant_Type = 'SEATED_INFANT' THEN
        SELECT fr.Route_ID INTO v_Route_ID
        FROM Flight_Instance fi
        JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
        WHERE fi.Instance_ID = p_Instance_ID;
        
        SELECT Base_Price INTO v_Base_Price
        FROM Route_Pricing
        WHERE Route_ID = v_Route_ID 
        AND Class_ID = p_Class_ID
        AND SYSDATE BETWEEN Valid_From AND Valid_To
        AND ROWNUM = 1;
        
        RETURN v_Base_Price * 0.5;
    END IF;
    
    -- Default: return 0
    RETURN 0;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RETURN 0;
END;
/

-- View: Booking summary with infant breakdown
CREATE OR REPLACE VIEW View_Booking_Infant_Summary AS
SELECT 
    b.Booking_ID,
    b.Contact_Email,
    fi.Instance_ID,
    COUNT(CASE WHEN r.Passenger_Type = 'ADULT' THEN 1 END) AS Adult_Count,
    COUNT(CASE WHEN r.Passenger_Type = 'LAP_INFANT' THEN 1 END) AS Lap_Infant_Count,
    COUNT(CASE WHEN r.Passenger_Type = 'SEATED_INFANT' THEN 1 END) AS Seated_Infant_Count,
    SUM(r.Price_Charged) AS Total_Price,
    SUM(CASE WHEN r.Passenger_Type = 'LAP_INFANT' THEN 0 ELSE r.Price_Charged END) AS Paid_Amount
FROM Booking b
JOIN Reservation r ON b.Booking_ID = r.Booking_ID
JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
GROUP BY b.Booking_ID, b.Contact_Email, fi.Instance_ID;

--------------------------------------------------------------------------------
-- 8. PAST PASSENGERS VIEW (Read-Only)
-- Returns passengers previously booked by a lead user with trip history.
-- Used by "Add from past bookings" feature.
-- 
-- IMPORTANT: When querying this view, the application should filter:
--   WHERE Lead_User_ID = :current_user_id
--     AND (Linked_User_ID IS NULL OR Linked_User_ID != :current_user_id)
-- 
-- This ensures:
-- 1. Only passengers the current user has booked appear
-- 2. The user's OWN passenger profile (Linked_User_ID = user) is excluded
--    (Use "Add Myself" button instead)
--------------------------------------------------------------------------------
CREATE OR REPLACE VIEW View_Past_Passengers AS
SELECT 
    -- Passenger details
    p.Passenger_ID,
    p.Linked_User_ID,
    p.Title,
    p.First_Name,
    p.Last_Name,
    p.Gender,
    p.Date_Of_Birth,
    p.Passport_Num,
    CASE WHEN p.Linked_User_ID IS NOT NULL THEN 'Y' ELSE 'N' END AS Is_Registered_User,
    
    -- Booking context (who booked this passenger)
    b.Lead_User_ID,
    b.Booking_ID,
    b.Booking_Date,
    
    -- Reservation details
    r.Reservation_ID,
    r.Row_Number,
    r.Seat_Letter,
    r.Price_Charged,
    r.Ticket_Status,
    r.Passenger_Type,
    
    -- Flight details
    fi.Instance_ID,
    fi.Departure_Time,
    fi.Arrival_Time,
    
    -- Route info (airport codes)
    fr.Source_Airport,
    fr.Dest_Airport,
    
    -- Airport names for display
    dep_apt.Airport_Name AS Departure_Airport_Name,
    arr_apt.Airport_Name AS Arrival_Airport_Name
    
FROM Passenger p
JOIN Reservation r ON p.Passenger_ID = r.Passenger_ID
JOIN Booking b ON r.Booking_ID = b.Booking_ID
JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
JOIN Airport dep_apt ON fr.Source_Airport = dep_apt.Airport_ID
JOIN Airport arr_apt ON fr.Dest_Airport = arr_apt.Airport_ID
WHERE b.Lead_User_ID IS NOT NULL;  -- Only bookings by logged-in users

--------------------------------------------------------------------------------
-- 9. FAMILY RELATIONSHIP TABLE
-- Enables users to add other registered users as family members.
-- 
-- KEY DESIGN DECISIONS (3NF Compliant):
-- - Only stores User IDs and relationship metadata
-- - NO duplication of user names, emails, or other App_User attributes
-- - Composite PK: (User_ID, Family_User_ID) 
-- - All non-key attributes are fully functionally dependent on the key
-- - Symmetric relationships: when accepted, two rows are inserted
--   (A → B and B → A) for efficient querying
--------------------------------------------------------------------------------
CREATE TABLE User_Family (
    User_ID        NUMBER NOT NULL,
    Family_User_ID NUMBER NOT NULL,
    Relationship   VARCHAR2(30),   -- e.g., 'SPOUSE', 'CHILD', 'PARENT', 'SIBLING', 'OTHER'
    Status         VARCHAR2(20) DEFAULT 'PENDING' NOT NULL
                   CHECK (Status IN ('PENDING', 'ACCEPTED', 'REJECTED')),
    Created_At     TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    
    CONSTRAINT PK_User_Family PRIMARY KEY (User_ID, Family_User_ID),
    CONSTRAINT FK_User_Family_User 
        FOREIGN KEY (User_ID) REFERENCES App_User(User_ID) ON DELETE CASCADE,
    CONSTRAINT FK_User_Family_Family_User 
        FOREIGN KEY (Family_User_ID) REFERENCES App_User(User_ID) ON DELETE CASCADE,
    CONSTRAINT CK_User_Family_No_Self 
        CHECK (User_ID != Family_User_ID)
);

-- Index for efficient lookup of family requests for a user
CREATE INDEX IDX_User_Family_Family_User ON User_Family(Family_User_ID, Status);

--------------------------------------------------------------------------------
-- 10. ACCOUNT DELETION PROCEDURE (Cascading Delete)
-- Deletes an App_User and all related data in the correct order.
-- 
-- This procedure performs a COMPLETE CASCADING DELETE:
-- 1. Payments for user's bookings
-- 2. Cancellation logs for user's bookings
-- 3. Reservations for user's bookings
-- 4. User's Bookings (as Lead_User)
-- 5. User's Family relationships
-- 6. User's Passenger profile (if exists)
-- 7. The App_User account itself
--
-- IMPORTANT: This is IRREVERSIBLE. All booking history is permanently lost.
--------------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE USP_Delete_User_Account (
    p_User_ID IN NUMBER,
    p_Rows_Deleted OUT NUMBER
) AS
    v_Passenger_ID NUMBER;
    v_Total_Deleted NUMBER := 0;
    v_Count NUMBER;
BEGIN
    -- 0. Verify user exists
    SELECT COUNT(*) INTO v_Count FROM App_User WHERE User_ID = p_User_ID;
    IF v_Count = 0 THEN
        RAISE_APPLICATION_ERROR(-20100, 'User account not found');
    END IF;
    
    -- 1. Delete Payments for all bookings made by this user
    DELETE FROM Payment 
    WHERE Booking_ID IN (SELECT Booking_ID FROM Booking WHERE Lead_User_ID = p_User_ID);
    v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
    
    -- 2. Delete Cancellation_Log entries for user's bookings
    DELETE FROM Cancellation_Log 
    WHERE Booking_ID IN (SELECT Booking_ID FROM Booking WHERE Lead_User_ID = p_User_ID);
    v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
    
    -- 3. Delete all Reservations for user's bookings
    DELETE FROM Reservation 
    WHERE Booking_ID IN (SELECT Booking_ID FROM Booking WHERE Lead_User_ID = p_User_ID);
    v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
    
    -- 4. Delete all Bookings made by this user
    DELETE FROM Booking WHERE Lead_User_ID = p_User_ID;
    v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
    
    -- 5. Delete all family relationships (both directions)
    DELETE FROM User_Family WHERE User_ID = p_User_ID OR Family_User_ID = p_User_ID;
    v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
    
    -- 6. Get and delete user's Passenger profile (if linked)
    BEGIN
        SELECT Passenger_ID INTO v_Passenger_ID 
        FROM Passenger 
        WHERE Linked_User_ID = p_User_ID;
        
        -- Delete any orphaned reservations for this passenger 
        -- (reservations made by OTHER users for this passenger)
        DELETE FROM Reservation WHERE Passenger_ID = v_Passenger_ID;
        v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
        
        -- Delete the passenger profile
        DELETE FROM Passenger WHERE Passenger_ID = v_Passenger_ID;
        v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            NULL; -- User has no passenger profile, that's OK
    END;
    
    -- 7. Finally, delete the App_User account
    DELETE FROM App_User WHERE User_ID = p_User_ID;
    v_Total_Deleted := v_Total_Deleted + SQL%ROWCOUNT;
    
    -- Return total rows deleted
    p_Rows_Deleted := v_Total_Deleted;
    
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

--------------------------------------------------------------------------------
-- 11. RESERVATION CANCELLATION PROCEDURE (UPDATED)
-- Cancels a reservation and calculates refund based on departure-time policy.
-- Works in harmony with triggers:
-- - TRG_Auto_Cancel_Booking: Automatically updates Booking.Booking_Status
-- - TRG_Auto_Log_Booking_Cancellation: Automatically logs to Cancellation_Log
-- 
-- CANCELLATION POLICY (via FN_Calculate_Refund):
-- - More than 24 hours before departure: 80% refund
-- - 24 hours or less before departure: 0% refund
-- 
-- This procedure:
-- 1. Validates reservation exists and is not already cancelled
-- 2. Calculates refund using FN_Calculate_Refund (departure-based)
-- 3. Updates reservation status to CANCELLED and frees seat
-- 4. Triggers handle booking status update and logging automatically
--------------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE USP_Cancel_Reservation (
    p_Reservation_ID IN VARCHAR2,
    p_Refund_Amount OUT NUMBER,
    p_Success OUT NUMBER
) AS
    v_Instance_ID VARCHAR2(8);
    v_Price_Charged NUMBER(10,2);
    v_Ticket_Status VARCHAR2(20);
BEGIN
    -- Initialize output parameters
    p_Success := 0;
    p_Refund_Amount := 0;
    
    -- 1. Get reservation details
    BEGIN
        SELECT Instance_ID, Price_Charged, Ticket_Status
        INTO v_Instance_ID, v_Price_Charged, v_Ticket_Status
        FROM Reservation
        WHERE Reservation_ID = p_Reservation_ID;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20200, 'Reservation not found: ' || p_Reservation_ID);
    END;
    
    -- 2. Check if already cancelled
    IF v_Ticket_Status = 'CANCELLED' THEN
        RAISE_APPLICATION_ERROR(-20201, 'Reservation already cancelled');
    END IF;
    
    -- 3. Calculate refund using FN_Calculate_Refund (departure-based policy)
    p_Refund_Amount := FN_Calculate_Refund(v_Instance_ID, v_Price_Charged);
    
    -- 4. Update reservation - this triggers TRG_Auto_Cancel_Booking
    --    which handles booking status and logging automatically
    UPDATE Reservation
    SET Ticket_Status = 'CANCELLED',
        Row_Number = NULL,
        Seat_Letter = NULL
    WHERE Reservation_ID = p_Reservation_ID;
    
    -- 5. Success - caller controls commit/rollback
    p_Success := 1;
    
EXCEPTION
    WHEN OTHERS THEN
        p_Success := 0;
        RAISE;
END;
/

--------------------------------------------------------------------------------
-- 12. ADDITIONAL BUSINESS LOGIC TRIGGERS
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
-- A. AUTO-CANCEL BOOKING TRIGGER
-- When all reservations in a booking have Ticket_Status = 'CANCELLED',
-- automatically update Booking.Booking_Status to 'CANCELLED'.
-- This eliminates the need for manual booking status updates in application code.
--------------------------------------------------------------------------------
CREATE OR REPLACE TRIGGER TRG_Auto_Cancel_Booking
AFTER UPDATE OF Ticket_Status ON Reservation
FOR EACH ROW
WHEN (NEW.Ticket_Status = 'CANCELLED')
DECLARE
    v_Booking_ID VARCHAR2(6);
    v_Total_Reservations NUMBER;
    v_Cancelled_Reservations NUMBER;
BEGIN
    v_Booking_ID := :NEW.Booking_ID;
    
    -- Count total reservations in this booking
    SELECT COUNT(*) INTO v_Total_Reservations
    FROM Reservation
    WHERE Booking_ID = v_Booking_ID;
    
    -- Count cancelled reservations in this booking
    SELECT COUNT(*) INTO v_Cancelled_Reservations
    FROM Reservation
    WHERE Booking_ID = v_Booking_ID
    AND Ticket_Status = 'CANCELLED';
    
    -- If all reservations are cancelled, update booking status
    IF v_Total_Reservations = v_Cancelled_Reservations THEN
        UPDATE Booking
        SET Booking_Status = 'CANCELLED'
        WHERE Booking_ID = v_Booking_ID
        AND Booking_Status != 'CANCELLED';  -- Avoid redundant updates
    END IF;
END;
/

--------------------------------------------------------------------------------
-- B. AUTO-LOG BOOKING CANCELLATION TRIGGER
-- When Booking.Booking_Status changes to 'CANCELLED', automatically insert
-- a record into Cancellation_Log. This is BOOKING-LEVEL logging only.
-- Fires only when the entire booking is cancelled (not per-reservation).
--------------------------------------------------------------------------------
CREATE OR REPLACE TRIGGER TRG_Auto_Log_Booking_Cancellation
AFTER UPDATE OF Booking_Status ON Booking
FOR EACH ROW
WHEN (NEW.Booking_Status = 'CANCELLED' AND OLD.Booking_Status != 'CANCELLED')
DECLARE
    v_Log_ID NUMBER;
BEGIN
    -- Get next Log_ID
    SELECT NVL(MAX(Log_ID), 0) + 1 INTO v_Log_ID FROM Cancellation_Log;
    
    -- Insert cancellation log entry
    INSERT INTO Cancellation_Log (Log_ID, Booking_ID, Cancel_Date, Reason)
    VALUES (v_Log_ID, :NEW.Booking_ID, SYSTIMESTAMP, 'Booking cancelled - all reservations cancelled');
END;
/

--------------------------------------------------------------------------------
-- C. REFUND CALCULATION FUNCTION
-- Calculates refund amount based on hours until departure (NOT hours since booking).
-- 
-- REFUND POLICY (Departure-Based - Customer Friendly):
-- - More than 24 hours before departure: 80% refund
-- - 24 hours or less before departure: 0% refund (no refund)
-- 
-- Parameters:
--   p_Instance_ID: The flight instance to check departure time
--   p_Price_Charged: The original ticket price
-- Returns:
--   The refund amount (0 to 80% of price)
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION FN_Calculate_Refund(
    p_Instance_ID  IN VARCHAR2,
    p_Price_Charged IN NUMBER
) RETURN NUMBER IS
    v_Departure_Time TIMESTAMP;
    v_Hours_Until_Departure NUMBER;
    v_Refund_Amount NUMBER(10,2);
BEGIN
    -- Get departure time for this flight instance
    SELECT Departure_Time INTO v_Departure_Time
    FROM Flight_Instance
    WHERE Instance_ID = p_Instance_ID;
    
    -- Calculate hours until departure
    v_Hours_Until_Departure := (CAST(v_Departure_Time AS DATE) - CAST(SYSTIMESTAMP AS DATE)) * 24;
    
    -- Apply refund policy
    IF v_Hours_Until_Departure > 24 THEN
        v_Refund_Amount := p_Price_Charged * 0.80;  -- 80% refund if >24h before departure
    ELSE
        v_Refund_Amount := 0;  -- No refund if <=24h before departure
    END IF;
    
    RETURN v_Refund_Amount;
    
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RETURN 0;  -- Flight not found, no refund
    WHEN OTHERS THEN
        RETURN 0;  -- Any error, no refund
END;
/

--------------------------------------------------------------------------------
-- D. AUTO-RECIPROCAL FAMILY RELATIONSHIP TRIGGER
-- When a User_Family request Status changes to 'ACCEPTED', automatically
-- create the symmetric/reciprocal relationship (B -> A) if it doesn't exist,
-- or update it to 'ACCEPTED' if it already exists.
-- 
-- This eliminates manual reciprocal handling in application code.
--------------------------------------------------------------------------------
CREATE OR REPLACE TRIGGER TRG_Auto_Reciprocal_Family
AFTER UPDATE OF Status ON User_Family
FOR EACH ROW
WHEN (NEW.Status = 'ACCEPTED' AND OLD.Status = 'PENDING')
DECLARE
    v_Exists NUMBER;
BEGIN
    -- Check if reciprocal relationship already exists
    SELECT COUNT(*) INTO v_Exists
    FROM User_Family
    WHERE User_ID = :NEW.Family_User_ID
    AND Family_User_ID = :NEW.User_ID;
    
    IF v_Exists = 0 THEN
        -- Insert new reciprocal relationship
        INSERT INTO User_Family (User_ID, Family_User_ID, Relationship, Status, Created_At)
        VALUES (:NEW.Family_User_ID, :NEW.User_ID, :NEW.Relationship, 'ACCEPTED', SYSTIMESTAMP);
    ELSE
        -- Update existing reciprocal relationship to ACCEPTED
        UPDATE User_Family
        SET Status = 'ACCEPTED', Relationship = :NEW.Relationship
        WHERE User_ID = :NEW.Family_User_ID
        AND Family_User_ID = :NEW.User_ID
        AND Status != 'ACCEPTED';  -- Avoid redundant updates
    END IF;
END;
/