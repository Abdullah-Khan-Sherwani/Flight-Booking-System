-- ============================================================================
-- FIX: Allow cancelled seats to be re-booked
-- 
-- Problem: The UQ_Seat_Instance constraint prevents booking a seat that exists
-- in a cancelled reservation. Even though we filter cancelled seats in queries,
-- the unique constraint still blocks new inserts.
--
-- Solution: Replace the unique CONSTRAINT with a function-based unique INDEX
-- that only applies to non-cancelled reservations.
--
-- Run this script in SQL*Plus or Oracle SQL Developer
-- ============================================================================

-- Step 1: Drop the existing unique constraint
-- (May fail if constraint doesn't exist - that's OK)
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE Reservation DROP CONSTRAINT UQ_Seat_Instance';
    DBMS_OUTPUT.PUT_LINE('Dropped constraint UQ_Seat_Instance');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Constraint UQ_Seat_Instance not found or already dropped: ' || SQLERRM);
END;
/

-- Step 2: Drop any existing index with the same name
BEGIN
    EXECUTE IMMEDIATE 'DROP INDEX IDX_Seat_Instance_Active';
    DBMS_OUTPUT.PUT_LINE('Dropped index IDX_Seat_Instance_Active');
EXCEPTION
    WHEN OTHERS THEN
        DBMS_OUTPUT.PUT_LINE('Index IDX_Seat_Instance_Active not found or already dropped: ' || SQLERRM);
END;
/

-- Step 3: Create a function-based unique index
-- This index only includes rows where Ticket_Status != 'CANCELLED'
-- Using CASE WHEN to create a conditional unique index
CREATE UNIQUE INDEX IDX_Seat_Instance_Active ON Reservation (
    CASE WHEN Ticket_Status != 'CANCELLED' THEN Instance_ID END,
    CASE WHEN Ticket_Status != 'CANCELLED' THEN Row_Number END,
    CASE WHEN Ticket_Status != 'CANCELLED' THEN Seat_Letter END
);

COMMIT;

-- Verify the index was created
SELECT index_name, uniqueness 
FROM user_indexes 
WHERE table_name = 'RESERVATION' 
AND index_name = 'IDX_SEAT_INSTANCE_ACTIVE';

PROMPT
PROMPT ========================================
PROMPT FIX APPLIED SUCCESSFULLY!
PROMPT ========================================
PROMPT The unique constraint UQ_Seat_Instance has been replaced with a 
PROMPT function-based unique index IDX_Seat_Instance_Active that only 
PROMPT applies to non-cancelled reservations.
PROMPT
PROMPT Cancelled seats can now be re-booked.
PROMPT ========================================
