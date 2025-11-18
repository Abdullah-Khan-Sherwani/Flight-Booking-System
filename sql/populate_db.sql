-- complete_populate_db_realistic_prices.sql
-- IAT Airlines Database Population Script - REALISTIC PAKISTANI PRICING

SET SERVEROUTPUT ON;
SET VERIFY OFF;

BEGIN
    DBMS_OUTPUT.PUT_LINE('=========================================');
    DBMS_OUTPUT.PUT_LINE('IAT Airlines Database Population - REALISTIC PRICES');
    DBMS_OUTPUT.PUT_LINE('Creating flights with realistic Pakistani pricing');
    DBMS_OUTPUT.PUT_LINE('Starting at: ' || TO_CHAR(SYSTIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'));
    DBMS_OUTPUT.PUT_LINE('=========================================');
END;
/

-- -----------------------------
-- 1. DELETE EXISTING DATA
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Clearing existing data...');
    
    EXECUTE IMMEDIATE 'DELETE FROM Flight_Cost';
    EXECUTE IMMEDIATE 'DELETE FROM Payment_Status';
    EXECUTE IMMEDIATE 'DELETE FROM Reservation';
    EXECUTE IMMEDIATE 'DELETE FROM Seat_Details';
    EXECUTE IMMEDIATE 'DELETE FROM Service_Offering';
    EXECUTE IMMEDIATE 'DELETE FROM Passenger';
    EXECUTE IMMEDIATE 'DELETE FROM Flight_Details';
    EXECUTE IMMEDIATE 'DELETE FROM Flight_Service';
    EXECUTE IMMEDIATE 'DELETE FROM Travel_Class';
    EXECUTE IMMEDIATE 'DELETE FROM Airport';
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ All existing data deleted successfully');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Error during deletion: ' || SQLERRM);
        ROLLBACK;
        RAISE;
END;
/

-- -----------------------------
-- 2. POPULATE AIRPORTS
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Populating airports...');
    
    INSERT INTO Airport (Airport_ID, AirportCity, AirportCountry) VALUES ('KHI', 'Karachi', 'Pakistan');
    INSERT INTO Airport (Airport_ID, AirportCity, AirportCountry) VALUES ('LHE', 'Lahore', 'Pakistan');
    INSERT INTO Airport (Airport_ID, AirportCity, AirportCountry) VALUES ('ISB', 'Islamabad', 'Pakistan');
    INSERT INTO Airport (Airport_ID, AirportCity, AirportCountry) VALUES ('PEW', 'Peshawar', 'Pakistan');
    INSERT INTO Airport (Airport_ID, AirportCity, AirportCountry) VALUES ('UET', 'Quetta', 'Pakistan');
    INSERT INTO Airport (Airport_ID, AirportCity, AirportCountry) VALUES ('MUX', 'Multan', 'Pakistan');
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Airports populated: 6 airports added');
END;
/

-- -----------------------------
-- 3. POPULATE TRAVEL CLASSES
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Populating travel classes...');
    
    INSERT INTO Travel_Class (Travel_Class_ID, Travel_Class_Name, Travel_Class_Capacity) VALUES ('ECO', 'Economy', 150);
    INSERT INTO Travel_Class (Travel_Class_ID, Travel_Class_Name, Travel_Class_Capacity) VALUES ('BUS', 'Business', 50);
    INSERT INTO Travel_Class (Travel_Class_ID, Travel_Class_Name, Travel_Class_Capacity) VALUES ('FIR', 'First', 20);
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Travel classes populated');
END;
/

-- -----------------------------
-- 4. POPULATE FLIGHT SERVICES
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Populating flight services...');
    
    INSERT INTO Flight_Service (Service_ID, Service_Name) VALUES ('MEAL', 'Meal');
    INSERT INTO Flight_Service (Service_ID, Service_Name) VALUES ('WIFI', 'Wi-Fi');
    INSERT INTO Flight_Service (Service_ID, Service_Name) VALUES ('ENT', 'In-flight Entertainment');
    INSERT INTO Flight_Service (Service_ID, Service_Name) VALUES ('EXL', 'Extra Legroom');
    INSERT INTO Flight_Service (Service_ID, Service_Name) VALUES ('PRI', 'Priority Boarding');
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Flight services populated');
END;
/

-- -----------------------------
-- 5. CREATE EXTENSIVE FLIGHTS (CURRENT DATE TO DEC 31, 2025)
-- -----------------------------
DECLARE
    flight_counter NUMBER := 1000;
    current_dt DATE := TRUNC(SYSDATE);
    end_dt DATE := DATE '2025-12-31';
    current_date DATE;
    
    -- Define routes and durations (in hours)
    TYPE route_rec IS RECORD (
        source_ap VARCHAR2(3),
        dest_ap VARCHAR2(3),
        duration NUMBER
    );
    
    TYPE route_table IS TABLE OF route_rec;
    routes route_table;
    
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating extensive flights from ' || TO_CHAR(current_dt, 'YYYY-MM-DD') || ' to ' || TO_CHAR(end_dt, 'YYYY-MM-DD'));
    
    -- Define all possible routes between airports
    routes := route_table(
        route_rec('KHI', 'LHE', 2.0),   route_rec('LHE', 'KHI', 2.0),
        route_rec('KHI', 'ISB', 2.5),   route_rec('ISB', 'KHI', 2.5),
        route_rec('KHI', 'PEW', 3.0),   route_rec('PEW', 'KHI', 3.0),
        route_rec('KHI', 'UET', 2.0),   route_rec('UET', 'KHI', 2.0),
        route_rec('KHI', 'MUX', 1.5),   route_rec('MUX', 'KHI', 1.5),
        route_rec('LHE', 'ISB', 1.0),   route_rec('ISB', 'LHE', 1.0),
        route_rec('LHE', 'PEW', 1.5),   route_rec('PEW', 'LHE', 1.5),
        route_rec('LHE', 'UET', 2.0),   route_rec('UET', 'LHE', 2.0),
        route_rec('LHE', 'MUX', 1.0),   route_rec('MUX', 'LHE', 1.0),
        route_rec('ISB', 'PEW', 1.0),   route_rec('PEW', 'ISB', 1.0),
        route_rec('ISB', 'UET', 2.5),   route_rec('UET', 'ISB', 2.5),
        route_rec('ISB', 'MUX', 1.5),   route_rec('MUX', 'ISB', 1.5),
        route_rec('PEW', 'UET', 2.0),   route_rec('UET', 'PEW', 2.0),
        route_rec('PEW', 'MUX', 2.0),   route_rec('MUX', 'PEW', 2.0),
        route_rec('UET', 'MUX', 1.5),   route_rec('MUX', 'UET', 1.5)
    );
    
    current_date := current_dt;
    WHILE current_date <= end_dt LOOP
        FOR i IN 1..routes.COUNT LOOP
            -- Create 2-4 flights per route per day (morning, afternoon, evening)
            FOR flight_num IN 1..3 LOOP
                DECLARE
                    departure_time TIMESTAMP;
                    arrival_time TIMESTAMP;
                    airplane_type VARCHAR2(20);
                BEGIN
                    -- Set departure times: 8:00, 14:00, 20:00
                    CASE flight_num
                        WHEN 1 THEN departure_time := TO_TIMESTAMP(TO_CHAR(current_date, 'YYYY-MM-DD') || ' 08:00:00', 'YYYY-MM-DD HH24:MI:SS');
                        WHEN 2 THEN departure_time := TO_TIMESTAMP(TO_CHAR(current_date, 'YYYY-MM-DD') || ' 14:00:00', 'YYYY-MM-DD HH24:MI:SS');
                        WHEN 3 THEN departure_time := TO_TIMESTAMP(TO_CHAR(current_date, 'YYYY-MM-DD') || ' 20:00:00', 'YYYY-MM-DD HH24:MI:SS');
                    END CASE;
                    
                    -- Add some random variation to departure times (±30 minutes)
                    departure_time := departure_time + NUMTODSINTERVAL(DBMS_RANDOM.VALUE(-30, 30), 'MINUTE');
                    
                    -- Calculate arrival time
                    arrival_time := departure_time + NUMTODSINTERVAL(routes(i).duration * 60, 'MINUTE');
                    
                    -- Select airplane type
                    CASE MOD(flight_counter, 4)
                        WHEN 0 THEN airplane_type := 'Airbus A320';
                        WHEN 1 THEN airplane_type := 'Boeing 737';
                        WHEN 2 THEN airplane_type := 'Airbus A321';
                        WHEN 3 THEN airplane_type := 'Boeing 777';
                    END CASE;
                    
                    -- Insert the flight
                    INSERT INTO Flight_Details (
                        Flight_ID, 
                        Source_Airport_ID, 
                        Destination_Airport_ID, 
                        Departure_Date_Time, 
                        Arrival_Date_Time, 
                        Airplane_Type
                    ) VALUES (
                        'IAT' || flight_counter,
                        routes(i).source_ap,
                        routes(i).dest_ap,
                        departure_time,
                        arrival_time,
                        airplane_type
                    );
                    
                    flight_counter := flight_counter + 1;
                    
                EXCEPTION
                    WHEN OTHERS THEN
                        DBMS_OUTPUT.PUT_LINE('Error creating flight IAT' || flight_counter || ': ' || SQLERRM);
                END;
            END LOOP;
        END LOOP;
        
        -- Show progress every 30 days
        IF MOD(current_date - current_dt, 30) = 0 THEN
            DBMS_OUTPUT.PUT_LINE('  Processed up to: ' || TO_CHAR(current_date, 'YYYY-MM-DD') || ' | Flights created: ' || flight_counter);
            COMMIT;
        END IF;
        
        current_date := current_date + 1;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Flights created: ' || (flight_counter - 1000) || ' total flights');
    DBMS_OUTPUT.PUT_LINE('✓ Date range: ' || TO_CHAR(current_dt, 'YYYY-MM-DD') || ' to ' || TO_CHAR(end_dt, 'YYYY-MM-DD'));
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Error in flight creation: ' || SQLERRM);
        ROLLBACK;
        RAISE;
END;
/

-- -----------------------------
-- 6. CREATE SEATS FOR ALL FLIGHTS (UPDATED WITH ROW_NUMBER AND SEAT_LETTER)
-- -----------------------------
DECLARE
    seats_per_row NUMBER := 6;
    total_seats NUMBER := 0;
    flights_processed NUMBER := 0;
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating seats for all flights...');
    
    FOR flight_rec IN (SELECT Flight_ID FROM Flight_Details ORDER BY Flight_ID) LOOP
        flights_processed := flights_processed + 1;
        
        FOR class_rec IN (SELECT Travel_Class_ID, Travel_Class_Capacity FROM Travel_Class ORDER BY Travel_Class_ID) LOOP
            DECLARE
                rows_needed NUMBER := FLOOR(class_rec.Travel_Class_Capacity / seats_per_row);
            BEGIN
                FOR row_num IN 1..rows_needed LOOP
                    FOR seat_num IN 1..seats_per_row LOOP
                        BEGIN
                            INSERT INTO Seat_Details (Seat_ID, Travel_Class_ID, Flight_ID, Row_Number, Seat_Letter)
                            VALUES (
                                flight_rec.Flight_ID || '-' || row_num || CHR(64 + seat_num),
                                class_rec.Travel_Class_ID,
                                flight_rec.Flight_ID,
                                row_num,
                                CHR(64 + seat_num)
                            );
                            total_seats := total_seats + 1;
                        EXCEPTION
                            WHEN DUP_VAL_ON_INDEX THEN
                                NULL;
                            WHEN OTHERS THEN
                                DBMS_OUTPUT.PUT_LINE('Error with seat creation: ' || SQLERRM);
                        END;
                    END LOOP;
                END LOOP;
            END;
        END LOOP;
        
        -- Show progress
        IF MOD(flights_processed, 100) = 0 THEN
            DBMS_OUTPUT.PUT_LINE('  Processed ' || flights_processed || ' flights, ' || total_seats || ' seats...');
            COMMIT;
        END IF;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Seats created: ' || total_seats || ' seats for ' || flights_processed || ' flights');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Error creating seats: ' || SQLERRM);
        ROLLBACK;
        RAISE;
END;
/

-- -----------------------------
-- 7. CREATE SERVICE OFFERINGS
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating service offerings...');
    
    -- Economy class
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('ECO', 'MEAL', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    
    -- Business class
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('BUS', 'MEAL', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('BUS', 'WIFI', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('BUS', 'PRI', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    
    -- First class
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('FIR', 'MEAL', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('FIR', 'WIFI', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('FIR', 'ENT', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('FIR', 'EXL', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    INSERT INTO Service_Offering (Travel_Class_ID, Service_ID, Offered_YN, From_Date, To_Date) VALUES ('FIR', 'PRI', 'Y', DATE '2025-01-01', DATE '2025-12-31');
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Service offerings created');
END;
/

-- -----------------------------
-- 8. CREATE SAMPLE PASSENGERS
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating sample passengers...');
    
    INSERT INTO Passenger VALUES ('P001', 'Ali', 'Khan', 'ali.khan@example.com', '03001234567', 'House 10', 'Karachi', 'Sindh', '74400', 'Pakistan');
    INSERT INTO Passenger VALUES ('P002', 'Ayesha', 'Ahmed', 'ayesha.ahmed@example.com', '03007654321', 'House 5', 'Lahore', 'Punjab', '54000', 'Pakistan');
    INSERT INTO Passenger VALUES ('P003', 'Usman', 'Malik', 'usman.malik@example.com', '03009876543', 'Sector F-8', 'Islamabad', 'Federal', '44000', 'Pakistan');
    INSERT INTO Passenger VALUES ('P004', 'Fatima', 'Raza', 'fatima.raza@example.com', '03005556677', 'University Road', 'Peshawar', 'KPK', '25000', 'Pakistan');
    INSERT INTO Passenger VALUES ('P005', 'Bilal', 'Shah', 'bilal.shah@example.com', '03003334455', 'Jinnah Road', 'Quetta', 'Balochistan', '87300', 'Pakistan');
    INSERT INTO Passenger VALUES ('P006', 'Sara', 'Iqbal', 'sara.iqbal@example.com', '03002223344', 'Bosan Road', 'Multan', 'Punjab', '60000', 'Pakistan');
    INSERT INTO Passenger VALUES ('P007', 'Ahmed', 'Hassan', 'ahmed.hassan@example.com', '03004445566', 'Gulshan-e-Iqbal', 'Karachi', 'Sindh', '75300', 'Pakistan');
    INSERT INTO Passenger VALUES ('P008', 'Zainab', 'Akhtar', 'zainab.akhtar@example.com', '03007778899', 'Defence Housing', 'Lahore', 'Punjab', '54700', 'Pakistan');
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Passengers created: 8 sample passengers');
END;
/

-- -----------------------------
-- 9. CREATE FLIGHT COSTS WITH REALISTIC PAKISTANI PRICING
-- -----------------------------
DECLARE
    total_costs NUMBER := 0;
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating flight costs with realistic Pakistani pricing...');
    
    FOR seat_rec IN (
        SELECT s.Seat_ID, s.Travel_Class_ID, f.Source_Airport_ID, f.Destination_Airport_ID, f.Departure_Date_Time
        FROM Seat_Details s 
        JOIN Flight_Details f ON s.Flight_ID = f.Flight_ID
    ) LOOP
        DECLARE
            final_price NUMBER;
            peak_multiplier NUMBER := 1.0;
        BEGIN
            -- REALISTIC PAKISTANI FLIGHT PRICING (in PKR)
            -- Apply peak season multiplier for December (20% increase)
            IF EXTRACT(MONTH FROM seat_rec.Departure_Date_Time) = 12 THEN
                peak_multiplier := 1.2;
            END IF;
            
            -- Set prices based on exact route and class
            CASE 
                -- KHI Routes
                WHEN seat_rec.Source_Airport_ID = 'KHI' AND seat_rec.Destination_Airport_ID = 'LHE' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 16000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 35200 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 56000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'KHI' AND seat_rec.Destination_Airport_ID = 'ISB' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 20000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 44000 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 70000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'KHI' AND seat_rec.Destination_Airport_ID = 'PEW' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 26880 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 59136 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 94080 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'KHI' AND seat_rec.Destination_Airport_ID = 'UET' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'KHI' AND seat_rec.Destination_Airport_ID = 'MUX' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 12000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 26400 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 42000 * peak_multiplier;
                    END CASE;
                    
                -- LHE Routes
                WHEN seat_rec.Source_Airport_ID = 'LHE' AND seat_rec.Destination_Airport_ID = 'KHI' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 16000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 35200 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 56000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'LHE' AND seat_rec.Destination_Airport_ID = 'ISB' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 8000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 17600 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 28000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'LHE' AND seat_rec.Destination_Airport_ID = 'PEW' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 13440 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 29568 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 47040 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'LHE' AND seat_rec.Destination_Airport_ID = 'UET' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'LHE' AND seat_rec.Destination_Airport_ID = 'MUX' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 8000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 17600 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 28000 * peak_multiplier;
                    END CASE;
                    
                -- ISB Routes
                WHEN seat_rec.Source_Airport_ID = 'ISB' AND seat_rec.Destination_Airport_ID = 'KHI' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 20000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 44000 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 70000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'ISB' AND seat_rec.Destination_Airport_ID = 'LHE' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 8000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 17600 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 28000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'ISB' AND seat_rec.Destination_Airport_ID = 'PEW' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 8960 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 19712 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 31360 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'ISB' AND seat_rec.Destination_Airport_ID = 'UET' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 22400 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 49280 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 78400 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'ISB' AND seat_rec.Destination_Airport_ID = 'MUX' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 12000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 26400 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 42000 * peak_multiplier;
                    END CASE;
                    
                -- PEW Routes
                WHEN seat_rec.Source_Airport_ID = 'PEW' AND seat_rec.Destination_Airport_ID = 'KHI' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 26880 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 59136 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 94080 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'PEW' AND seat_rec.Destination_Airport_ID = 'LHE' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 13440 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 29568 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 47040 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'PEW' AND seat_rec.Destination_Airport_ID = 'ISB' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 8960 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 19712 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 31360 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'PEW' AND seat_rec.Destination_Airport_ID = 'UET' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'PEW' AND seat_rec.Destination_Airport_ID = 'MUX' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                -- UET Routes
                WHEN seat_rec.Source_Airport_ID = 'UET' AND seat_rec.Destination_Airport_ID = 'KHI' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'UET' AND seat_rec.Destination_Airport_ID = 'LHE' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'UET' AND seat_rec.Destination_Airport_ID = 'ISB' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 22400 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 49280 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 78400 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'UET' AND seat_rec.Destination_Airport_ID = 'PEW' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'UET' AND seat_rec.Destination_Airport_ID = 'MUX' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 13440 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 29568 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 47040 * peak_multiplier;
                    END CASE;
                    
                -- MUX Routes
                WHEN seat_rec.Source_Airport_ID = 'MUX' AND seat_rec.Destination_Airport_ID = 'KHI' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 12000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 26400 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 42000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'MUX' AND seat_rec.Destination_Airport_ID = 'LHE' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 8000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 17600 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 28000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'MUX' AND seat_rec.Destination_Airport_ID = 'ISB' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 12000 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 26400 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 42000 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'MUX' AND seat_rec.Destination_Airport_ID = 'PEW' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 17920 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 39424 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 62720 * peak_multiplier;
                    END CASE;
                    
                WHEN seat_rec.Source_Airport_ID = 'MUX' AND seat_rec.Destination_Airport_ID = 'UET' THEN
                    CASE seat_rec.Travel_Class_ID
                        WHEN 'ECO' THEN final_price := 13440 * peak_multiplier;
                        WHEN 'BUS' THEN final_price := 29568 * peak_multiplier;
                        WHEN 'FIR' THEN final_price := 47040 * peak_multiplier;
                    END CASE;
                    
                ELSE
                    -- Default price if route not found
                    final_price := 15000;
            END CASE;
            
            -- Round to nearest whole number (PKR doesn't have decimals)
            final_price := ROUND(final_price);
            
            INSERT INTO Flight_Cost (Seat_ID, Valid_From_Date, Valid_To_Date, Cost)
            VALUES (seat_rec.Seat_ID, DATE '2025-01-01', DATE '2025-12-31', final_price);
            
            total_costs := total_costs + 1;
            
        EXCEPTION
            WHEN OTHERS THEN 
                DBMS_OUTPUT.PUT_LINE('Error with seat ' || seat_rec.Seat_ID || ': ' || SQLERRM);
        END;
        
        -- Show progress
        IF MOD(total_costs, 10000) = 0 THEN
            DBMS_OUTPUT.PUT_LINE('  Processed ' || total_costs || ' seat costs...');
            COMMIT;
        END IF;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Flight costs created: ' || total_costs || ' seat prices with realistic Pakistani pricing');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Error creating flight costs: ' || SQLERRM);
        ROLLBACK;
        RAISE;
END;
/

-- -----------------------------
-- 10. CREATE SAMPLE RESERVATIONS (UPDATED WITH REALISTIC PRICES)
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating sample reservations...');
    
    -- Create some sample reservations for upcoming flights
    FOR i IN 1..10 LOOP
        DECLARE
            seat_id_var VARCHAR2(50);
            flight_cost NUMBER;
        BEGIN
            -- Get a random available seat from upcoming flights with its cost
            SELECT s.Seat_ID, fc.Cost INTO seat_id_var, flight_cost
            FROM (
                SELECT s.Seat_ID, fc.Cost
                FROM Seat_Details s
                JOIN Flight_Details f ON s.Flight_ID = f.Flight_ID
                JOIN Flight_Cost fc ON s.Seat_ID = fc.Seat_ID
                WHERE f.Departure_Date_Time > SYSTIMESTAMP
                AND NOT EXISTS (
                    SELECT 1 FROM Reservation r WHERE r.Seat_ID = s.Seat_ID
                )
                ORDER BY DBMS_RANDOM.VALUE
            ) WHERE ROWNUM = 1;
            
            INSERT INTO Reservation (Reservation_ID, Passenger_ID, Seat_ID, Date_Of_Reservation) 
            VALUES ('R' || LPAD(i, 3, '0'), 'P' || LPAD(MOD(i, 8) + 1, 3, '0'), seat_id_var, SYSDATE - DBMS_RANDOM.VALUE(1, 10));
            
            INSERT INTO Payment_Status (Payment_ID, Payment_Status_YN, Payment_Due_Date, Payment_Amount, Reservation_ID) 
            VALUES ('PAY' || LPAD(i, 3, '0'), 'Y', SYSDATE + 2, flight_cost, 'R' || LPAD(i, 3, '0'));
            
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                DBMS_OUTPUT.PUT_LINE('No available seats found for reservation');
            WHEN OTHERS THEN
                DBMS_OUTPUT.PUT_LINE('Error creating reservation: ' || SQLERRM);
        END;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Sample reservations created with realistic pricing');
END;
/

-- -----------------------------
-- FINAL SUMMARY
-- -----------------------------
DECLARE
    v_airports NUMBER;
    v_flights NUMBER;
    v_seats NUMBER;
    v_passengers NUMBER;
    v_reservations NUMBER;
    v_flight_costs NUMBER;
    v_earliest_date DATE;
    v_latest_date DATE;
BEGIN
    SELECT COUNT(*) INTO v_airports FROM Airport;
    SELECT COUNT(*) INTO v_flights FROM Flight_Details;
    SELECT COUNT(*) INTO v_seats FROM Seat_Details;
    SELECT COUNT(*) INTO v_passengers FROM Passenger;
    SELECT COUNT(*) INTO v_reservations FROM Reservation;
    SELECT COUNT(*) INTO v_flight_costs FROM Flight_Cost;
    SELECT MIN(TRUNC(Departure_Date_Time)), MAX(TRUNC(Departure_Date_Time)) 
    INTO v_earliest_date, v_latest_date FROM Flight_Details;
    
    DBMS_OUTPUT.PUT_LINE('=========================================');
    DBMS_OUTPUT.PUT_LINE('DATABASE POPULATION COMPLETE!');
    DBMS_OUTPUT.PUT_LINE('=========================================');
    DBMS_OUTPUT.PUT_LINE('Summary:');
    DBMS_OUTPUT.PUT_LINE('- Airports: ' || v_airports);
    DBMS_OUTPUT.PUT_LINE('- Flights: ' || v_flights);
    DBMS_OUTPUT.PUT_LINE('- Seats: ' || v_seats);
    DBMS_OUTPUT.PUT_LINE('- Passengers: ' || v_passengers);
    DBMS_OUTPUT.PUT_LINE('- Reservations: ' || v_reservations);
    DBMS_OUTPUT.PUT_LINE('- Flight Costs: ' || v_flight_costs);
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Flight Date Range:');
    DBMS_OUTPUT.PUT_LINE('- From: ' || TO_CHAR(v_earliest_date, 'YYYY-MM-DD'));
    DBMS_OUTPUT.PUT_LINE('- To: ' || TO_CHAR(v_latest_date, 'YYYY-MM-DD'));
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('All routes available with REALISTIC PAKISTANI PRICING:');
    DBMS_OUTPUT.PUT_LINE('- Karachi (KHI), Lahore (LHE), Islamabad (ISB)');
    DBMS_OUTPUT.PUT_LINE('- Peshawar (PEW), Quetta (UET), Multan (MUX)');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Example Prices:');
    DBMS_OUTPUT.PUT_LINE('- KHI to LHE: Economy ₹16,000, Business ₹35,200, First ₹56,000');
    DBMS_OUTPUT.PUT_LINE('- LHE to ISB: Economy ₹8,000, Business ₹17,600, First ₹28,000');
    DBMS_OUTPUT.PUT_LINE('- KHI to ISB: Economy ₹20,000, Business ₹44,000, First ₹70,000');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Completed at: ' || TO_CHAR(SYSTIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'));
    DBMS_OUTPUT.PUT_LINE('=========================================');
END;
/

COMMIT;