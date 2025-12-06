-- complete_populate_db_realistic_prices.sql
-- IAT Airlines Database Population Script - REALISTIC PAKISTANI PRICING
-- UPDATED FOR NEW SCHEMA WITH ECONOMY EXTENDING TO 30F

SET SERVEROUTPUT ON;
SET VERIFY OFF;

BEGIN
    DBMS_OUTPUT.PUT_LINE('=========================================');
    DBMS_OUTPUT.PUT_LINE('IAT Airlines Database Population - REALISTIC PRICES');
    DBMS_OUTPUT.PUT_LINE('Creating flights with realistic Pakistani pricing');
    DBMS_OUTPUT.PUT_LINE('Economy class now extends to row 30F');
    DBMS_OUTPUT.PUT_LINE('Starting at: ' || TO_CHAR(SYSTIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'));
    DBMS_OUTPUT.PUT_LINE('=========================================');
END;
/

-- -----------------------------
-- 1. DELETE EXISTING DATA
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Clearing existing data...');
    
    EXECUTE IMMEDIATE 'DELETE FROM Cancellation_Log';
    EXECUTE IMMEDIATE 'DELETE FROM Payment';
    EXECUTE IMMEDIATE 'DELETE FROM Reservation';
    EXECUTE IMMEDIATE 'DELETE FROM Passenger';
    EXECUTE IMMEDIATE 'DELETE FROM Booking';
    EXECUTE IMMEDIATE 'DELETE FROM App_User';
    EXECUTE IMMEDIATE 'DELETE FROM Route_Pricing';
    EXECUTE IMMEDIATE 'DELETE FROM Flight_Instance';
    EXECUTE IMMEDIATE 'DELETE FROM Flight_Route';
    EXECUTE IMMEDIATE 'DELETE FROM Service_Offering';
    EXECUTE IMMEDIATE 'DELETE FROM Flight_Service';
    EXECUTE IMMEDIATE 'DELETE FROM Aircraft_Seat_Map';
    EXECUTE IMMEDIATE 'DELETE FROM Aircraft_Row_Class';
    EXECUTE IMMEDIATE 'DELETE FROM Travel_Class';
    EXECUTE IMMEDIATE 'DELETE FROM Aircraft_Model';
    EXECUTE IMMEDIATE 'DELETE FROM Airport';
    EXECUTE IMMEDIATE 'DELETE FROM Zip_Master';
    EXECUTE IMMEDIATE 'DELETE FROM City';
    EXECUTE IMMEDIATE 'DELETE FROM State_Province';
    EXECUTE IMMEDIATE 'DELETE FROM Country';
    
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
-- 2. POPULATE GEOGRAPHIC DATA
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Populating geographic data...');
    
    -- Countries
    INSERT INTO Country (Country_ID, Country_Name) VALUES (1, 'Pakistan');
    
    -- States/Provinces
    INSERT INTO State_Province (State_ID, State_Name, Country_ID) VALUES (1, 'Sindh', 1);
    INSERT INTO State_Province (State_ID, State_Name, Country_ID) VALUES (2, 'Punjab', 1);
    INSERT INTO State_Province (State_ID, State_Name, Country_ID) VALUES (3, 'Khyber Pakhtunkhwa', 1);
    INSERT INTO State_Province (State_ID, State_Name, Country_ID) VALUES (4, 'Balochistan', 1);
    INSERT INTO State_Province (State_ID, State_Name, Country_ID) VALUES (5, 'Federal', 1);
    
    -- Cities
    INSERT INTO City (City_ID, City_Name, State_ID) VALUES (1, 'Karachi', 1);
    INSERT INTO City (City_ID, City_Name, State_ID) VALUES (2, 'Lahore', 2);
    INSERT INTO City (City_ID, City_Name, State_ID) VALUES (3, 'Islamabad', 5);
    INSERT INTO City (City_ID, City_Name, State_ID) VALUES (4, 'Peshawar', 3);
    INSERT INTO City (City_ID, City_Name, State_ID) VALUES (5, 'Quetta', 4);
    INSERT INTO City (City_ID, City_Name, State_ID) VALUES (6, 'Multan', 2);
    
    -- Zip Codes
    INSERT INTO Zip_Master (Zipcode, City_ID) VALUES ('74400', 1);
    INSERT INTO Zip_Master (Zipcode, City_ID) VALUES ('54000', 2);
    INSERT INTO Zip_Master (Zipcode, City_ID) VALUES ('44000', 3);
    INSERT INTO Zip_Master (Zipcode, City_ID) VALUES ('25000', 4);
    INSERT INTO Zip_Master (Zipcode, City_ID) VALUES ('87300', 5);
    INSERT INTO Zip_Master (Zipcode, City_ID) VALUES ('60000', 6);
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Geographic data populated');
END;
/

-- -----------------------------
-- 3. POPULATE AIRPORTS
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Populating airports...');
    
    INSERT INTO Airport (Airport_ID, Airport_Name, Zipcode) VALUES ('KHI', 'Jinnah International Airport', '74400');
    INSERT INTO Airport (Airport_ID, Airport_Name, Zipcode) VALUES ('LHE', 'Allama Iqbal International Airport', '54000');
    INSERT INTO Airport (Airport_ID, Airport_Name, Zipcode) VALUES ('ISB', 'Islamabad International Airport', '44000');
    INSERT INTO Airport (Airport_ID, Airport_Name, Zipcode) VALUES ('PEW', 'Peshawar International Airport', '25000');
    INSERT INTO Airport (Airport_ID, Airport_Name, Zipcode) VALUES ('UET', 'Quetta International Airport', '87300');
    INSERT INTO Airport (Airport_ID, Airport_Name, Zipcode) VALUES ('MUX', 'Multan International Airport', '60000');
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Airports populated: 6 airports added');
END;
/

-- -----------------------------
-- 4. POPULATE AIRCRAFT MODELS
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Populating aircraft models...');
    
    INSERT INTO Aircraft_Model (Model_ID, Model_Name, Manufacturer) VALUES ('A320', 'Airbus A320', 'Airbus');
    INSERT INTO Aircraft_Model (Model_ID, Model_Name, Manufacturer) VALUES ('B737', 'Boeing 737', 'Boeing');
    INSERT INTO Aircraft_Model (Model_ID, Model_Name, Manufacturer) VALUES ('A321', 'Airbus A321', 'Airbus');
    INSERT INTO Aircraft_Model (Model_ID, Model_Name, Manufacturer) VALUES ('B777', 'Boeing 777', 'Boeing');
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Aircraft models populated');
END;
/

-- -----------------------------
-- 5. POPULATE TRAVEL CLASSES
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Populating travel classes...');
    
    INSERT INTO Travel_Class (Class_ID, Class_Name) VALUES ('ECO', 'Economy');
    INSERT INTO Travel_Class (Class_ID, Class_Name) VALUES ('BUS', 'Business');
    INSERT INTO Travel_Class (Class_ID, Class_Name) VALUES ('FIR', 'First');
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Travel classes populated');
END;
/

-- -----------------------------
-- 6. CREATE AIRCRAFT SEAT CONFIGURATION (UPDATED WITH ECONOMY TO 30F)
-- -----------------------------
DECLARE
    seats_per_row NUMBER := 6;
    
    -- UPDATED: Class row assignments
    first_class_start_row NUMBER := 1;
    first_class_end_row NUMBER := 4;    -- 4 rows for First Class
    
    business_class_start_row NUMBER := 5;
    business_class_end_row NUMBER := 10; -- 6 rows for Business Class
    
    economy_class_start_row NUMBER := 11;
    economy_class_end_row NUMBER := 30;  -- UPDATED: 20 rows for Economy Class (up to 30F)
    
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating aircraft seat configuration with Economy extending to row 30F...');
    DBMS_OUTPUT.PUT_LINE('  First Class: Rows ' || first_class_start_row || '-' || first_class_end_row);
    DBMS_OUTPUT.PUT_LINE('  Business Class: Rows ' || business_class_start_row || '-' || business_class_end_row);
    DBMS_OUTPUT.PUT_LINE('  Economy Class: Rows ' || economy_class_start_row || '-' || economy_class_end_row);
    
    -- Create seat configuration for each aircraft model
    FOR model_rec IN (SELECT Model_ID FROM Aircraft_Model) LOOP
        -- First Class rows
        FOR row_num IN first_class_start_row..first_class_end_row LOOP
            INSERT INTO Aircraft_Row_Class (Model_ID, Row_Number, Class_ID)
            VALUES (model_rec.Model_ID, row_num, 'FIR');
            
            FOR seat_num IN 1..seats_per_row LOOP
                INSERT INTO Aircraft_Seat_Map (Model_ID, Row_Number, Seat_Letter)
                VALUES (model_rec.Model_ID, row_num, CHR(64 + seat_num));
            END LOOP;
        END LOOP;
        
        -- Business Class rows
        FOR row_num IN business_class_start_row..business_class_end_row LOOP
            INSERT INTO Aircraft_Row_Class (Model_ID, Row_Number, Class_ID)
            VALUES (model_rec.Model_ID, row_num, 'BUS');
            
            FOR seat_num IN 1..seats_per_row LOOP
                INSERT INTO Aircraft_Seat_Map (Model_ID, Row_Number, Seat_Letter)
                VALUES (model_rec.Model_ID, row_num, CHR(64 + seat_num));
            END LOOP;
        END LOOP;
        
        -- Economy Class rows (UPDATED TO 30)
        FOR row_num IN economy_class_start_row..economy_class_end_row LOOP
            INSERT INTO Aircraft_Row_Class (Model_ID, Row_Number, Class_ID)
            VALUES (model_rec.Model_ID, row_num, 'ECO');
            
            FOR seat_num IN 1..seats_per_row LOOP
                INSERT INTO Aircraft_Seat_Map (Model_ID, Row_Number, Seat_Letter)
                VALUES (model_rec.Model_ID, row_num, CHR(64 + seat_num));
            END LOOP;
        END LOOP;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Aircraft seat configuration created');
    DBMS_OUTPUT.PUT_LINE('✓ Economy class now extends to row ' || economy_class_end_row || 'F');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Error creating seat configuration: ' || SQLERRM);
        ROLLBACK;
        RAISE;
END;
/

-- -----------------------------
-- 7. POPULATE FLIGHT SERVICES
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
-- 8. CREATE SERVICE OFFERINGS (UPDATED FOR NEW SCHEMA)
-- -----------------------------
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating service offerings...');
    
    -- For demonstration, create service offerings for all routes and classes
    FOR route_rec IN (SELECT Route_ID FROM Flight_Route) LOOP
        -- Economy class services
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'ECO', 'MEAL', DATE '2025-01-01', DATE '2026-01-31', 'N', 500);
        
        -- Business class services
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'BUS', 'MEAL', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'BUS', 'WIFI', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'BUS', 'PRI', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
        
        -- First class services
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'FIR', 'MEAL', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'FIR', 'WIFI', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'FIR', 'ENT', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'FIR', 'EXL', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
        INSERT INTO Service_Offering (Route_ID, Class_ID, Service_ID, Valid_From, Valid_To, Is_Complimentary, Cost_If_Paid)
        VALUES (route_rec.Route_ID, 'FIR', 'PRI', DATE '2025-01-01', DATE '2026-01-31', 'Y', 0);
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Service offerings created');
END;
/

-- -----------------------------
-- 9. CREATE FLIGHT ROUTES
-- -----------------------------
DECLARE
    route_counter NUMBER := 100;
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating flight routes...');
    
    -- Define all possible routes between airports
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'KHI', 'LHE', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'LHE', 'KHI', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'KHI', 'ISB', 150); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'ISB', 'KHI', 150); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'KHI', 'PEW', 180); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'PEW', 'KHI', 180); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'KHI', 'UET', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'UET', 'KHI', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'KHI', 'MUX', 90); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'MUX', 'KHI', 90); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'LHE', 'ISB', 60); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'ISB', 'LHE', 60); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'LHE', 'PEW', 90); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'PEW', 'LHE', 90); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'LHE', 'UET', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'UET', 'LHE', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'LHE', 'MUX', 60); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'MUX', 'LHE', 60); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'ISB', 'PEW', 60); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'PEW', 'ISB', 60); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'ISB', 'UET', 150); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'UET', 'ISB', 150); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'ISB', 'MUX', 90); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'MUX', 'ISB', 90); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'PEW', 'UET', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'UET', 'PEW', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'PEW', 'MUX', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'MUX', 'PEW', 120); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'UET', 'MUX', 90); route_counter := route_counter + 1;
    INSERT INTO Flight_Route (Route_ID, Source_Airport, Dest_Airport, Base_Duration) VALUES ('RT' || route_counter, 'MUX', 'UET', 90); route_counter := route_counter + 1;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Flight routes created: ' || (route_counter - 100) || ' routes');
END;
/

-- -----------------------------
-- 10. CREATE ROUTE PRICING WITH REALISTIC PAKISTANI PRICING (FIXED)
-- -----------------------------
DECLARE
    pricing_counter NUMBER := 1;
    
    -- Pricing matrix for all airport combinations
    TYPE pricing_matrix IS TABLE OF NUMBER INDEX BY VARCHAR2(10);
    eco_prices pricing_matrix;
    bus_prices pricing_matrix;
    fir_prices pricing_matrix;
    
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating route pricing with realistic Pakistani pricing...');
    
    -- Initialize pricing matrix for ALL airport combinations
    -- Format: 'KHI-LHE' -> price
    eco_prices('KHI-LHE') := 16000;
    bus_prices('KHI-LHE') := 35200;
    fir_prices('KHI-LHE') := 56000;
    
    eco_prices('KHI-ISB') := 20000;
    bus_prices('KHI-ISB') := 44000;
    fir_prices('KHI-ISB') := 70000;
    
    eco_prices('KHI-PEW') := 26880;
    bus_prices('KHI-PEW') := 59136;
    fir_prices('KHI-PEW') := 94080;
    
    eco_prices('KHI-UET') := 17920;
    bus_prices('KHI-UET') := 39424;
    fir_prices('KHI-UET') := 62720;
    
    eco_prices('KHI-MUX') := 12000;
    bus_prices('KHI-MUX') := 26400;
    fir_prices('KHI-MUX') := 42000;
    
    eco_prices('LHE-ISB') := 8000;
    bus_prices('LHE-ISB') := 17600;
    fir_prices('LHE-ISB') := 28000;
    
    eco_prices('LHE-PEW') := 13440;
    bus_prices('LHE-PEW') := 29568;
    fir_prices('LHE-PEW') := 47040;
    
    eco_prices('LHE-UET') := 17920;
    bus_prices('LHE-UET') := 39424;
    fir_prices('LHE-UET') := 62720;
    
    eco_prices('LHE-MUX') := 8000;
    bus_prices('LHE-MUX') := 17600;
    fir_prices('LHE-MUX') := 28000;
    
    eco_prices('ISB-PEW') := 8960;
    bus_prices('ISB-PEW') := 19712;
    fir_prices('ISB-PEW') := 31360;
    
    eco_prices('ISB-UET') := 22400;
    bus_prices('ISB-UET') := 49280;
    fir_prices('ISB-UET') := 78400;
    
    eco_prices('ISB-MUX') := 12000;
    bus_prices('ISB-MUX') := 26400;
    fir_prices('ISB-MUX') := 42000;
    
    eco_prices('PEW-UET') := 17920;
    bus_prices('PEW-UET') := 39424;
    fir_prices('PEW-UET') := 62720;
    
    eco_prices('PEW-MUX') := 17920;
    bus_prices('PEW-MUX') := 39424;
    fir_prices('PEW-MUX') := 62720;
    
    eco_prices('UET-MUX') := 13440;
    bus_prices('UET-MUX') := 29568;
    fir_prices('UET-MUX') := 47040;
    
    -- For return routes, use the same pricing as forward routes
    FOR route_rec IN (SELECT Route_ID, Source_Airport, Dest_Airport FROM Flight_Route) LOOP
        DECLARE
            route_key VARCHAR2(10);
        BEGIN
            -- Create route key (e.g., 'KHI-LHE')
            route_key := route_rec.Source_Airport || '-' || route_rec.Dest_Airport;
            
            -- Check if we have pricing for this route
            IF eco_prices.EXISTS(route_key) THEN
                -- Insert pricing for all three classes
                INSERT INTO Route_Pricing (Pricing_ID, Route_ID, Class_ID, Valid_From, Valid_To, Base_Price) 
                VALUES (pricing_counter, route_rec.Route_ID, 'ECO', DATE '2025-01-01', DATE '2026-01-31', eco_prices(route_key));
                pricing_counter := pricing_counter + 1;
                
                INSERT INTO Route_Pricing (Pricing_ID, Route_ID, Class_ID, Valid_From, Valid_To, Base_Price) 
                VALUES (pricing_counter, route_rec.Route_ID, 'BUS', DATE '2025-01-01', DATE '2026-01-31', bus_prices(route_key));
                pricing_counter := pricing_counter + 1;
                
                INSERT INTO Route_Pricing (Pricing_ID, Route_ID, Class_ID, Valid_From, Valid_To, Base_Price) 
                VALUES (pricing_counter, route_rec.Route_ID, 'FIR', DATE '2025-01-01', DATE '2026-01-31', fir_prices(route_key));
                pricing_counter := pricing_counter + 1;
                
            ELSE
                -- Try the reverse route (for return flights)
                route_key := route_rec.Dest_Airport || '-' || route_rec.Source_Airport;
                
                IF eco_prices.EXISTS(route_key) THEN
                    -- Use the same pricing for return routes
                    INSERT INTO Route_Pricing (Pricing_ID, Route_ID, Class_ID, Valid_From, Valid_To, Base_Price) 
                    VALUES (pricing_counter, route_rec.Route_ID, 'ECO', DATE '2025-01-01', DATE '2026-01-31', eco_prices(route_key));
                    pricing_counter := pricing_counter + 1;
                    
                    INSERT INTO Route_Pricing (Pricing_ID, Route_ID, Class_ID, Valid_From, Valid_To, Base_Price) 
                    VALUES (pricing_counter, route_rec.Route_ID, 'BUS', DATE '2025-01-01', DATE '2026-01-31', bus_prices(route_key));
                    pricing_counter := pricing_counter + 1;
                    
                    INSERT INTO Route_Pricing (Pricing_ID, Route_ID, Class_ID, Valid_From, Valid_To, Base_Price) 
                    VALUES (pricing_counter, route_rec.Route_ID, 'FIR', DATE '2025-01-01', DATE '2026-01-31', fir_prices(route_key));
                    pricing_counter := pricing_counter + 1;
                ELSE
                    DBMS_OUTPUT.PUT_LINE('Warning: No pricing found for route ' || route_rec.Route_ID || ' (' || route_rec.Source_Airport || '-' || route_rec.Dest_Airport || ')');
                END IF;
            END IF;
        END;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Route pricing created with realistic Pakistani pricing');
    DBMS_OUTPUT.PUT_LINE('✓ Total pricing records: ' || (pricing_counter - 1));
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Error creating route pricing: ' || SQLERRM);
        ROLLBACK;
        RAISE;
END;
/

-- -----------------------------
-- 11. CREATE EXTENSIVE FLIGHT INSTANCES WITH QUARTER-HOUR TIMINGS
-- -----------------------------
DECLARE
    instance_counter NUMBER := 1000;
    current_dt DATE := TRUNC(SYSDATE);
    end_dt DATE := DATE '2026-01-31';
    current_date DATE;
    
    route_count NUMBER;
    model_count NUMBER;
    
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating extensive flight instances from ' || TO_CHAR(current_dt, 'YYYY-MM-DD') || ' to ' || TO_CHAR(end_dt, 'YYYY-MM-DD'));
    DBMS_OUTPUT.PUT_LINE('Using quarter-hour timings (00, 15, 30, 45 minutes)');
    
    -- Get counts for randomization
    SELECT COUNT(*) INTO route_count FROM Flight_Route;
    SELECT COUNT(*) INTO model_count FROM Aircraft_Model;
    
    current_date := current_dt;
    WHILE current_date <= end_dt LOOP
        FOR route_rec IN (SELECT Route_ID, Source_Airport, Dest_Airport, Base_Duration FROM Flight_Route) LOOP
            -- Create 3 flights per route per day with quarter-hour timings
            FOR flight_num IN 1..3 LOOP
                DECLARE
                    base_hour NUMBER;
                    quarter_minute NUMBER;
                    departure_time TIMESTAMP;
                    arrival_time TIMESTAMP;
                    model_id_var VARCHAR2(20);
                    instance_id_var VARCHAR2(20);
                BEGIN
                    -- Set base hours for different flight times of day
                    CASE flight_num
                        WHEN 1 THEN base_hour := 8;  -- Morning flight
                        WHEN 2 THEN base_hour := 14; -- Afternoon flight  
                        WHEN 3 THEN base_hour := 20; -- Evening flight
                    END CASE;
                    
                    -- Choose quarter-hour minute (00, 15, 30, 45)
                    CASE MOD(instance_counter, 4)
                        WHEN 0 THEN quarter_minute := 0;
                        WHEN 1 THEN quarter_minute := 15;
                        WHEN 2 THEN quarter_minute := 30;
                        WHEN 3 THEN quarter_minute := 45;
                    END CASE;
                    
                    -- Create departure time with quarter-hour precision
                    departure_time := TO_TIMESTAMP(
                        TO_CHAR(current_date, 'YYYY-MM-DD') || ' ' || 
                        LPAD(base_hour, 2, '0') || ':' || 
                        LPAD(quarter_minute, 2, '0') || ':00', 
                        'YYYY-MM-DD HH24:MI:SS'
                    );
                    
                    -- Calculate arrival time (maintaining quarter-hour precision)
                    arrival_time := departure_time + NUMTODSINTERVAL(route_rec.Base_Duration, 'MINUTE');
                    
                    -- Round arrival time to nearest quarter hour for consistency
                    arrival_time := TRUNC(arrival_time, 'MI') + 
                                   NUMTODSINTERVAL(ROUND(TO_NUMBER(TO_CHAR(arrival_time, 'MI')) / 15) * 15, 'MINUTE');
                    
                    -- Select random aircraft model
                    SELECT Model_ID INTO model_id_var
                    FROM (
                        SELECT Model_ID, ROWNUM as rn
                        FROM Aircraft_Model
                        ORDER BY Model_ID
                    ) WHERE rn = MOD(instance_counter, model_count) + 1;
                    
                    -- Create instance ID
                    instance_id_var := 'IAT' || instance_counter;
                    
                    -- Insert the flight instance
                    INSERT INTO Flight_Instance (
                        Instance_ID,
                        Route_ID,
                        Model_ID,
                        Departure_Time,
                        Arrival_Time,
                        Flight_Status
                    ) VALUES (
                        instance_id_var,
                        route_rec.Route_ID,
                        model_id_var,
                        departure_time,
                        arrival_time,
                        'SCHEDULED'
                    );
                    
                    instance_counter := instance_counter + 1;
                    
                    -- Debug output for first few flights
                    IF instance_counter <= 1010 THEN
                        DBMS_OUTPUT.PUT_LINE('Flight ' || instance_id_var || ': ' || 
                            TO_CHAR(departure_time, 'YYYY-MM-DD HH24:MI') || ' -> ' || 
                            TO_CHAR(arrival_time, 'YYYY-MM-DD HH24:MI'));
                    END IF;
                    
                EXCEPTION
                    WHEN OTHERS THEN
                        DBMS_OUTPUT.PUT_LINE('Error creating flight instance IAT' || instance_counter || ': ' || SQLERRM);
                END;
            END LOOP;
        END LOOP;
        
        -- Show progress every 30 days
        IF MOD(current_date - current_dt, 30) = 0 THEN
            DBMS_OUTPUT.PUT_LINE('  Processed up to: ' || TO_CHAR(current_date, 'YYYY-MM-DD') || ' | Flight instances created: ' || instance_counter);
            COMMIT;
        END IF;
        
        current_date := current_date + 1;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Flight instances created: ' || (instance_counter - 1000) || ' total flights');
    DBMS_OUTPUT.PUT_LINE('✓ Date range: ' || TO_CHAR(current_dt, 'YYYY-MM-DD') || ' to ' || TO_CHAR(end_dt, 'YYYY-MM-DD'));
    DBMS_OUTPUT.PUT_LINE('✓ All flights use quarter-hour timings (00, 15, 30, 45 minutes)');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Error in flight instance creation: ' || SQLERRM);
        ROLLBACK;
        RAISE;
END;
/

-- -----------------------------
-- 12. CREATE APP USERS AND SAMPLE BOOKINGS (UPDATED FOR NEW SCHEMA - IMPROVED)
-- -----------------------------
DECLARE
    payment_counter NUMBER := 1000;
    reservation_counter NUMBER := 1000;
    user_counter NUMBER := 1;
    successful_bookings NUMBER := 0;
    
    -- Sample user data
    TYPE user_rec IS RECORD (
        first_name VARCHAR2(50),
        last_name VARCHAR2(50),
        email VARCHAR2(100),
        phone VARCHAR2(20),
        dob DATE,
        gender VARCHAR2(20),
        passport VARCHAR2(20),
        password_hash VARCHAR2(256)
    );
    
    TYPE user_table IS TABLE OF user_rec;
    users user_table;
    
BEGIN
    DBMS_OUTPUT.PUT_LINE('Creating app users and sample bookings...');
    
    -- Define sample users (with simple password hash for demo)
    users := user_table(
        user_rec('Ali', 'Khan', 'ali.khan@example.com', '03001234567', DATE '1985-05-15', 'MALE', 'AB1234567', 'hashed_password_1'),
        user_rec('Ayesha', 'Ahmed', 'ayesha.ahmed@example.com', '03007654321', DATE '1990-08-22', 'FEMALE', 'CD2345678', 'hashed_password_2'),
        user_rec('Usman', 'Malik', 'usman.malik@example.com', '03009876543', DATE '1988-03-10', 'MALE', 'EF3456789', 'hashed_password_3'),
        user_rec('Fatima', 'Raza', 'fatima.raza@example.com', '03005556677', DATE '1992-11-05', 'FEMALE', 'GH4567890', 'hashed_password_4'),
        user_rec('Bilal', 'Shah', 'bilal.shah@example.com', '03003334455', DATE '1987-07-18', 'MALE', 'IJ5678901', 'hashed_password_5'),
        user_rec('Sara', 'Iqbal', 'sara.iqbal@example.com', '03002223344', DATE '1995-01-30', 'FEMALE', 'KL6789012', 'hashed_password_6'),
        user_rec('Ahmed', 'Hassan', 'ahmed.hassan@example.com', '03004445566', DATE '1983-09-12', 'MALE', 'MN7890123', 'hashed_password_7'),
        user_rec('Zainab', 'Akhtar', 'zainab.akhtar@example.com', '03007778899', DATE '1991-04-25', 'FEMALE', 'OP8901234', 'hashed_password_8')
    );
    
    -- First create App_Users
    FOR i IN 1..users.COUNT LOOP
        INSERT INTO App_User (User_ID, Email, Password_Hash, Phone_Number, Created_At)
        VALUES (user_counter, users(i).email, users(i).password_hash, users(i).phone, SYSTIMESTAMP - DBMS_RANDOM.VALUE(1, 365));
        user_counter := user_counter + 1;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Created ' || (user_counter - 1) || ' app users');
    
    -- Now create sample bookings - try until we get 3 successful ones
    WHILE successful_bookings < 3 LOOP
        DECLARE
            instance_id_var VARCHAR2(20);
            route_id_var VARCHAR2(10);
            class_id_var VARCHAR2(10);
            base_price NUMBER;
            final_price NUMBER;
            user_index NUMBER;
            booking_id_var VARCHAR2(6);
            passenger_id_var NUMBER;
            reservation_id_var VARCHAR2(20);
            payment_id_var VARCHAR2(20);
            row_num NUMBER;
            seat_letter CHAR(1);
            model_id_var VARCHAR2(20);
            user_id_var NUMBER;
            title_var VARCHAR2(10);
            pricing_found BOOLEAN := FALSE;
            seat_found BOOLEAN := FALSE;
        BEGIN
            DBMS_OUTPUT.PUT_LINE('=== Attempting Booking ' || (successful_bookings + 1) || ' ===');
            
            -- STEP 1: Get a random flight instance that has pricing
            BEGIN
                SELECT fi.Instance_ID, fi.Route_ID, fi.Model_ID 
                INTO instance_id_var, route_id_var, model_id_var
                FROM (
                    SELECT fi.Instance_ID, fi.Route_ID, fi.Model_ID
                    FROM Flight_Instance fi
                    WHERE fi.Departure_Time > SYSTIMESTAMP
                    AND EXISTS (
                        SELECT 1 FROM Route_Pricing rp 
                        WHERE rp.Route_ID = fi.Route_ID
                        AND rp.Valid_From <= TRUNC(SYSDATE) 
                        AND rp.Valid_To >= TRUNC(SYSDATE)
                    )
                    ORDER BY DBMS_RANDOM.VALUE
                ) fi
                WHERE ROWNUM = 1;
                
                DBMS_OUTPUT.PUT_LINE('Found flight with pricing: ' || instance_id_var || ', Route: ' || route_id_var || ', Model: ' || model_id_var);
            EXCEPTION
                WHEN NO_DATA_FOUND THEN
                    DBMS_OUTPUT.PUT_LINE('No upcoming flights with pricing found. Trying again...');
                    CONTINUE;
            END;
            
            -- STEP 2: Get pricing for this route
            BEGIN
                SELECT Class_ID, Base_Price
                INTO class_id_var, base_price
                FROM (
                    SELECT rp.Class_ID, rp.Base_Price
                    FROM Route_Pricing rp
                    WHERE rp.Route_ID = route_id_var
                    AND rp.Valid_From <= TRUNC(SYSDATE) 
                    AND rp.Valid_To >= TRUNC(SYSDATE)
                    AND EXISTS (
                        SELECT 1 FROM Aircraft_Row_Class arc 
                        WHERE arc.Model_ID = model_id_var 
                        AND arc.Class_ID = rp.Class_ID
                    )
                    ORDER BY DBMS_RANDOM.VALUE
                ) 
                WHERE ROWNUM = 1;
                
                pricing_found := TRUE;
                DBMS_OUTPUT.PUT_LINE('Found class: ' || class_id_var || ', Base price: ' || base_price);
            EXCEPTION
                WHEN NO_DATA_FOUND THEN
                    DBMS_OUTPUT.PUT_LINE('No pricing found for route ' || route_id_var || '. Trying different flight...');
                    CONTINUE;
            END;
            
            IF NOT pricing_found THEN
                CONTINUE;
            END IF;
            
            -- Apply peak season multiplier for December (20% increase)
            IF EXTRACT(MONTH FROM SYSDATE) = 12 THEN
                final_price := base_price * 1.2;
            ELSE
                final_price := base_price;
            END IF;
            
            final_price := ROUND(final_price);
            DBMS_OUTPUT.PUT_LINE('Final price: ' || final_price);
            
            -- Select user
            user_index := MOD(successful_bookings, 8) + 1;
            user_id_var := user_index;
            
            -- Determine title based on gender
            IF users(user_index).gender = 'MALE' THEN
                title_var := 'MR';
            ELSE
                title_var := 'MS';
            END IF;
            
            -- STEP 3: Create booking (PNR will be auto-generated by trigger)
            BEGIN
                INSERT INTO Booking (Lead_User_ID, Booking_Date, Booking_Status, Contact_Email, Emergency_Phone)
                VALUES (user_id_var, SYSTIMESTAMP - DBMS_RANDOM.VALUE(1, 10), 'CONFIRMED', 
                       users(user_index).email, users(user_index).phone)
                RETURNING Booking_ID INTO booking_id_var;
                
                DBMS_OUTPUT.PUT_LINE('Created booking: ' || booking_id_var);
            EXCEPTION
                WHEN OTHERS THEN
                    DBMS_OUTPUT.PUT_LINE('Error creating booking: ' || SQLERRM);
                    CONTINUE;
            END;
            
            -- STEP 4: Create passenger (linked to user)
            BEGIN
                INSERT INTO Passenger (Linked_User_ID, Title, First_Name, Last_Name, Gender, Date_Of_Birth, Passport_Num)
                VALUES (user_id_var, title_var, users(user_index).first_name, users(user_index).last_name,
                       users(user_index).gender, users(user_index).dob, users(user_index).passport)
                RETURNING Passenger_ID INTO passenger_id_var;
                
                DBMS_OUTPUT.PUT_LINE('Created passenger: ' || passenger_id_var);
            EXCEPTION
                WHEN OTHERS THEN
                    DBMS_OUTPUT.PUT_LINE('Error creating passenger: ' || SQLERRM);
                    -- Clean up booking if passenger creation fails
                    DELETE FROM Booking WHERE Booking_ID = booking_id_var;
                    CONTINUE;
            END;
            
            -- STEP 5: Find available seat
            BEGIN
                SELECT Row_Number, Seat_Letter
                INTO row_num, seat_letter
                FROM (
                    SELECT arc.Row_Number, asm.Seat_Letter
                    FROM Aircraft_Row_Class arc
                    JOIN Aircraft_Seat_Map asm ON arc.Model_ID = asm.Model_ID AND arc.Row_Number = asm.Row_Number
                    WHERE arc.Model_ID = model_id_var
                    AND arc.Class_ID = class_id_var
                    AND NOT EXISTS (
                        SELECT 1 FROM Reservation r 
                        WHERE r.Instance_ID = instance_id_var 
                        AND r.Row_Number = arc.Row_Number 
                        AND r.Seat_Letter = asm.Seat_Letter
                    )
                    ORDER BY DBMS_RANDOM.VALUE
                ) 
                WHERE ROWNUM = 1;
                
                seat_found := TRUE;
                DBMS_OUTPUT.PUT_LINE('Found seat: Row ' || row_num || ', ' || seat_letter);
            EXCEPTION
                WHEN NO_DATA_FOUND THEN
                    DBMS_OUTPUT.PUT_LINE('No available seats found for class ' || class_id_var || '. Trying different flight...');
                    -- Clean up
                    DELETE FROM Passenger WHERE Passenger_ID = passenger_id_var;
                    DELETE FROM Booking WHERE Booking_ID = booking_id_var;
                    CONTINUE;
            END;
            
            IF NOT seat_found THEN
                CONTINUE;
            END IF;
            
            -- STEP 6: Create reservation
            BEGIN
                reservation_id_var := 'RES' || reservation_counter;
                INSERT INTO Reservation (Reservation_ID, Booking_ID, Passenger_ID, Instance_ID, Row_Number, Seat_Letter, Price_Charged, Ticket_Status)
                VALUES (reservation_id_var, booking_id_var, passenger_id_var, instance_id_var, row_num, seat_letter, final_price, 'ISSUED');
                
                DBMS_OUTPUT.PUT_LINE('Created reservation: ' || reservation_id_var);
                reservation_counter := reservation_counter + 1;
            EXCEPTION
                WHEN OTHERS THEN
                    DBMS_OUTPUT.PUT_LINE('Error creating reservation: ' || SQLERRM);
                    -- Clean up
                    DELETE FROM Passenger WHERE Passenger_ID = passenger_id_var;
                    DELETE FROM Booking WHERE Booking_ID = booking_id_var;
                    CONTINUE;
            END;
            
            -- STEP 7: Create payment
            BEGIN
                payment_id_var := 'PAY' || payment_counter;
                INSERT INTO Payment (Payment_ID, Booking_ID, Amount_Paid, Payment_Date, Payment_Method)
                VALUES (payment_id_var, booking_id_var, final_price, SYSTIMESTAMP, 'Credit Card');
                
                DBMS_OUTPUT.PUT_LINE('Created payment: ' || payment_id_var);
                payment_counter := payment_counter + 1;
            EXCEPTION
                WHEN OTHERS THEN
                    DBMS_OUTPUT.PUT_LINE('Error creating payment: ' || SQLERRM);
                    -- Clean up
                    DELETE FROM Reservation WHERE Reservation_ID = reservation_id_var;
                    DELETE FROM Passenger WHERE Passenger_ID = passenger_id_var;
                    DELETE FROM Booking WHERE Booking_ID = booking_id_var;
                    CONTINUE;
            END;
            
            successful_bookings := successful_bookings + 1;
            DBMS_OUTPUT.PUT_LINE('✓ Successfully completed booking ' || successful_bookings);
            
        EXCEPTION
            WHEN OTHERS THEN
                DBMS_OUTPUT.PUT_LINE('Unexpected error in booking attempt: ' || SQLERRM);
        END;
    END LOOP;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('✓ Sample bookings completed: ' || successful_bookings || ' successful bookings');
END;
/

-- -----------------------------
-- FINAL SUMMARY
-- -----------------------------
DECLARE
    v_countries NUMBER;
    v_states NUMBER;
    v_cities NUMBER;
    v_airports NUMBER;
    v_models NUMBER;
    v_routes NUMBER;
    v_instances NUMBER;
    v_users NUMBER;
    v_passengers NUMBER;
    v_bookings NUMBER;
    v_reservations NUMBER;
    v_payments NUMBER;
    v_pricings NUMBER;
    v_earliest_date DATE;
    v_latest_date DATE;
    
    -- Count seats by class for a sample aircraft
    v_first_seats NUMBER;
    v_business_seats NUMBER;
    v_economy_seats NUMBER;
    v_max_economy_row NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_countries FROM Country;
    SELECT COUNT(*) INTO v_states FROM State_Province;
    SELECT COUNT(*) INTO v_cities FROM City;
    SELECT COUNT(*) INTO v_airports FROM Airport;
    SELECT COUNT(*) INTO v_models FROM Aircraft_Model;
    SELECT COUNT(*) INTO v_routes FROM Flight_Route;
    SELECT COUNT(*) INTO v_instances FROM Flight_Instance;
    SELECT COUNT(*) INTO v_users FROM App_User;
    SELECT COUNT(*) INTO v_passengers FROM Passenger;
    SELECT COUNT(*) INTO v_bookings FROM Booking;
    SELECT COUNT(*) INTO v_reservations FROM Reservation;
    SELECT COUNT(*) INTO v_payments FROM Payment;
    SELECT COUNT(*) INTO v_pricings FROM Route_Pricing;
    
    SELECT MIN(TRUNC(Departure_Time)), MAX(TRUNC(Departure_Time)) 
    INTO v_earliest_date, v_latest_date FROM Flight_Instance;
    
    -- Count seats by travel class for a sample aircraft
    SELECT COUNT(*) INTO v_first_seats FROM Aircraft_Seat_Map WHERE Model_ID = 'A320' AND Row_Number BETWEEN 1 AND 4;
    SELECT COUNT(*) INTO v_business_seats FROM Aircraft_Seat_Map WHERE Model_ID = 'A320' AND Row_Number BETWEEN 5 AND 10;
    SELECT COUNT(*) INTO v_economy_seats FROM Aircraft_Seat_Map WHERE Model_ID = 'A320' AND Row_Number BETWEEN 11 AND 30;
    
    -- Get maximum economy row number
    SELECT MAX(Row_Number) INTO v_max_economy_row FROM Aircraft_Seat_Map WHERE Model_ID = 'A320' AND Row_Number BETWEEN 11 AND 30;
    
    DBMS_OUTPUT.PUT_LINE('=========================================');
    DBMS_OUTPUT.PUT_LINE('DATABASE POPULATION COMPLETE!');
    DBMS_OUTPUT.PUT_LINE('=========================================');
    DBMS_OUTPUT.PUT_LINE('Summary:');
    DBMS_OUTPUT.PUT_LINE('- Geographic Data:');
    DBMS_OUTPUT.PUT_LINE('  * Countries: ' || v_countries);
    DBMS_OUTPUT.PUT_LINE('  * States/Provinces: ' || v_states);
    DBMS_OUTPUT.PUT_LINE('  * Cities: ' || v_cities);
    DBMS_OUTPUT.PUT_LINE('- Airports: ' || v_airports);
    DBMS_OUTPUT.PUT_LINE('- Aircraft Models: ' || v_models);
    DBMS_OUTPUT.PUT_LINE('- Flight Routes: ' || v_routes);
    DBMS_OUTPUT.PUT_LINE('- Flight Instances: ' || v_instances);
    DBMS_OUTPUT.PUT_LINE('- App Users: ' || v_users);
    DBMS_OUTPUT.PUT_LINE('- Seat Configuration (per aircraft):');
    DBMS_OUTPUT.PUT_LINE('  * First Class: ' || v_first_seats || ' seats (Rows 1-4)');
    DBMS_OUTPUT.PUT_LINE('  * Business Class: ' || v_business_seats || ' seats (Rows 5-10)');
    DBMS_OUTPUT.PUT_LINE('  * Economy Class: ' || v_economy_seats || ' seats (Rows 11-' || v_max_economy_row || ')');
    DBMS_OUTPUT.PUT_LINE('- Passengers: ' || v_passengers);
    DBMS_OUTPUT.PUT_LINE('- Bookings: ' || v_bookings);
    DBMS_OUTPUT.PUT_LINE('- Reservations: ' || v_reservations);
    DBMS_OUTPUT.PUT_LINE('- Payments: ' || v_payments);
    DBMS_OUTPUT.PUT_LINE('- Route Pricings: ' || v_pricings);
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
    DBMS_OUTPUT.PUT_LINE('✓ ECONOMY CLASS NOW EXTENDS TO ROW ' || v_max_economy_row || 'F');
    DBMS_OUTPUT.PUT_LINE('✓ DATA NOW EXTENDS TO JAN 31, 2026');
    DBMS_OUTPUT.PUT_LINE('✓ UPDATED FOR NEW SCHEMA WITH SEPARATE APP_USER AND PASSENGER TABLES');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Completed at: ' || TO_CHAR(SYSTIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'));
    DBMS_OUTPUT.PUT_LINE('=========================================');
END;
/

COMMIT;