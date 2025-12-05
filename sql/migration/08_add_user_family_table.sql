-- Migration: Add User_Family table for family relationships
-- Date: 2024-12-05
-- Purpose: Enable family member linking between App_User accounts
--
-- This migration is idempotent - safe to run multiple times.

-- Check if table exists and create if not
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = 'USER_FAMILY';
    
    IF v_count = 0 THEN
        -- Create the User_Family table
        EXECUTE IMMEDIATE '
            CREATE TABLE User_Family (
                User_ID        NUMBER NOT NULL,
                Family_User_ID NUMBER NOT NULL,
                Relationship   VARCHAR2(30),
                Status         VARCHAR2(20) DEFAULT ''PENDING'' NOT NULL
                               CHECK (Status IN (''PENDING'', ''ACCEPTED'', ''REJECTED'')),
                Created_At     TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                
                CONSTRAINT PK_User_Family PRIMARY KEY (User_ID, Family_User_ID),
                CONSTRAINT FK_User_Family_User 
                    FOREIGN KEY (User_ID) REFERENCES App_User(User_ID) ON DELETE CASCADE,
                CONSTRAINT FK_User_Family_Family_User 
                    FOREIGN KEY (Family_User_ID) REFERENCES App_User(User_ID) ON DELETE CASCADE,
                CONSTRAINT CK_User_Family_No_Self 
                    CHECK (User_ID != Family_User_ID)
            )
        ';
        
        DBMS_OUTPUT.PUT_LINE('Created User_Family table');
    ELSE
        DBMS_OUTPUT.PUT_LINE('User_Family table already exists - skipping creation');
    END IF;
END;
/

-- Create index for efficient lookup (idempotent)
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM user_indexes WHERE index_name = 'IDX_USER_FAMILY_FAMILY_USER';
    
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_User_Family_Family_User ON User_Family(Family_User_ID, Status)';
        DBMS_OUTPUT.PUT_LINE('Created index IDX_User_Family_Family_User');
    ELSE
        DBMS_OUTPUT.PUT_LINE('Index already exists - skipping creation');
    END IF;
END;
/

-- Verify the table structure
SELECT column_name, data_type, nullable 
FROM user_tab_columns 
WHERE table_name = 'USER_FAMILY'
ORDER BY column_id;

-- Show constraints
SELECT constraint_name, constraint_type, status 
FROM user_constraints 
WHERE table_name = 'USER_FAMILY';

COMMIT;

-- Success message
BEGIN
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('=================================================');
    DBMS_OUTPUT.PUT_LINE('Migration completed successfully!');
    DBMS_OUTPUT.PUT_LINE('User_Family table is ready for use.');
    DBMS_OUTPUT.PUT_LINE('=================================================');
END;
/
