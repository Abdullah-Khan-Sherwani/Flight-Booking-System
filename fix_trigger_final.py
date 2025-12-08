#!/usr/bin/env python3
"""
Final fix for the reciprocal family trigger - simple and clean version
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
        print("FINAL FIX FOR RECIPROCAL FAMILY TRIGGER")
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
        
        # Create clean statement-level trigger
        print("\n2. Creating new statement-level trigger (AFTER STATEMENT)...")
        
        trigger_sql = """
CREATE OR REPLACE TRIGGER TRG_AUTO_RECIPROCAL_FAMILY
AFTER UPDATE OF Status ON User_Family
BEGIN
    -- This trigger runs once per statement (not per row)
    -- It processes all ACCEPTED relationships and creates their reciprocals
    FOR row_data IN (
        SELECT User_ID, Family_User_ID, Relationship
        FROM User_Family
        WHERE Status = 'ACCEPTED'
    )
    LOOP
        DECLARE
            v_exists NUMBER;
        BEGIN
            -- Check if reciprocal already exists in ACCEPTED state
            SELECT COUNT(*) INTO v_exists
            FROM User_Family
            WHERE User_ID = row_data.Family_User_ID
            AND Family_User_ID = row_data.User_ID
            AND Status = 'ACCEPTED';
            
            -- If reciprocal doesn't exist in ACCEPTED state, update or create it
            IF v_exists = 0 THEN
                BEGIN
                    -- Try to update an existing PENDING or REJECTED relationship
                    UPDATE User_Family
                    SET Status = 'ACCEPTED', Relationship = row_data.Relationship
                    WHERE User_ID = row_data.Family_User_ID
                    AND Family_User_ID = row_data.User_ID;
                    
                    -- If no row was updated, insert a new one
                    IF SQL%ROWCOUNT = 0 THEN
                        INSERT INTO User_Family 
                        (User_ID, Family_User_ID, Relationship, Status, Created_At)
                        VALUES (row_data.Family_User_ID, row_data.User_ID, 
                                row_data.Relationship, 'ACCEPTED', SYSTIMESTAMP);
                    END IF;
                EXCEPTION WHEN DUP_VAL_ON_INDEX THEN
                    -- Silently ignore duplicate key errors
                    NULL;
                END;
            END IF;
        END;
    END LOOP;
END
"""
        
        cursor.execute(trigger_sql)
        print("   ✓ New statement-level trigger created")
        
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
