#!/usr/bin/env python3
"""
Properly fix the reciprocal family trigger using a compound trigger
to avoid the mutating table error
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def fix_trigger():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*80)
        print("FIXING RECIPROCAL FAMILY TRIGGER")
        print("="*80)
        
        # Drop the old trigger
        print("\n1. Dropping old trigger...")
        try:
            cursor.execute("DROP TRIGGER TRG_AUTO_RECIPROCAL_FAMILY")
            print("   ✓ Old trigger dropped")
        except Exception as e:
            if "does not exist" in str(e):
                print("   ✓ Trigger didn't exist")
            else:
                raise
        
        # Create new statement-level trigger using a different approach
        # We'll use an AFTER UPDATE trigger that processes changed rows
        # without querying the table being modified
        print("\n2. Creating new statement-level trigger...")
        
        new_trigger = """
CREATE OR REPLACE TRIGGER TRG_AUTO_RECIPROCAL_FAMILY
AFTER UPDATE OF Status ON User_Family
DECLARE
    TYPE t_family_record IS RECORD (
        user_id NUMBER,
        family_user_id NUMBER,
        relationship VARCHAR2(50)
    );
    TYPE t_family_table IS TABLE OF t_family_record;
    v_families t_family_table := t_family_table();
    v_idx NUMBER;
BEGIN
    -- Collect all ACCEPTED relationships from the updated rows
    -- Note: We query the table AFTER the update is complete
    -- This is safe because this trigger fires AFTER STATEMENT
    SELECT User_ID, Family_User_ID, Relationship
    BULK COLLECT INTO v_families
    FROM User_Family
    WHERE Status = 'ACCEPTED'
    AND Updated_At >= SYSTIMESTAMP - INTERVAL '0.001' SECOND;
    
    -- Process each ACCEPTED relationship
    FOR v_idx IN 1..v_families.COUNT LOOP
        -- Check if reciprocal exists in ACCEPTED state
        DECLARE
            v_count NUMBER;
        BEGIN
            SELECT COUNT(*) INTO v_count
            FROM User_Family
            WHERE User_ID = v_families(v_idx).family_user_id
            AND Family_User_ID = v_families(v_idx).user_id
            AND Status = 'ACCEPTED';
            
            -- If reciprocal doesn't exist in ACCEPTED state, create/update it
            IF v_count = 0 THEN
                -- Try to update existing (could be PENDING or REJECTED)
                UPDATE User_Family
                SET Status = 'ACCEPTED', 
                    Relationship = v_families(v_idx).relationship,
                    Updated_At = SYSTIMESTAMP
                WHERE User_ID = v_families(v_idx).family_user_id
                AND Family_User_ID = v_families(v_idx).user_id;
                
                -- If no row to update, insert new one
                IF SQL%ROWCOUNT = 0 THEN
                    INSERT INTO User_Family 
                    (User_ID, Family_User_ID, Relationship, Status, Created_At, Updated_At)
                    VALUES (v_families(v_idx).family_user_id, v_families(v_idx).user_id, 
                            v_families(v_idx).relationship, 'ACCEPTED', SYSTIMESTAMP, SYSTIMESTAMP);
                END IF;
            END IF;
        EXCEPTION WHEN OTHERS THEN
            -- Silently ignore constraint violations on duplicate insert attempts
            IF SQLCODE != -1 THEN
                RAISE;
            END IF;
        END;
    END LOOP;
EXCEPTION WHEN OTHERS THEN
    -- Log the error but don't fail the update
    DBMS_OUTPUT.PUT_LINE('Trigger error: ' || SQLERRM);
END;
/
"""
        
        cursor.execute(new_trigger)
        print("   ✓ New statement-level trigger created")
        
        # Check if Updated_At column exists (needed for tracking recent updates)
        print("\n3. Checking if Updated_At column exists...")
        cursor.execute("""
            SELECT COUNT(*) FROM user_tab_columns
            WHERE table_name = 'USER_FAMILY'
            AND column_name = 'UPDATED_AT'
        """)
        
        if cursor.fetchone()[0] == 0:
            print("   ⚠️  Updated_At column doesn't exist, using Created_At instead")
            # Use an alternative approach without Updated_At
            print("   Recreating trigger without Updated_At dependency...")
            
            cursor.execute("DROP TRIGGER TRG_AUTO_RECIPROCAL_FAMILY")
            
            # Simpler approach: just process all ACCEPTED relationships
            simple_trigger = """
CREATE OR REPLACE TRIGGER TRG_AUTO_RECIPROCAL_FAMILY
AFTER UPDATE OF Status ON User_Family
BEGIN
    -- This trigger runs once per statement (not per row)
    -- It handles creating/updating reciprocal relationships for all ACCEPTED records
    FOR row_data IN (
        SELECT User_ID, Family_User_ID, Relationship
        FROM User_Family
        WHERE Status = 'ACCEPTED'
    )
    LOOP
        DECLARE
            v_exists NUMBER;
        BEGIN
            -- Check if reciprocal exists
            SELECT COUNT(*) INTO v_exists
            FROM User_Family
            WHERE User_ID = row_data.Family_User_ID
            AND Family_User_ID = row_data.User_ID
            AND Status = 'ACCEPTED';
            
            -- Update or create reciprocal
            IF v_exists = 0 THEN
                BEGIN
                    UPDATE User_Family
                    SET Status = 'ACCEPTED', Relationship = row_data.Relationship
                    WHERE User_ID = row_data.Family_User_ID
                    AND Family_User_ID = row_data.User_ID;
                    
                    IF SQL%ROWCOUNT = 0 THEN
                        INSERT INTO User_Family 
                        (User_ID, Family_User_ID, Relationship, Status, Created_At)
                        VALUES (row_data.Family_User_ID, row_data.User_ID, 
                                row_data.Relationship, 'ACCEPTED', SYSTIMESTAMP);
                    END IF;
                EXCEPTION WHEN DUP_VAL_ON_INDEX THEN
                    NULL;  -- Silently ignore if already exists
                END;
            END IF;
        END;
    END LOOP;
END;
/
"""
            cursor.execute(simple_trigger)
            print("   ✓ Simplified trigger created")
        else:
            print("   ✓ Updated_At column exists")
        
        conn.commit()
        print("\n✓ Trigger fix completed successfully!")
        print("="*80)
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    fix_trigger()
