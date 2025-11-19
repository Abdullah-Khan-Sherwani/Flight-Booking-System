-- ============================================
-- 01_BACKUP_EXISTING_DATA.SQL
-- Flight Booking System - Database Migration
-- Creates backup tables before migration
-- ============================================

SET SERVEROUTPUT ON;

BEGIN
    DBMS_OUTPUT.PUT_LINE('===========================================');
    DBMS_OUTPUT.PUT_LINE('CREATING BACKUP TABLES');
    DBMS_OUTPUT.PUT_LINE('Timestamp: ' || TO_CHAR(SYSTIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'));
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

-- Backup Passenger Table
BEGIN
    EXECUTE IMMEDIATE 'CREATE TABLE Passenger_BACKUP AS SELECT * FROM Passenger';
    DBMS_OUTPUT.PUT_LINE('✓ Passenger backup created');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('ERROR backing up Passenger: ' || SQLERRM);
END;
/

-- Backup Reservation Table
BEGIN
    EXECUTE IMMEDIATE 'CREATE TABLE Reservation_BACKUP AS SELECT * FROM Reservation';
    DBMS_OUTPUT.PUT_LINE('✓ Reservation backup created');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('ERROR backing up Reservation: ' || SQLERRM);
END;
/

-- Backup Payment_Status Table
BEGIN
    EXECUTE IMMEDIATE 'CREATE TABLE Payment_Status_BACKUP AS SELECT * FROM Payment_Status';
    DBMS_OUTPUT.PUT_LINE('✓ Payment_Status backup created');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('ERROR backing up Payment_Status: ' || SQLERRM);
END;
/

-- Verify Backups
DECLARE
    v_passenger_count NUMBER;
    v_reservation_count NUMBER;
    v_payment_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_passenger_count FROM Passenger_BACKUP;
    SELECT COUNT(*) INTO v_reservation_count FROM Reservation_BACKUP;
    SELECT COUNT(*) INTO v_payment_count FROM Payment_Status_BACKUP;
    
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('BACKUP VERIFICATION:');
    DBMS_OUTPUT.PUT_LINE('Passenger records backed up: ' || v_passenger_count);
    DBMS_OUTPUT.PUT_LINE('Reservation records backed up: ' || v_reservation_count);
    DBMS_OUTPUT.PUT_LINE('Payment_Status records backed up: ' || v_payment_count);
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('✓ Backup completed successfully');
    DBMS_OUTPUT.PUT_LINE('===========================================');
END;
/

COMMIT;
