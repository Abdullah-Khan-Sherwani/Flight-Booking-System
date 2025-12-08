#!/usr/bin/env python3
"""
Test the second family request accept by simulating the exact scenario
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def test_second_accept():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*60)
        print("SIMULATING SECOND ACCEPT SCENARIO")
        print("="*60)
        
        # Show current state
        print("\n1. BEFORE second accept attempt:")
        cursor.execute("""
            SELECT User_ID, Family_User_ID, Relationship, Status
            FROM User_Family
            WHERE (User_ID = 9 AND Family_User_ID = 10)
               OR (User_ID = 10 AND Family_User_ID = 9)
            ORDER BY User_ID
        """)
        for uid, fid, rel, status in cursor.fetchall():
            print(f"   User {uid} → {fid}: {rel} ({status})")
        
        # Now try to accept the PENDING request (User 9 → 10, currently PENDING)
        print("\n2. Attempting to UPDATE User 9 → 10 from PENDING to ACCEPTED...")
        
        # This is what happens when User 10 clicks "Accept" on User 9's request
        try:
            cursor.execute("""
                UPDATE User_Family
                SET Status = 'ACCEPTED'
                WHERE User_ID = 9
                  AND Family_User_ID = 10
                  AND Status = 'PENDING'
            """)
            
            print(f"   ✓ Rows updated: {cursor.rowcount}")
            conn.commit()
            print("   ✓ COMMIT successful")
            
            # Check the state after update
            print("\n3. AFTER second accept attempt:")
            cursor.execute("""
                SELECT User_ID, Family_User_ID, Relationship, Status
                FROM User_Family
                WHERE (User_ID = 9 AND Family_User_ID = 10)
                   OR (User_ID = 10 AND Family_User_ID = 9)
                ORDER BY User_ID
            """)
            
            for uid, fid, rel, status in cursor.fetchall():
                print(f"   User {uid} → {fid}: {rel} ({status})")
            
            # Check if trigger created/updated reciprocal
            print("\n4. Checking reciprocal status:")
            cursor.execute("""
                SELECT User_ID, Family_User_ID, Status
                FROM User_Family
                WHERE User_ID = 10 AND Family_User_ID = 9
            """)
            
            result = cursor.fetchone()
            if result:
                uid, fid, status = result
                print(f"   Found: User {uid} → {fid} ({status})")
                if status == 'ACCEPTED':
                    print("   ✓ Reciprocal was updated to ACCEPTED by trigger")
                elif status == 'REJECTED':
                    print("   ⚠️  Reciprocal is still REJECTED!")
                else:
                    print(f"   ⚠️  Reciprocal is {status}")
            else:
                print("   ✗ No reciprocal found!")
            
        except Exception as update_err:
            print(f"   ✗ UPDATE failed: {update_err}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"✗ Connection error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_second_accept()
