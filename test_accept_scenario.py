#!/usr/bin/env python3
"""
Test the exact scenario causing the error
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def test_exact_scenario():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*60)
        print("TESTING EXACT ACCEPT SCENARIO")
        print("="*60)
        
        # Find the pending request
        print("\n1. Finding pending family request...")
        cursor.execute("""
            SELECT User_ID, Family_User_ID, Relationship, Status
            FROM User_Family
            WHERE Status = 'PENDING'
            AND ROWNUM = 1
        """)
        
        result = cursor.fetchone()
        if not result:
            print("   No pending requests found!")
            return
        
        user_id, fam_id, rel, status = result
        print(f"   Found: {user_id} → {fam_id}: {rel} ({status})")
        
        # Try to update it
        print(f"\n2. Attempting UPDATE to ACCEPTED...")
        print(f"   User {user_id} accepting from User {fam_id}...")
        
        try:
            cursor.execute("""
                UPDATE User_Family 
                SET Status = 'ACCEPTED'
                WHERE User_ID = :u1 AND Family_User_ID = :u2
            """, u1=user_id, u2=fam_id)
            
            print(f"   ✓ UPDATE successful (rows affected: {cursor.rowcount})")
            
            # Check if it was actually updated
            cursor.execute("""
                SELECT Status FROM User_Family
                WHERE User_ID = :u1 AND Family_User_ID = :u2
            """, u1=user_id, u2=fam_id)
            
            new_status = cursor.fetchone()[0]
            print(f"   ✓ Status now: {new_status}")
            
            # Try to commit
            conn.commit()
            print("   ✓ COMMIT successful")
            
            # Check for reciprocal
            print(f"\n3. Checking for reciprocal relationship...")
            cursor.execute("""
                SELECT * FROM User_Family
                WHERE User_ID = :u2 AND Family_User_ID = :u1
            """, u2=fam_id, u1=user_id)
            
            reciprocal = cursor.fetchone()
            if reciprocal:
                print(f"   ✓ RECIPROCAL EXISTS: {reciprocal[0]} → {reciprocal[1]} ({reciprocal[3]})")
            else:
                print(f"   ✗ RECIPROCAL MISSING - TRIGGER FAILED")
                
                # Try to insert reciprocal manually
                print(f"\n4. Attempting manual reciprocal insert...")
                try:
                    cursor.execute("""
                        INSERT INTO User_Family (User_ID, Family_User_ID, Relationship, Status, Created_At)
                        VALUES (:u1, :u2, :rel, 'ACCEPTED', SYSTIMESTAMP)
                    """, u1=fam_id, u2=user_id, rel=rel)
                    conn.commit()
                    print("   ✓ Manual insert successful")
                except Exception as e:
                    print(f"   ✗ Manual insert failed: {e}")
            
        except Exception as e:
            print(f"   ✗ UPDATE FAILED: {e}")
            conn.rollback()
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("Test completed")
        print("="*60)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_exact_scenario()
