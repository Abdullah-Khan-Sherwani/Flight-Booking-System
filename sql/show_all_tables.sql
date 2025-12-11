-- ============================================================================
-- SHOW TABLE DATA - User, Booking & Financial Tables
-- Run this script in SQL*Plus or Oracle SQL Developer
-- ============================================================================

SET LINESIZE 200
SET PAGESIZE 50
SET COLSEP ' | '

-- ============================================================================
-- USER & AUTHENTICATION
-- ============================================================================

PROMPT
PROMPT ========================================
PROMPT TABLE: App_User
PROMPT ========================================
SELECT User_ID, Email, Phone_Number, Created_At FROM App_User;

PROMPT
PROMPT ========================================
PROMPT TABLE: User_Family
PROMPT ========================================
SELECT * FROM User_Family;

-- ============================================================================
-- BOOKING & PASSENGER DATA
-- ============================================================================

PROMPT
PROMPT ========================================
PROMPT TABLE: Passenger
PROMPT ========================================
SELECT * FROM Passenger;

PROMPT
PROMPT ========================================
PROMPT TABLE: Booking
PROMPT ========================================
SELECT * FROM Booking;

PROMPT
PROMPT ========================================
PROMPT TABLE: Reservation
PROMPT ========================================
SELECT * FROM Reservation;

-- ============================================================================
-- FINANCIAL & LOGS
-- ============================================================================

PROMPT
PROMPT ========================================
PROMPT TABLE: Payment
PROMPT ========================================
SELECT * FROM Payment;

PROMPT
PROMPT ========================================
PROMPT TABLE: Cancellation_Log
PROMPT ========================================
SELECT * FROM Cancellation_Log;

-- ============================================================================
-- VIEWS
-- ============================================================================

PROMPT
PROMPT ========================================
PROMPT VIEW: View_Booking_Infant_Summary
PROMPT ========================================
SELECT * FROM View_Booking_Infant_Summary;

PROMPT
PROMPT ========================================
PROMPT Done! All selected tables displayed.
PROMPT ========================================
