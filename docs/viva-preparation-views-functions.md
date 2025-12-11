# 📚 Viva Preparation: Views and Functions in `database-3NF.sql`

This guide covers all views and functions in your Flight Booking System database with detailed explanations, key concepts, and potential viva questions.

---

## 👁️ VIEWS

### 1. `View_Flight_Availability` (Line 357-373)

**Purpose:** Shows real-time seat availability for each flight without storing calculated data (which would violate 3NF).

```sql
CREATE OR REPLACE VIEW View_Flight_Availability AS
SELECT 
    F.Instance_ID,
    F.Route_ID,
    F.Departure_Time,
    (SELECT COUNT(*) FROM Aircraft_Seat_Map WHERE Model_ID = F.Model_ID) AS Total_Capacity,
    (SELECT COUNT(*) FROM Reservation WHERE Instance_ID = F.Instance_ID 
     AND Row_Number IS NOT NULL AND Ticket_Status != 'CANCELLED') AS Seats_Booked,
    (SELECT ...) - (SELECT ...) AS Seats_Remaining
FROM Flight_Instance F;
```

**How It Works:**
1. **Total_Capacity**: Counts all physical seats in the aircraft model using a correlated subquery
2. **Seats_Booked**: Counts non-cancelled reservations that have a seat assigned (excludes lap infants who have `Row_Number IS NULL`)
3. **Seats_Remaining**: Simple subtraction of booked from total

**Key Concepts:**
- **Correlated Subquery**: Each subquery references `F.Model_ID` or `F.Instance_ID` from the outer query
- **3NF Compliance**: We don't store `Seats_Remaining` in a column because it's a **derived attribute** (calculated from other data)
- **Virtual Table**: Views don't store data; they compute results on-the-fly

**Potential Viva Questions:**

> **Q: Why not just add a `Seats_Remaining` column to `Flight_Instance`?**
> 
> **A:** That would violate 3NF because it's a calculated value. If someone books a seat but we forget to decrement the counter, the data becomes inconsistent. Views guarantee consistency by always computing from source data.

---

### 2. `View_Booking_Infant_Summary` (Line 618-631)

**Purpose:** Provides a summary of each booking showing the breakdown of passenger types and pricing.

```sql
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
```

**How It Works:**
1. Joins Booking → Reservation → Flight_Instance
2. Uses **conditional aggregation** with `CASE WHEN` inside `COUNT()` and `SUM()`
3. `Total_Price` includes all prices (even $0 for lap infants)
4. `Paid_Amount` excludes lap infant prices (they're free)

**Key Concepts:**
- **Conditional Aggregation**: `COUNT(CASE WHEN ... THEN 1 END)` only counts rows matching the condition
- **GROUP BY**: Aggregates results per booking per flight

**Potential Viva Questions:**

> **Q: Why do you have both `Total_Price` and `Paid_Amount`?**
>
> **A:** `Total_Price` shows the theoretical total including $0 for lap infants. `Paid_Amount` shows what the customer actually pays. This helps in reporting and verification.

---

### 3. `View_Past_Passengers` (Line 647-693)

**Purpose:** Enables the "Add from past bookings" feature by showing all passengers a user has previously booked.

```sql
CREATE OR REPLACE VIEW View_Past_Passengers AS
SELECT 
    p.Passenger_ID, p.First_Name, p.Last_Name, p.Title, ...
    b.Lead_User_ID, b.Booking_ID, b.Booking_Date,
    r.Reservation_ID, r.Ticket_Status, r.Passenger_Type,
    fi.Instance_ID, fi.Departure_Time,
    fr.Source_Airport, fr.Dest_Airport,
    dep_apt.Airport_Name, arr_apt.Airport_Name
FROM Passenger p
JOIN Reservation r ON p.Passenger_ID = r.Passenger_ID
JOIN Booking b ON r.Booking_ID = b.Booking_ID
JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
JOIN Airport dep_apt ON fr.Source_Airport = dep_apt.Airport_ID
JOIN Airport arr_apt ON fr.Dest_Airport = arr_apt.Airport_ID
WHERE b.Lead_User_ID IS NOT NULL;
```

**How It Works:**
1. **6-table JOIN** chain: Passenger → Reservation → Booking → Flight_Instance → Flight_Route → Airport (twice)
2. Returns complete travel history with passenger and flight details
3. Filters to only include bookings made by logged-in users (`Lead_User_ID IS NOT NULL`)

**Key Concepts:**
- **Self-Join on Airport**: Joins `Airport` table twice (as `dep_apt` and `arr_apt`) to get both departure and arrival airport names
- **Denormalized Output**: The view "flattens" data from 6 tables for easy consumption

**Potential Viva Questions:**

> **Q: Why join Airport twice?**
>
> **A:** Because `Flight_Route` has two foreign keys to `Airport` (Source_Airport and Dest_Airport). To get both airport names, we need two separate joins with different aliases.

---

## 🔧 FUNCTIONS

### 1. `Generate_PNR` (Line 291-306)

**Purpose:** Generates a unique 6-character alphanumeric booking reference (PNR = Passenger Name Record).

```sql
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
        EXIT WHEN v_count = 0;  -- Exit loop when unique PNR found
    END LOOP;
    RETURN v_pnr;
END;
```

**How It Works:**
1. Uses `DBMS_RANDOM.VALUE` to pick random positions from the character set
2. Builds a 6-character string by concatenating random characters
3. Checks if PNR already exists in `Booking` table
4. Loops until it finds a unique PNR

**Key Concepts:**
- **LOOP with EXIT WHEN**: Repeats until condition is met
- **DBMS_RANDOM**: Oracle built-in package for random number generation
- **Collision Handling**: Guarantees uniqueness by checking database

**Potential Viva Questions:**

> **Q: What happens if all possible PNRs are taken?**
>
> **A:** With 36^6 = 2.17 billion possible combinations, this is practically impossible for a flight booking system. However, in a real production system, you might add a counter or fallback mechanism.

---

### 2. `FN_Get_Infant_Type` (Line 536-574)

**Purpose:** Determines whether an infant should be a LAP_INFANT (free, on parent's lap) or SEATED_INFANT (50% price, own seat).

```sql
CREATE OR REPLACE FUNCTION FN_Get_Infant_Type(
    p_Booking_ID   IN VARCHAR2,
    p_Instance_ID  IN VARCHAR2,
    p_Passenger_ID IN NUMBER
) RETURN VARCHAR2 IS
    v_Adult_Count NUMBER;
    v_Lap_Infant_Count NUMBER;
    v_Title VARCHAR2(10);
BEGIN
    -- Check if actually an infant
    SELECT Title INTO v_Title FROM Passenger WHERE Passenger_ID = p_Passenger_ID;
    IF v_Title != 'INF' THEN RETURN 'ADULT'; END IF;
    
    -- Count adults in this booking for this flight
    SELECT COUNT(*) INTO v_Adult_Count ...
    
    -- Count existing lap infants
    SELECT COUNT(*) INTO v_Lap_Infant_Count ...
    
    -- Rule: 1 lap infant per adult maximum
    IF v_Lap_Infant_Count < v_Adult_Count THEN
        RETURN 'LAP_INFANT';  -- Free
    ELSE
        RETURN 'SEATED_INFANT';  -- 50% price
    END IF;
END;
```

**How It Works:**
1. First checks if the passenger is actually an infant (Title = 'INF')
2. Counts adults already in the booking for this flight
3. Counts lap infants already booked
4. **Business Rule**: Maximum 1 lap infant per adult. If exceeded, infant needs their own seat.

**Key Concepts:**
- **Business Logic in Database**: Ensures consistent rule enforcement regardless of application
- **Encapsulation**: All infant-type logic in one reusable function

**Potential Viva Questions:**

> **Q: Why is this logic in the database and not the application?**
>
> **A:** Database functions ensure consistency across all applications (web, mobile, API). If a mobile app and web app both book flights, they both enforce the same rule.

---

### 3. `FN_Get_Infant_Price` (Line 579-615)

**Purpose:** Calculates the price for an infant based on their type.

```sql
CREATE OR REPLACE FUNCTION FN_Get_Infant_Price(
    p_Instance_ID  IN VARCHAR2,
    p_Infant_Type  IN VARCHAR2,
    p_Class_ID     IN VARCHAR2 DEFAULT 'ECO'
) RETURN NUMBER IS
BEGIN
    -- LAP_INFANT is always FREE
    IF p_Infant_Type = 'LAP_INFANT' THEN
        RETURN 0;
    END IF;
    
    -- SEATED_INFANT: 50% of base price
    IF p_Infant_Type = 'SEATED_INFANT' THEN
        SELECT Base_Price * 0.5 INTO result FROM Route_Pricing WHERE ...;
        RETURN result;
    END IF;
    
    RETURN 0;  -- Default
EXCEPTION
    WHEN NO_DATA_FOUND THEN RETURN 0;
END;
```

**How It Works:**
1. LAP_INFANT → Returns 0 (free, no seat)
2. SEATED_INFANT → Looks up base price from `Route_Pricing` and returns 50%
3. Handles missing pricing data gracefully

**Key Concepts:**
- **EXCEPTION Handling**: `NO_DATA_FOUND` prevents crashes if pricing isn't configured
- **Temporal Pricing**: Uses `SYSDATE BETWEEN Valid_From AND Valid_To` for time-valid pricing

**Potential Viva Questions:**

> **Q: Why does the function have a DEFAULT parameter for Class_ID?**
>
> **A:** If the caller doesn't specify a class, it defaults to 'ECO' (Economy). This provides convenience while allowing override for business/first class.

---

### 4. `FN_Calculate_Refund` (Line 1012-1043)

**Purpose:** Calculates refund amount based on how many hours remain until flight departure.

```sql
CREATE OR REPLACE FUNCTION FN_Calculate_Refund(
    p_Instance_ID  IN VARCHAR2,
    p_Price_Charged IN NUMBER
) RETURN NUMBER IS
    v_Departure_Time TIMESTAMP;
    v_Hours_Until_Departure NUMBER;
BEGIN
    SELECT Departure_Time INTO v_Departure_Time
    FROM Flight_Instance WHERE Instance_ID = p_Instance_ID;
    
    -- Calculate hours until departure
    v_Hours_Until_Departure := (CAST(v_Departure_Time AS DATE) - CAST(SYSTIMESTAMP AS DATE)) * 24;
    
    -- Apply refund policy
    IF v_Hours_Until_Departure > 24 THEN
        RETURN p_Price_Charged * 0.80;  -- 80% refund
    ELSE
        RETURN 0;  -- No refund
    END IF;
EXCEPTION
    WHEN NO_DATA_FOUND THEN RETURN 0;
END;
```

**How It Works:**
1. Fetches departure time for the flight
2. Calculates hours remaining: `(Departure - Now) * 24`
3. **Refund Policy**:
   - More than 24 hours before departure: **80% refund**
   - 24 hours or less: **0% refund (no refund)**

**Key Concepts:**
- **TIMESTAMP Arithmetic**: Subtracting dates gives days; multiply by 24 for hours
- **SYSTIMESTAMP**: Current date/time including timezone

**Potential Viva Questions:**

> **Q: Why is the refund policy based on departure time, not booking time?**
>
> **A:** Customer-friendly policy. A customer who booked 6 months ago shouldn't lose their refund just because they booked early. What matters is how close to the flight they're cancelling.

---

### 5. `FN_Get_Booking_Total` (Line 1399-1410)

**Purpose:** Returns the total price of all reservations in a booking.

```sql
CREATE OR REPLACE FUNCTION FN_Get_Booking_Total(
    p_Booking_ID IN VARCHAR2
) RETURN NUMBER IS
    v_Total NUMBER(10,2);
BEGIN
    SELECT NVL(SUM(Price_Charged), 0) INTO v_Total
    FROM Reservation
    WHERE Booking_ID = p_Booking_ID;
    
    RETURN v_Total;
END;
```

**How It Works:**
1. Sums all `Price_Charged` values from reservations in the booking
2. Uses `NVL(..., 0)` to return 0 instead of NULL if no reservations exist

**Key Concepts:**
- **NVL Function**: Null Value Logic - replaces NULL with a default value
- **Aggregate Function**: `SUM()` adds up all values

**Potential Viva Questions:**

> **Q: Why use NVL instead of just SUM?**
>
> **A:** If no reservations exist for a booking, `SUM()` returns NULL (not 0). `NVL(SUM(...), 0)` ensures we always return a number, preventing NULL-related bugs in calling code.

---

## 🎯 Quick Reference Summary

| Object | Key Purpose | Key SQL Concept |
|---|---|---|
| `View_Flight_Availability` | Real-time seat availability | Correlated subqueries, 3NF compliance |
| `View_Booking_Infant_Summary` | Passenger type breakdown | Conditional aggregation with CASE |
| `View_Past_Passengers` | Travel history for re-booking | Multi-table JOIN, self-join on Airport |
| `Generate_PNR` | Unique booking reference | DBMS_RANDOM, collision detection loop |
| `FN_Get_Infant_Type` | Lap vs seated infant logic | Business rule encapsulation |
| `FN_Get_Infant_Price` | Infant pricing (0% or 50%) | Exception handling, temporal pricing |
| `FN_Calculate_Refund` | Departure-based refund | TIMESTAMP arithmetic, policy enforcement |
| `FN_Get_Booking_Total` | Sum of reservation prices | NVL for NULL handling, aggregation |

---

## 📝 General Viva Tips

1. **Always explain WHY** - Don't just describe what the code does, explain the design decision
2. **Mention normalization** - Show you understand why derived values are in views, not tables
3. **Talk about consistency** - Business logic in database ensures all apps follow same rules
4. **Exception handling** - Show you handle edge cases (NO_DATA_FOUND, NULL values)
5. **Performance awareness** - Views compute on-the-fly vs stored procedures for complex operations

Good luck with your viva! 🍀
