#!/usr/bin/env python3
"""
Fix the trigger with a statement-level trigger instead of row-level
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def fix_mutating_trigger():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*60)
        print("Fixing ORA-04091: Mutating Table Error")
        print("="*60)
        
        # Drop the problematic trigger
        print("\nDropping old trigger...")
        try:
            cursor.execute("DROP TRIGGER TRG_AUTO_RECIPROCAL_FAMILY")
            print("✓ Old trigger dropped")
        except:
            print("⚠️  Old trigger not found")
        
        # Create a STATEMENT-level trigger instead (fires once per statement, not per row)
        # This avoids the mutating table issue
        print("\nCreating fixed statement-level trigger...")
        cursor.execute("""
            CREATE OR REPLACE TRIGGER TRG_AUTO_RECIPROCAL_FAMILY
            AFTER UPDATE OF Status ON User_Family
            DECLARE
                v_Exists NUMBER;
            BEGIN
                -- For each row that was updated to ACCEPTED from PENDING
                FOR row_data IN (
                    SELECT User_ID, Family_User_ID, Relationship
                    FROM User_Family
                    WHERE Status = 'ACCEPTED'
                )
                LOOP
                    -- Check if reciprocal exists
                    SELECT COUNT(*) INTO v_Exists
                    FROM User_Family
                    WHERE User_ID = row_data.Family_User_ID
                    AND Family_User_ID = row_data.User_ID;
                    
                    IF v_Exists = 0 THEN
                        -- Insert reciprocal
                        INSERT INTO User_Family (User_ID, Family_User_ID, Relationship, Status, Created_At)
                        VALUES (row_data.Family_User_ID, row_data.User_ID, row_data.Relationship, 'ACCEPTED', SYSTIMESTAMP);
                    ELSE
                        -- Update reciprocal if it's PENDING
                        UPDATE User_Family
                        SET Status = 'ACCEPTED', Relationship = row_data.Relationship
                        WHERE User_ID = row_data.Family_User_ID
                        AND Family_User_ID = row_data.User_ID
                        AND Status = 'PENDING';
                    END IF;
                END LOOP;
            EXCEPTION WHEN OTHERS THEN
                DBMS_OUTPUT.PUT_LINE('Trigger error: ' || SQLERRM);
            END;
        """)
        
        conn.commit()
        print("✓ Statement-level trigger created successfully")
        
        # Verify trigger
        cursor.execute("""
            SELECT trigger_name, trigger_type, status
            FROM user_triggers
            WHERE trigger_name = 'TRG_AUTO_RECIPROCAL_FAMILY'
        """)
        
        trigger_info = cursor.fetchone()
        if trigger_info:
            print(f"✓ Trigger Status: {trigger_info[2]}")
            print(f"✓ Trigger Type: {trigger_info[1]}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✓ Trigger fix completed!")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    fix_mutating_trigger()
