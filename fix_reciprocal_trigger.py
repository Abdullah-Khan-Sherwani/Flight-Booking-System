#!/usr/bin/env python3
"""
Fix the TRG_Auto_Reciprocal_Family trigger with better logic
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
        
        print("="*60)
        print("Fixing TRG_Auto_Reciprocal_Family trigger")
        print("="*60)
        
        # Drop the old trigger
        print("\nDropping old trigger...")
        try:
            cursor.execute("DROP TRIGGER TRG_Auto_Reciprocal_Family")
            print("✓ Old trigger dropped")
        except:
            print("⚠️  Old trigger not found (that's ok)")
        
        # Create the fixed trigger
        print("\nCreating fixed trigger...")
        cursor.execute("""
            CREATE OR REPLACE TRIGGER TRG_Auto_Reciprocal_Family
            AFTER UPDATE OF Status ON User_Family
            FOR EACH ROW
            WHEN (NEW.Status = 'ACCEPTED' AND OLD.Status = 'PENDING')
            BEGIN
                -- Insert reciprocal relationship if it doesn't exist
                MERGE INTO User_Family uf
                USING DUAL
                ON (uf.User_ID = :NEW.Family_User_ID AND uf.Family_User_ID = :NEW.User_ID)
                WHEN NOT MATCHED THEN
                    INSERT (User_ID, Family_User_ID, Relationship, Status, Created_At)
                    VALUES (:NEW.Family_User_ID, :NEW.User_ID, :NEW.Relationship, 'ACCEPTED', SYSTIMESTAMP)
                WHEN MATCHED THEN
                    UPDATE SET Status = 'ACCEPTED', 
                              Relationship = :NEW.Relationship,
                              Created_At = SYSTIMESTAMP
                    WHERE Status = 'PENDING';
            END;
        """)
        
        conn.commit()
        print("✓ Fixed trigger created successfully")
        
        # Verify trigger was created
        cursor.execute("""
            SELECT trigger_name, trigger_type, status
            FROM user_triggers
            WHERE trigger_name = 'TRG_AUTO_RECIPROCAL_FAMILY'
        """)
        
        trigger_info = cursor.fetchone()
        if trigger_info:
            print(f"\n✓ Trigger Status: {trigger_info[2]}")
        
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
    fix_trigger()
