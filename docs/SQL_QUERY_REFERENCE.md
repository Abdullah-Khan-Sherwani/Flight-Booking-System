# SQL Query Reference - Flight Booking System

This document catalogs all SQL queries currently used in the Flight Booking System application (app.py).

---

## Flight Search Queries

### Get Airport City Name
**Location:** app.py lines 49-51, 53-54  
**Purpose:** Convert airport code to city name for display

```sql
SELECT AirportCity 
FROM Airport 
WHERE Airport_ID = :dept
```

**Parameters:**
- `:dept` - Airport code (e.g., 'KHI', 'LHE')

**Returns:** Single row with city name

---

### Search Flights
**Location:** app.py lines 63-75  
**Purpose:** Find available flights matching search criteria

```sql
SELECT f.Flight_ID,
       f.Source_Airport_ID,
       f.Destination_Airport_ID,
       TO_CHAR(f.Departure_Date_Time, 'YYYY-MM-DD HH24:MI'),
       TO_CHAR(f.Arrival_Date_Time, 'YYYY-MM-DD HH24:MI'),
       f.Airplane_Type,
       a1.AirportCity AS Source_City,
       a2.AirportCity AS Dest_City
FROM Flight_Details f
JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
WHERE f.Source_Airport_ID = :src
  AND f.Destination_Airport_ID = :dest
  AND TRUNC(f.Departure_Date_Time) = TO_DATE(:dep_date, 'YYYY-MM-DD')
```

**Explanation:**
- `JOIN Airport` twice to get source and destination city names
- `TRUNC(f.Departure_Date_Time)` removes time component for date-only comparison
- `TO_CHAR` formats datetime for display
- `TO_DATE(:dep_date, 'YYYY-MM-DD')` converts string input to date

**Parameters:**
- `:src` - Source airport code
- `:dest` - Destination airport code  
- `:dep_date` - Departure date (YYYY-MM-DD format)

---

## Return Flight Queries

### Get Flight Route Info
**Location:** app.py lines 141-145  
**Purpose:** Get source/destination for return flight search

```sql
SELECT Source_Airport_ID, Destination_Airport_ID 
FROM Flight_Details 
WHERE Flight_ID = :flight_id
```

### Search Return Flights
**Location:** app.py lines 154-167  
**Purpose:** Same as flight search, but for return journey

(Uses same query structure as Search Flights above)

---

## Seat Selection Queries

### Get Flight Details with Cities
**Location:** app.py lines 213-219, 224-230  
**Purpose:** Display flight information on seat selection page

```sql
SELECT f.Flight_ID, f.Airplane_Type, a1.AirportCity, a2.AirportCity,
       TO_CHAR(f.Departure_Date_Time, 'DD-MON-YYYY HH24:MI')
FROM Flight_Details f
JOIN Airport a1 ON f.Source_Airport_ID = a1.Airport_ID
JOIN Airport a2 ON f.Destination_Airport_ID = a2.Airport_ID
WHERE f.Flight_ID = :flight_id
```

**Explanation:**
- `TO_CHAR` with 'DD-MON-YYYY HH24:MI' formats date for display (e.g., "19-NOV-2025 14:30")

---

### Get Available Seats for Class
**Location:** app.py lines 233-241  
**Purpose:** Show seats available in selected travel class

```sql
SELECT s.Seat_ID, s.Travel_Class_ID, s.Row_Number, s.Seat_Letter,
       CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
FROM Seat_Details s
LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID AND r.Seat_ID LIKE :flight_pattern
WHERE s.Flight_ID = :flight_id 
  AND s.Travel_Class_ID = :travel_class
ORDER BY s.Row_Number, s.Seat_Letter
```

**Explanation:**
- `LEFT JOIN Reservation` includes all seats, even if not reserved
- `CASE WHEN r.Reservation_ID IS NULL` checks if seat has reservation
- `r.Seat_ID LIKE :flight_pattern` filters reservations for this flight
- `ORDER BY Row_Number, Seat_Letter` sorts seats logically

**Parameters:**
- `:flight_id` - Flight code
- `:travel_class` - Class code ('ECO', 'BUS', 'FIR')
- `:flight_pattern` - Pattern like 'IAT1000%'

---

### Get All Booked Seats (Any Class)
**Location:** app.py lines 244-249  
**Purpose:** Show which seats are unavailable on seat map

```sql
SELECT s.Row_Number, s.Seat_Letter
FROM Seat_Details s
JOIN Reservation r ON s.Seat_ID = r.Seat_ID
WHERE s.Flight_ID = :flight_id
```

**Explanation:**
- `JOIN` (INNER JOIN) only returns seats that have reservations
- Used to mark seats as unavailable regardless of class

---

### Get Seat Status for Flight
**Location:** app.py lines 368-378  
**Purpose:** AJAX endpoint for real-time seat availability

```sql
SELECT s.Seat_ID,
       CASE WHEN r.Reservation_ID IS NULL THEN 'available' ELSE 'booked' END as status
FROM Seat_Details s
LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID
WHERE s.Flight_ID = :flight_id
ORDER BY s.Seat_ID
```

---

## Passenger & Booking Creation Queries

### Insert Passenger
**Location:** app.py lines 527-532  
**Purpose:** Create new passenger record

```sql
INSERT INTO Passenger 
(Passenger_ID, P_FirstName, P_LastName, P_Email, P_PhoneNumber, 
 P_Address, P_City, P_State, P_Zipcode, P_Country)
VALUES (:id, :first_name, :last_name, :email, :phone, 
        :address, :city, :state, :postal_code, :country)
```

**Note:** Currently uses auto-generated Passenger_ID. Will change to CNIC in new schema.

---

### Check Seat Availability Before Booking
**Location:** app.py lines 551-555  
**Purpose:** Verify seat is not already booked

```sql
SELECT 1 FROM Seat_Details s 
LEFT JOIN Reservation r ON s.Seat_ID = r.Seat_ID 
WHERE s.Seat_ID = :seat_id AND r.Reservation_ID IS NULL
```

**Explanation:**
- Returns row only if seat exists AND has no reservation
- Used before INSERT to prevent double booking

---

### Insert Reservation
**Location:** app.py lines 558-562  
**Purpose:** Create seat reservation for passenger

```sql
INSERT INTO Reservation 
(Reservation_ID, Passenger_ID, Seat_ID, Date_Of_Reservation)
VALUES (:res_id, :pass_id, :seat_id, SYSDATE)
```

**Note:** `SYSDATE` captures current date/time

---

### Insert Payment Status
**Location:** app.py lines 571-575  
**Purpose:** Track payment for reservation

```sql
INSERT INTO Payment_Status 
(Payment_ID, Payment_Status_YN, Payment_Due_Date, Payment_Amount, Reservation_ID)
VALUES (:pay_id, 'Y', SYSDATE + 7, :amount, :res_id)
```

**Explanation:**
- `Payment_Status_YN` currently always set to 'Y' (paid)
- `SYSDATE + 7` sets due date 7 days in future
- In new schema, this changes to booking-level tracking

---

### Get Seat Cost
**Location:** app.py lines 505-507  
**Purpose:** Calculate booking total amount

```sql
SELECT Cost 
FROM Flight_Cost 
WHERE Seat_ID = :seat_id
```

**Explanation:**
- Flight_Cost table has different prices per seat (based on class/route)
- Used to calculate total booking amount

---

## Debug/Admin Queries

### List Database Tables
**Location:** app.py lines 698-705  
**Purpose:** Show all relevant tables for debugging

```sql
SELECT table_name 
FROM user_tables 
WHERE table_name LIKE '%AIRPORT%' 
   OR table_name LIKE '%FLIGHT%' 
   OR table_name LIKE '%SEAT%' 
   OR table_name LIKE '%PASSENGER%' 
   OR table_name LIKE '%RESERVATION%'
ORDER BY table_name
```

---

### Show Table Columns
**Location:** app.py lines 711-716  
**Purpose:** Display column structure for table

```sql
SELECT column_name, data_type 
FROM user_tab_columns 
WHERE table_name = '{table_name}' 
ORDER BY column_id
```

**Explanation:**
- `user_tab_columns` system view contains metadata
- `ORDER BY column_id` shows columns in definition order

---

### Show Table Constraints
**Location:** app.py lines 779-786  
**Purpose:** Display constraints for debugging

```sql
SELECT uc.constraint_name, uc.table_name, ucc.column_name, uc.constraint_type,
       uc.search_condition, uc.status
FROM user_constraints uc
JOIN user_cons_columns ucc ON uc.constraint_name = ucc.constraint_name
WHERE uc.table_name IN ('PASSENGER', 'RESERVATION', 'PAYMENT_STATUS', 'SEAT_DETAILS')
ORDER BY uc.table_name, uc.constraint_type
```

**Explanation:**
- `user_constraints` contains constraint definitions
- `user_cons_columns` links constraints to columns
- Used to troubleshoot constraint violations

---

## Query Patterns & Best Practices

### Using Bind Variables
All queries use bind variables (`:parameter_name`) instead of string concatenation:

```python
# GOOD - Uses bind variable
cursor.execute("SELECT * FROM Flight WHERE Flight_ID = :id", id=flight_id)

# BAD - SQL injection risk
cursor.execute(f"SELECT * FROM Flight WHERE Flight_ID = '{flight_id}'")
```

### LEFT JOIN vs INNER JOIN

- **LEFT JOIN:** Include all rows from left table even if no match
  - Used for seat availability (show all seats, even if not reserved)
  
- **INNER JOIN:** Only include rows with matches in both tables
  - Used for booked seats (only show seats that have reservations)

### Date Handling

- `SYSDATE` - Current database date/time
- `SYSTIMESTAMP` - Current date/time with timezone (more precise)
- `TRUNC(date)` - Remove time component
- `TO_DATE(string, format)` - Convert string to date
- `TO_CHAR(date, format)` - Convert date to formatted string

### Transaction Management

```python
try:
    # Execute queries
    cursor.execute("INSERT ...")
    cursor.execute("UPDATE ...")
    conn.commit()  # Save changes
except Exception as e:
    conn.rollback()  # Undo changes on error
finally:
    cursor.close()
    conn.close()
```

---

## Changes in New Schema

The following queries will need modification:

1. **Passenger Insert** - Use CNIC instead of Passenger_ID
2. **Reservation Insert** - Add Booking_ID foreign key
3. **Payment Tracking** - Move to Booking level
4. **Seat Availability** - Check Reservation_Status = 'ACTIVE'

Refer to MIGRATION_AND_UPGRADE_GUIDE.md for new query examples.

---

**End of SQL Query Reference**
