# Flight Booking System - Migration and Upgrade Guide

**Project:** IAT Airlines Flight Booking System  
**Version:** 2.0 - CNIC-Based Booking System  
**Date:** November 2025  
**Database:** Oracle 19c (XEPDB1)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current vs New Schema](#current-vs-new-schema)
3. [Migration Strategy](#migration-strategy)
4. [CRUD Operations](#crud-operations)
5. [Triggers & Business Rules](#triggers--business-rules)
6. [Testing Checklist](#testing-checklist)
7. [Rollback Procedures](#rollback-procedures)

---

## 1. Executive Summary

### Project Goals
- Replace auto-generated Passenger_ID with Pakistani CNIC (15 chars: 12345-1234567-1)
- Group multiple passengers under single Booking (instead of separate reservations)
- Implement Pay Now / Pay Later options
- Simplify payment status: UNPAID → PAID (no REFUNDED tracking)
- Support 24-hour cancellation policy
- Allow passengers to delete past UNPAID bookings
- Add stored procedures for CRUD operations
- Implement triggers for business rule enforcement

### Timeline
- **Phase 1:** Database Migration (2-3 days)
- **Phase 2:** Frontend Updates (2-3 days)  
- **Phase 3:** Backend Integration (3-4 days)

---

## 2. Current vs New Schema

### Current Schema (OLD)

```sql
Passenger (
    Passenger_ID VARCHAR2(255) PRIMARY KEY,  -- Auto-generated
    P_FirstName, P_LastName, P_Email, P_PhoneNumber,
    P_Address, P_City, P_State, P_Zipcode, P_Country
)

Reservation (
    Reservation_ID VARCHAR2(255) PRIMARY KEY,
    Passenger_ID FK,
    Seat_ID FK,
    Date_Of_Reservation DATE
)

Payment_Status (
    Payment_ID VARCHAR2(255) PRIMARY KEY,
    Payment_Status_YN CHAR(1),  -- 'Y' or 'N'
    Payment_Due_Date DATE,
    Payment_Amount NUMBER(10,2),
    Reservation_ID FK
)
```

**Problems:**
- Each passenger creates separate reservation (no grouping)
- Cannot identify lead passenger
- Payment tracked per reservation, not per booking group
- All payments marked 'Y' immediately (no unpaid state)

### New Schema (NEW)

```sql
Passenger (
    CNIC VARCHAR2(15) PRIMARY KEY,  -- Format: 12345-1234567-1
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
    Gender CHAR(1) CHECK (Gender IN ('M','F','O'))
)

Booking (
    Booking_ID VARCHAR2(20) PRIMARY KEY,
    Lead_Passenger_CNIC VARCHAR2(15) FK,
    Booking_Date TIMESTAMP,
    Total_Amount NUMBER(10,2),
    Payment_Status VARCHAR2(20) CHECK IN ('UNPAID','PAID','CANCELLED'),
    Booking_Status VARCHAR2(20) CHECK IN ('CONFIRMED','CANCELLED','COMPLETED'),
    Pay_Option VARCHAR2(20) CHECK IN ('PAY_NOW','PAY_LATER'),
    Trip_Type VARCHAR2(10) CHECK IN ('ONE_WAY','ROUND_TRIP'),
    Payment_Method VARCHAR2(50),
    Payment_Date TIMESTAMP,
    Cancellation_Date TIMESTAMP,
    Cancellation_Reason VARCHAR2(500)
)

Reservation (
    Reservation_ID VARCHAR2(20) PRIMARY KEY,
    Booking_ID VARCHAR2(20) FK ON DELETE CASCADE,
    Passenger_CNIC VARCHAR2(15) FK,
    Seat_ID VARCHAR2(20) FK,
    Flight_ID VARCHAR2(10) FK,
    Date_Of_Reservation TIMESTAMP,
    Reservation_Status VARCHAR2(20) CHECK IN ('ACTIVE','CANCELLED','CHANGED'),
    Seat_Cost NUMBER(10,2),
    Is_Outbound CHAR(1) CHECK IN ('Y','N')
)

Cancellation_Log (
    Cancellation_ID VARCHAR2(20) PRIMARY KEY,
    Booking_ID FK,
    Cancellation_Date TIMESTAMP,
    Cancelled_By_CNIC VARCHAR2(15) FK,
    Reason VARCHAR2(500),
    Original_Amount NUMBER(10,2),
    Refund_Eligible CHAR(1),
    Hours_Since_Booking NUMBER
)

Flight_Change_Log (
    Change_ID VARCHAR2(20) PRIMARY KEY,
    Booking_ID FK,
    Change_Date TIMESTAMP,
    Changed_By_CNIC VARCHAR2(15),
    Old_Flight_ID, New_Flight_ID VARCHAR2(10),
    Old_Seat_ID, New_Seat_ID VARCHAR2(20),
    Price_Difference NUMBER(10,2),
    Change_Fee NUMBER(10,2)
)
```

---

## 3. Migration Strategy

### Phase 1: Database Migration

**Step 1: Backup Existing Data**
```sql
-- Run: 01_backup_existing_data.sql
CREATE TABLE Passenger_BACKUP AS SELECT * FROM Passenger;
CREATE TABLE Reservation_BACKUP AS SELECT * FROM Reservation;
CREATE TABLE Payment_Status_BACKUP AS SELECT * FROM Payment_Status;
```

**Step 2: Drop Old Tables**
```sql
-- Run: 02_drop_old_tables.sql
DROP TABLE Payment_Status CASCADE CONSTRAINTS;
DROP TABLE Reservation CASCADE CONSTRAINTS;
DROP TABLE Passenger CASCADE CONSTRAINTS;
```

**Step 3: Create New Schema**
```sql
-- Run: 03_create_new_schema.sql
-- Creates Passenger, Booking, Reservation, Cancellation_Log, Flight_Change_Log
```

**Step 4: Create Stored Procedures**
```sql
-- Run: 04_create_procedures.sql
-- Creates all CRUD procedures
```

**Step 5: Create Triggers**
```sql
-- Run: 05_create_triggers.sql
-- Creates validation and business rule triggers
```

**Step 6: Create Indexes**
```sql
-- Run: 06_create_indexes.sql
-- Performance optimization indexes
```

**Step 7: Repopulate Data**
```sql
-- Run: 07_repopulate_data.sql
-- Sample passengers, bookings, reservations
```

### Automated Migration
```bash
# Run Python migration script
cd sql/migration
python migrate_database.py
```

---

## 4. CRUD Operations

### Passenger Operations

#### CREATE Passenger
```sql
CALL SP_CREATE_PASSENGER(
    p_cnic => '42101-1234567-1',
    p_fname => 'Ali',
    p_lname => 'Khan',
    p_email => 'ali@example.com',
    p_phone => '03001234567',
    p_address => 'House 10, Karachi',
    p_city => 'Karachi',
    p_state => 'Sindh',
    p_zipcode => '74400',
    p_country => 'Pakistan',
    p_dob => TO_DATE('1990-01-15', 'YYYY-MM-DD'),
    p_gender => 'M'
);
```

#### READ Passenger
```sql
DECLARE
    v_cursor SYS_REFCURSOR;
BEGIN
    SP_GET_PASSENGER('42101-1234567-1', v_cursor);
END;
```

#### UPDATE Passenger
```sql
CALL SP_UPDATE_PASSENGER(
    p_cnic => '42101-1234567-1',
    p_email => 'newemail@example.com',
    p_phone => '03009876543',
    p_address => 'New Address'
);
```

#### DELETE Passenger
```sql
-- Hard delete (use with caution)
DELETE FROM Passenger WHERE CNIC = '42101-1234567-1';
```

### Booking Operations

#### CREATE Booking
```sql
CALL SP_CREATE_BOOKING(
    p_booking_id => 'BKG20241119123456',
    p_lead_cnic => '42101-1234567-1',
    p_total_amount => 32000,
    p_pay_option => 'PAY_LATER',
    p_trip_type => 'ROUND_TRIP'
);
```

#### UPDATE Payment Status
```sql
CALL SP_UPDATE_PAYMENT_STATUS(
    p_booking_id => 'BKG20241119123456',
    p_payment_status => 'PAID',
    p_payment_method => 'Credit Card'
);
```

#### CANCEL Booking
```sql
DECLARE
    v_refund_eligible CHAR(1);
BEGIN
    SP_CANCEL_BOOKING(
        p_booking_id => 'BKG20241119123456',
        p_cnic => '42101-1234567-1',
        p_reason => 'Travel plans changed',
        p_refund_eligible => v_refund_eligible
    );
    DBMS_OUTPUT.PUT_LINE('Refund Eligible: ' || v_refund_eligible);
END;
```

#### DELETE Unpaid Bookings (User Selection)
```sql
CALL SP_DELETE_UNPAID_BOOKINGS(
    p_cnic => '42101-1234567-1',
    p_booking_ids => 'BKG001,BKG002,BKG003'  -- Comma-separated
);
```

### Reservation Operations

#### CREATE Reservation
```sql
CALL SP_CREATE_RESERVATION(
    p_res_id => 'RES20241119123456_1',
    p_booking_id => 'BKG20241119123456',
    p_cnic => '42101-1234567-1',
    p_seat_id => 'IAT1000-1A',
    p_flight_id => 'IAT1000',
    p_seat_cost => 16000,
    p_is_outbound => 'Y'
);
```

#### READ Booking with Reservations
```sql
SELECT 
    b.Booking_ID, b.Payment_Status, b.Total_Amount,
    r.Reservation_ID, r.Seat_ID, r.Seat_Cost,
    p.P_FirstName, p.P_LastName,
    f.Departure_Date_Time
FROM Booking b
JOIN Reservation r ON b.Booking_ID = r.Booking_ID
JOIN Passenger p ON r.Passenger_CNIC = p.CNIC
JOIN Flight_Details f ON r.Flight_ID = f.Flight_ID
WHERE b.Booking_ID = 'BKG20241119123456'
  AND r.Reservation_Status = 'ACTIVE';
```

### Lookup Operations

#### Get All Bookings for Passenger
```sql
DECLARE
    v_cursor SYS_REFCURSOR;
BEGIN
    SP_GET_PASSENGER_BOOKINGS('42101-1234567-1', v_cursor);
END;
```

#### Search by Booking ID
```sql
SELECT * FROM Booking WHERE Booking_ID = 'BKG20241119123456';
```

---

## 5. Triggers & Business Rules

### TRG_VALIDATE_CNIC_FORMAT
**Timing:** BEFORE INSERT OR UPDATE ON Passenger  
**Purpose:** Ensure CNIC follows format: 12345-1234567-1

```sql
IF NOT REGEXP_LIKE(:NEW.CNIC, '^\d{5}-\d{7}-\d$') THEN
    RAISE_APPLICATION_ERROR(-20010, 'Invalid CNIC format');
END IF;
```

### TRG_PREVENT_DOUBLE_BOOKING
**Timing:** BEFORE INSERT ON Reservation  
**Purpose:** Prevent booking same seat twice

```sql
SELECT COUNT(*) INTO v_count 
FROM Reservation 
WHERE Seat_ID = :NEW.Seat_ID AND Reservation_Status = 'ACTIVE';

IF v_count > 0 THEN
    RAISE_APPLICATION_ERROR(-20011, 'Seat already booked');
END IF;
```

### TRG_UPDATE_BOOKING_TOTAL
**Timing:** AFTER INSERT/UPDATE/DELETE ON Reservation  
**Purpose:** Auto-calculate Booking.Total_Amount

```sql
UPDATE Booking SET Total_Amount = (
    SELECT SUM(Seat_Cost) FROM Reservation 
    WHERE Booking_ID = :NEW.Booking_ID AND Reservation_Status = 'ACTIVE'
)
WHERE Booking_ID = :NEW.Booking_ID;
```

### TRG_AUTO_BOOKING_ID
**Timing:** BEFORE INSERT ON Booking  
**Purpose:** Generate Booking_ID if NULL

```sql
IF :NEW.Booking_ID IS NULL THEN
    :NEW.Booking_ID := 'BKG' || TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS');
END IF;
```

### TRG_AUTO_RESERVATION_ID
**Timing:** BEFORE INSERT ON Reservation  
**Purpose:** Generate Reservation_ID if NULL

```sql
IF :NEW.Reservation_ID IS NULL THEN
    :NEW.Reservation_ID := 'RES' || TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS');
END IF;
```

---

## 6. Testing Checklist

### Database Tests

- [ ] **Test 1:** Insert passenger with valid CNIC
  ```sql
  CALL SP_CREATE_PASSENGER('42101-1234567-1', 'Test', 'User', ...);
  -- Expected: SUCCESS
  ```

- [ ] **Test 2:** Insert passenger with invalid CNIC
  ```sql
  CALL SP_CREATE_PASSENGER('12345', 'Test', 'User', ...);
  -- Expected: ORA-20010 Invalid CNIC format
  ```

- [ ] **Test 3:** Create booking and verify total auto-calculates
  ```sql
  -- Create booking, add 2 reservations
  -- Verify: Booking.Total_Amount = sum of Seat_Cost
  ```

- [ ] **Test 4:** Try to book same seat twice
  ```sql
  -- Create reservation for seat IAT1000-1A
  -- Try to create another reservation for same seat
  -- Expected: ORA-20011 Seat already booked
  ```

- [ ] **Test 5:** Cancel booking within 24 hours
  ```sql
  -- Create booking with Booking_Date = SYSTIMESTAMP
  -- Call SP_CANCEL_BOOKING immediately
  -- Expected: Refund_Eligible = 'Y'
  ```

- [ ] **Test 6:** Try to cancel booking after 24 hours
  ```sql
  -- Create booking with Booking_Date = SYSTIMESTAMP - 2 days
  -- Call SP_CANCEL_BOOKING
  -- Expected: Refund_Eligible = 'N'
  ```

- [ ] **Test 7:** Update payment status
  ```sql
  CALL SP_UPDATE_PAYMENT_STATUS('BKG001', 'PAID', 'Credit Card');
  -- Verify: Payment_Status = 'PAID', Payment_Date = SYSTIMESTAMP
  ```

- [ ] **Test 8:** Delete unpaid bookings
  ```sql
  -- Create 3 unpaid bookings
  -- Call SP_DELETE_UNPAID_BOOKINGS with booking IDs
  -- Verify: Bookings deleted, reservations deleted (CASCADE)
  ```

- [ ] **Test 9:** Lookup bookings by CNIC
  ```sql
  CALL SP_GET_PASSENGER_BOOKINGS('42101-1234567-1', cursor);
  -- Verify: Returns all bookings for that passenger
  ```

- [ ] **Test 10:** Verify indexes created
  ```sql
  SELECT index_name, table_name FROM user_indexes 
  WHERE table_name IN ('BOOKING','RESERVATION','PASSENGER');
  ```

### Application Tests (After Backend Integration)

- [ ] Book 2 passengers, verify single Booking_ID created
- [ ] Test PAY_NOW flow → redirects to payment
- [ ] Test PAY_LATER flow → shows confirmation with UNPAID status
- [ ] Search booking by CNIC → shows all bookings
- [ ] Search booking by Booking_ID → shows exact match
- [ ] Manage booking → shows cancel button if within 24hrs
- [ ] Cancel booking within 24hrs → success
- [ ] Try to cancel after 24hrs → error message
- [ ] Delete unpaid past bookings → checkboxes work, deletion succeeds

---

## 7. Rollback Procedures

### If Migration Fails

**Step 1: Drop New Tables**
```sql
DROP TABLE Flight_Change_Log CASCADE CONSTRAINTS;
DROP TABLE Cancellation_Log CASCADE CONSTRAINTS;
DROP TABLE Reservation CASCADE CONSTRAINTS;
DROP TABLE Booking CASCADE CONSTRAINTS;
DROP TABLE Passenger CASCADE CONSTRAINTS;
```

**Step 2: Restore From Backup**
```sql
CREATE TABLE Passenger AS SELECT * FROM Passenger_BACKUP;
CREATE TABLE Reservation AS SELECT * FROM Reservation_BACKUP;
CREATE TABLE Payment_Status AS SELECT * FROM Payment_Status_BACKUP;

-- Recreate constraints
ALTER TABLE Passenger ADD CONSTRAINT PK_Passenger PRIMARY KEY (Passenger_ID);
ALTER TABLE Reservation ADD CONSTRAINT PK_Reservation PRIMARY KEY (Reservation_ID);
ALTER TABLE Reservation ADD CONSTRAINT FK_Res_Passenger 
    FOREIGN KEY (Passenger_ID) REFERENCES Passenger(Passenger_ID);
-- ... (add other constraints as needed)
```

**Step 3: Verify Data**
```sql
SELECT COUNT(*) FROM Passenger;
SELECT COUNT(*) FROM Reservation;
SELECT COUNT(*) FROM Payment_Status;
```

### If Issues Found After Go-Live

1. Document the issue with screenshots and error messages
2. Check `migration_log.txt` for any warnings during migration
3. Verify triggers are enabled: `SELECT trigger_name, status FROM user_triggers;`
4. Verify procedures compiled: `SELECT object_name, status FROM user_objects WHERE object_type='PROCEDURE';`
5. If data corruption, restore from backup taken before migration
6. Contact development team with issue details

---

## Quick Reference

### Key Changes Summary

| Aspect | Old | New |
|--------|-----|-----|
| Passenger PK | Auto-generated ID | CNIC (15 chars) |
| Booking Grouping | None | Booking table groups reservations |
| Payment Status | Y/N flag | UNPAID, PAID, CANCELLED |
| Pay Options | All immediate | PAY_NOW or PAY_LATER |
| Lead Passenger | Not tracked | Booking.Lead_Passenger_CNIC |
| Cancellation | Not supported | 24-hour window with refund eligibility |
| Delete Bookings | Not supported | Delete unpaid bookings via procedure |

### Important File Locations

- **Migration Scripts:** `sql/migration/`
- **Python Automation:** `sql/migration/migrate_database.py`
- **Documentation:** `docs/`
- **Backup Tables:** `Passenger_BACKUP`, `Reservation_BACKUP`, `Payment_Status_BACKUP`

### Support Contacts

- **Database Issues:** DBA Team
- **Application Issues:** Backend Development Team  
- **Frontend Issues:** Frontend Development Team

---

**End of Migration Guide**
