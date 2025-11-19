-- ============================================
-- 02_DROP_OLD_TABLES.SQL
-- Flight Booking System - Database Migration
-- Drops old tables to prepare for new schema
-- ============================================

SET SERVEROUTPUT ON;

BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('DROPPING OLD TABLES');
    DBMS_OUTPUT.PUT_LINE('WARNING: This will delete existing data!');
    DBMS_OUTPUT.PUT_LINE('Backup tables: Passenger_BACKUP, Reservation_BACKUP, Payment_Status_BACKUP');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

-- Drop Payment_Status (has FK to Reservation)
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE Payment_Status CASCADE CONSTRAINTS';
    DBMS_OUTPUT.PUT_LINE('✓ Payment_Status table dropped');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -942 THEN -- Table does not exist
            DBMS_OUTPUT.PUT_LINE('  Payment_Status table does not exist (already dropped)');
        ELSE
            DBMS_OUTPUT.PUT_LINE('ERROR dropping Payment_Status: ' || SQLERRM);
            RAISE;
        END IF;
END;
/

-- Drop Reservation (has FK to Passenger and Seat_Details)
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE Reservation CASCADE CONSTRAINTS';
    DBMS_OUTPUT.PUT_LINE('✓ Reservation table dropped');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -942 THEN
            DBMS_OUTPUT.PUT_LINE('  Reservation table does not exist (already dropped)');
        ELSE
            DBMS_OUTPUT.PUT_LINE('ERROR dropping Reservation: ' || SQLERRM);
            RAISE;
        END IF;
END;
/

-- Drop Passenger
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE Passenger CASCADE CONSTRAINTS';
    DBMS_OUTPUT.PUT_LINE('✓ Passenger table dropped');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -942 THEN
            DBMS_OUTPUT.PUT_LINE('  Passenger table does not exist (already dropped)');
        ELSE
            DBMS_OUTPUT.PUT_LINE('ERROR dropping Passenger: ' || SQLERRM);
            RAISE;
        END IF;
END;
/

BEGIN
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('✓ Old tables dropped successfully');
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('ROLLBACK INSTRUCTIONS:');
    DBMS_OUTPUT.PUT_LINE('If you need to restore, run:');
    DBMS_OUTPUT.PUT_LINE('  CREATE TABLE Passenger AS SELECT * FROM Passenger_BACKUP;');
    DBMS_OUTPUT.PUT_LINE('  CREATE TABLE Reservation AS SELECT * FROM Reservation_BACKUP;');
    DBMS_OUTPUT.PUT_LINE('  CREATE TABLE Payment_Status AS SELECT * FROM Payment_Status_BACKUP;');
    DBMS_OUTPUT.PUT_LINE('  Then recreate constraints manually.');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

COMMIT;
