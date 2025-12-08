-- ============================================================================
-- IAT AIRLINES - DATABASE VERIFICATION QUERIES
-- Run these queries AFTER conducting tests on the website
-- ============================================================================

-- ============================================================================
-- SECTION 1: FAMILY MEMBER VERIFICATION
-- ============================================================================

-- 1.1: Check all family relationships
SELECT 
    uf.User_ID,
    u1.Email as "From User",
    uf.Family_User_ID,
    u2.Email as "Family Member",
    uf.Relationship,
    uf.Status,
    uf.Created_At
FROM User_Family uf
JOIN App_User u1 ON uf.User_ID = u1.User_ID
JOIN App_User u2 ON uf.Family_User_ID = u2.User_ID
ORDER BY uf.Created_At DESC;

-- 1.2: Check reciprocal relationships were created (TRG_Auto_Reciprocal_Family)
SELECT 
    CASE WHEN Status = 'ACCEPTED' THEN '✓ RECIPROCAL CREATED' ELSE '✗ NOT RECIPROCAL' END as Status_Check,
    User_ID,
    Family_User_ID,
    Status
FROM User_Family
WHERE Status = 'ACCEPTED'
ORDER BY User_ID, Family_User_ID;

-- 1.3: Verify family member was used in booking
-- (Check if passenger is linked to family member's user account)
SELECT 
    b.Booking_ID,
    b.Lead_User_ID,
    p.Passenger_ID,
    p.First_Name || ' ' || p.Last_Name as Passenger_Name,
    p.Linked_User_ID,
    CASE WHEN p.Linked_User_ID IS NOT NULL THEN '✓ LINKED TO USER' ELSE '✗ NOT LINKED' END as Link_Status
FROM Booking b
JOIN Reservation r ON b.Booking_ID = r.Booking_ID
JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
WHERE p.Linked_User_ID IS NOT NULL
ORDER BY b.Booking_ID DESC;

---
-- ============================================================================
-- SECTION 2: GUEST BOOKING VERIFICATION
-- ============================================================================

-- 2.1: Find guest bookings (Lead_User_ID IS NULL)
SELECT 
    b.Booking_ID,
    CASE WHEN b.Lead_User_ID IS NULL THEN '✓ GUEST BOOKING' ELSE '✗ ACCOUNT BOOKING' END as Booking_Type,
    b.Contact_Email,
    b.Emergency_Phone,
    b.Booking_Date,
    b.Booking_Status,
    COUNT(r.Reservation_ID) as Passenger_Count
FROM Booking b
LEFT JOIN Reservation r ON b.Booking_ID = r.Booking_ID
WHERE b.Lead_User_ID IS NULL
GROUP BY b.Booking_ID, b.Lead_User_ID, b.Contact_Email, b.Emergency_Phone, b.Booking_Date, b.Booking_Status
ORDER BY b.Booking_Date DESC;

-- 2.2: Guest booking details with passengers
SELECT 
    b.Booking_ID,
    b.Contact_Email as Guest_Email,
    p.First_Name || ' ' || p.Last_Name as Passenger_Name,
    p.Passport_Num,
    r.Reservation_ID,
    fi.Departure_Time,
    r.Row_Number,
    r.Seat_Letter,
    r.Price_Charged,
    r.Ticket_Status
FROM Booking b
JOIN Reservation r ON b.Booking_ID = r.Booking_ID
JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
WHERE b.Lead_User_ID IS NULL
ORDER BY b.Booking_Date DESC;

-- 2.3: Verify guest cannot have multiple accounts
SELECT 
    Contact_Email,
    COUNT(*) as Booking_Count,
    CASE WHEN COUNT(*) > 1 THEN '⚠️  MULTIPLE BOOKINGS' ELSE '✓ OK' END as Status
FROM Booking
WHERE Lead_User_ID IS NULL
GROUP BY Contact_Email
HAVING COUNT(*) >= 1
ORDER BY Booking_Count DESC;

---
-- ============================================================================
-- SECTION 3: CANCELLATION VERIFICATION
-- ============================================================================

-- 3.1: View all cancellations with refund amounts
SELECT 
    cl.Cancellation_Log_ID,
    cl.Booking_ID,
    cl.Reservation_ID,
    cl.Cancellation_Date,
    cl.Refund_Amount,
    r.Price_Charged as Original_Price,
    CASE 
        WHEN cl.Refund_Amount = r.Price_Charged THEN '✓ FULL REFUND'
        WHEN cl.Refund_Amount > 0 AND cl.Refund_Amount < r.Price_Charged THEN '⚠️  PARTIAL REFUND (fees deducted)'
        WHEN cl.Refund_Amount = 0 THEN '✗ NO REFUND (within 24 hours)'
        ELSE '⚠️  UNKNOWN'
    END as Refund_Status
FROM Cancellation_Log cl
JOIN Reservation r ON cl.Reservation_ID = r.Reservation_ID
ORDER BY cl.Cancellation_Date DESC;

-- 3.2: Check cancellation rules based on time to departure
SELECT 
    cl.Cancellation_Date,
    cl.Booking_ID,
    cl.Reservation_ID,
    fi.Departure_Time,
    ROUND((fi.Departure_Time - cl.Cancellation_Date) * 24) as Hours_Before_Departure,
    cl.Refund_Amount,
    r.Price_Charged,
    CASE 
        WHEN (fi.Departure_Time - cl.Cancellation_Date) * 24 > 48 THEN '✓ >48hrs: Full Refund'
        WHEN (fi.Departure_Time - cl.Cancellation_Date) * 24 BETWEEN 24 AND 48 THEN '⚠️  24-48hrs: 50% Refund'
        WHEN (fi.Departure_Time - cl.Cancellation_Date) * 24 < 24 THEN '✗ <24hrs: No Refund'
        ELSE 'ERROR'
    END as Expected_Refund_Rule
FROM Cancellation_Log cl
JOIN Reservation r ON cl.Reservation_ID = r.Reservation_ID
JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
ORDER BY cl.Cancellation_Date DESC;

-- 3.3: Verify booking status after cancellation
-- If ALL reservations cancelled → Booking should be CANCELLED
-- If SOME reservations cancelled → Booking should remain CONFIRMED
SELECT 
    b.Booking_ID,
    b.Booking_Status,
    COUNT(DISTINCT r.Reservation_ID) as Total_Reservations,
    SUM(CASE WHEN r.Ticket_Status = 'CANCELLED' THEN 1 ELSE 0 END) as Cancelled_Count,
    SUM(CASE WHEN r.Ticket_Status != 'CANCELLED' THEN 1 ELSE 0 END) as Active_Count,
    CASE 
        WHEN SUM(CASE WHEN r.Ticket_Status = 'CANCELLED' THEN 1 ELSE 0 END) = COUNT(DISTINCT r.Reservation_ID) 
            THEN '✓ ALL CANCELLED: Booking Status OK'
        WHEN SUM(CASE WHEN r.Ticket_Status = 'CANCELLED' THEN 1 ELSE 0 END) > 0 
            THEN '✓ PARTIAL CANCEL: Booking Status OK'
        ELSE 'N/A'
    END as Validation
FROM Booking b
LEFT JOIN Reservation r ON b.Booking_ID = r.Booking_ID
WHERE b.Booking_Status IN ('CANCELLED', 'CONFIRMED')
GROUP BY b.Booking_ID, b.Booking_Status
ORDER BY b.Booking_ID DESC;

-- 3.4: Track refund vs original payment
SELECT 
    b.Booking_ID,
    p.Payment_ID,
    p.Amount_Paid as Original_Payment,
    SUM(cl.Refund_Amount) as Total_Refunds,
    (p.Amount_Paid - SUM(cl.Refund_Amount)) as Net_Retained,
    CASE 
        WHEN (p.Amount_Paid - SUM(cl.Refund_Amount)) > 0 THEN '✓ Fees Applied: ' || (p.Amount_Paid - SUM(cl.Refund_Amount)) || ' PKR'
        ELSE '✓ Full Refund'
    END as Fee_Status
FROM Payment p
JOIN Booking b ON p.Booking_ID = b.Booking_ID
LEFT JOIN Cancellation_Log cl ON b.Booking_ID = cl.Booking_ID
WHERE b.Booking_Status = 'CANCELLED'
GROUP BY b.Booking_ID, p.Payment_ID, p.Amount_Paid
ORDER BY b.Booking_ID DESC;

---
-- ============================================================================
-- SECTION 4: RESCHEDULING VERIFICATION
-- ============================================================================

-- 4.1: Check all rescheduled reservations
SELECT 
    r.Reservation_ID,
    r.Booking_ID,
    p.First_Name || ' ' || p.Last_Name as Passenger,
    r.Ticket_Status,
    fi.Instance_ID,
    fi.Departure_Time,
    r.Row_Number || r.Seat_Letter as Seat,
    r.Price_Charged,
    CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN '✓ RESCHEDULED' ELSE '✗ NOT RESCHEDULED' END as Status
FROM Reservation r
JOIN Passenger p ON r.Passenger_ID = p.Passenger_ID
JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
WHERE r.Ticket_Status = 'RESCHEDULED'
ORDER BY r.Booking_ID DESC;

-- 4.2: Find reservations with price changes (indicating rescheduling)
-- Group by booking to see price before/after reschedule
SELECT 
    b.Booking_ID,
    b.Booking_Status,
    COUNT(r.Reservation_ID) as Reservation_Count,
    SUM(CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN 1 ELSE 0 END) as Rescheduled_Count,
    SUM(CASE WHEN r.Ticket_Status = 'ISSUED' THEN 1 ELSE 0 END) as Active_Count,
    SUM(r.Price_Charged) as Total_Current_Charges,
    CASE 
        WHEN SUM(CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN 1 ELSE 0 END) > 0 
            THEN '✓ HAS RESCHEDULED PASSENGERS'
        ELSE '✗ NO RESCHEDULING'
    END as Reschedule_Status
FROM Booking b
LEFT JOIN Reservation r ON b.Booking_ID = r.Booking_ID
WHERE b.Booking_Status = 'CONFIRMED'
GROUP BY b.Booking_ID, b.Booking_Status
HAVING SUM(CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN 1 ELSE 0 END) > 0
ORDER BY b.Booking_ID DESC;

-- 4.3: Trace rescheduling changes for a specific booking
-- (Shows old and new flight details if available)
SELECT 
    r.Reservation_ID,
    r.Ticket_Status,
    fi.Instance_ID,
    fi.Departure_Time,
    fr.Source_Airport || ' → ' || fr.Dest_Airport as Route,
    r.Row_Number || r.Seat_Letter as Seat_Assignment,
    r.Price_Charged as Current_Price
FROM Reservation r
JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
JOIN Flight_Route fr ON fi.Route_ID = fr.Route_ID
WHERE r.Booking_ID = '&BOOKING_ID'  -- Replace with actual booking ID
ORDER BY r.Reservation_ID;

-- 4.4: Calculate change fees (500 PKR per rescheduled passenger)
SELECT 
    b.Booking_ID,
    COUNT(DISTINCT CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN r.Passenger_ID END) as Rescheduled_Passengers,
    COUNT(DISTINCT CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN r.Passenger_ID END) * 500 as Expected_Change_Fee,
    p.Amount_Paid as Total_Payment,
    CASE 
        WHEN (COUNT(DISTINCT CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN r.Passenger_ID END) * 500) <= p.Amount_Paid - SUM(r.Price_Charged)
            THEN '✓ CHANGE FEE INCLUDED'
        ELSE '⚠️  FEE MAY BE MISSING'
    END as Fee_Status
FROM Booking b
JOIN Reservation r ON b.Booking_ID = r.Booking_ID
JOIN Payment p ON b.Booking_ID = p.Booking_ID
GROUP BY b.Booking_ID, p.Amount_Paid
ORDER BY b.Booking_ID DESC;

---
-- ============================================================================
-- SECTION 5: COMPREHENSIVE BOOKING AUDIT
-- ============================================================================

-- 5.1: Complete booking lifecycle view
SELECT 
    b.Booking_ID,
    b.Lead_User_ID,
    CASE WHEN b.Lead_User_ID IS NULL THEN '👤 GUEST' ELSE '👤 ACCOUNT' END as User_Type,
    b.Booking_Date,
    b.Booking_Status,
    COUNT(DISTINCT r.Reservation_ID) as Total_Passengers,
    SUM(CASE WHEN r.Ticket_Status = 'ISSUED' THEN 1 ELSE 0 END) as Active_Passengers,
    SUM(CASE WHEN r.Ticket_Status = 'CANCELLED' THEN 1 ELSE 0 END) as Cancelled_Passengers,
    SUM(CASE WHEN r.Ticket_Status = 'RESCHEDULED' THEN 1 ELSE 0 END) as Rescheduled_Passengers,
    SUM(r.Price_Charged) as Total_Revenue,
    COUNT(DISTINCT cl.Cancellation_Log_ID) as Cancellations,
    COALESCE(SUM(cl.Refund_Amount), 0) as Total_Refunded
FROM Booking b
LEFT JOIN Reservation r ON b.Booking_ID = r.Booking_ID
LEFT JOIN Cancellation_Log cl ON b.Booking_ID = cl.Booking_ID
GROUP BY b.Booking_ID, b.Lead_User_ID, b.Booking_Date, b.Booking_Status
ORDER BY b.Booking_Date DESC
LIMIT 20;

-- 5.2: Summary statistics
SELECT 
    COUNT(DISTINCT b.Booking_ID) as Total_Bookings,
    SUM(CASE WHEN b.Lead_User_ID IS NULL THEN 1 ELSE 0 END) as Guest_Bookings,
    SUM(CASE WHEN b.Lead_User_ID IS NOT NULL THEN 1 ELSE 0 END) as Account_Bookings,
    SUM(CASE WHEN b.Booking_Status = 'CONFIRMED' THEN 1 ELSE 0 END) as Active_Bookings,
    SUM(CASE WHEN b.Booking_Status = 'CANCELLED' THEN 1 ELSE 0 END) as Cancelled_Bookings,
    COUNT(DISTINCT r.Reservation_ID) as Total_Passengers,
    ROUND(SUM(r.Price_Charged), 2) as Total_Revenue,
    ROUND(COALESCE(SUM(cl.Refund_Amount), 0), 2) as Total_Refunded,
    ROUND(SUM(r.Price_Charged) - COALESCE(SUM(cl.Refund_Amount), 0), 2) as Net_Revenue
FROM Booking b
LEFT JOIN Reservation r ON b.Booking_ID = r.Booking_ID
LEFT JOIN Cancellation_Log cl ON b.Booking_ID = cl.Booking_ID;

---
-- ============================================================================
-- SECTION 6: TRIGGER VERIFICATION
-- ============================================================================

-- 6.1: Verify PNR generation trigger (TRG_Generate_Booking_PNR)
SELECT 
    b.Booking_ID,
    LENGTH(b.Booking_ID) as PNR_Length,
    CASE 
        WHEN REGEXP_LIKE(b.Booking_ID, '^[A-Z0-9]{6}$') THEN '✓ VALID 6-CHAR ALPHANUMERIC PNR'
        ELSE '✗ INVALID PNR FORMAT'
    END as PNR_Validation
FROM Booking b
ORDER BY b.Booking_ID DESC
LIMIT 20;

-- 6.2: Verify reciprocal family relationship trigger
SELECT 
    uf1.User_ID,
    uf1.Family_User_ID,
    uf1.Status,
    uf2.User_ID as Reciprocal_User_ID,
    uf2.Family_User_ID as Reciprocal_Family_ID,
    uf2.Status as Reciprocal_Status,
    CASE 
        WHEN uf1.Status = 'ACCEPTED' AND uf2.Status = 'ACCEPTED' THEN '✓ RECIPROCAL OK'
        WHEN uf1.Status != uf2.Status THEN '✗ MISMATCH'
        ELSE 'ℹ️  PENDING'
    END as Reciprocal_Check
FROM User_Family uf1
LEFT JOIN User_Family uf2 ON uf1.Family_User_ID = uf2.User_ID 
    AND uf1.User_ID = uf2.Family_User_ID
WHERE uf1.Status = 'ACCEPTED'
ORDER BY uf1.User_ID;

---
-- ============================================================================
-- HOW TO USE THESE QUERIES
-- ============================================================================
-- 1. Copy each query section
-- 2. Run in SQL Developer with your flight_app_user connection
-- 3. Check results against expected outcomes
-- 4. Note any anomalies or issues
-- 5. Take screenshots of results for your report
