#!/usr/bin/env python3
"""
Debug script to test family invitation acceptance
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def test_family_accept():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*60)
        print("DEBUGGING FAMILY ACCEPT ISSUE")
        print("="*60)
        
        # 1. Check existing User_Family records
        print("\n1. Checking User_Family table...")
        cursor.execute("""
            SELECT * FROM (
                SELECT User_ID, Family_User_ID, Relationship, Status, Created_At
                FROM User_Family
                ORDER BY Created_At DESC
            ) WHERE ROWNUM <= 5
        """)
        
        records = cursor.fetchall()
        if records:
            for user_id, fam_id, rel, status, created in records:
                print(f"   {user_id} → {fam_id}: {rel} ({status}) created {created}")
        else:
            print("   No family relationships found")
        
        # 2. Test the MERGE statement manually
        print("\n2. Testing MERGE statement...")
        
        # Create test data
        print("\n   Creating test users...")
        cursor.execute("""
            INSERT INTO App_User (Email, Password_Hash, Phone_Number, Created_At)
            VALUES ('test_merge1@example.com', 'hash1', '03001234567', SYSTIMESTAMP)
        """)
        user1_id = cursor.var(int)
        cursor.execute("SELECT MAX(User_ID) FROM App_User", [user1_id])
        
        cursor.execute("""
            INSERT INTO App_User (Email, Password_Hash, Phone_Number, Created_At)
            VALUES ('test_merge2@example.com', 'hash2', '03007654321', SYSTIMESTAMP)
        """)
        
        cursor.execute("SELECT MAX(User_ID) FROM App_User")
        user2_id = cursor.fetchone()[0]
        user1_id = user2_id - 1
        
        print(f"   Created User 1: {user1_id}")
        print(f"   Created User 2: {user2_id}")
        
        # Create pending relationship
        print("\n   Creating pending relationship...")
        cursor.execute("""
            INSERT INTO User_Family (User_ID, Family_User_ID, Relationship, Status, Created_At)
            VALUES (:u1, :u2, 'SPOUSE', 'PENDING', SYSTIMESTAMP)
        """, u1=user1_id, u2=user2_id)
        
        conn.commit()
        print(f"   Pending relationship created: {user1_id} → {user2_id}")
        
        # Update to ACCEPTED (which should trigger the reciprocal)
        print("\n   Updating to ACCEPTED...")
        cursor.execute("""
            UPDATE User_Family 
            SET Status = 'ACCEPTED'
            WHERE User_ID = :u1 AND Family_User_ID = :u2
        """, u1=user1_id, u2=user2_id)
        
        conn.commit()
        print("   ✓ Update successful")
        
        # Check if reciprocal was created
        print("\n3. Checking for reciprocal relationship...")
        cursor.execute("""
            SELECT User_ID, Family_User_ID, Status
            FROM User_Family
            WHERE User_ID = :u2 AND Family_User_ID = :u1
        """, u2=user2_id, u1=user1_id)
        
        reciprocal = cursor.fetchone()
        if reciprocal:
            print(f"   ✓ RECIPROCAL CREATED: {reciprocal[0]} → {reciprocal[1]} ({reciprocal[2]})")
        else:
            print("   ✗ RECIPROCAL NOT FOUND - TRIGGER MAY HAVE FAILED")
        
        # Check both directions
        print("\n4. All relationships in database:")
        cursor.execute("""
            SELECT User_ID, Family_User_ID, Relationship, Status
            FROM User_Family
            WHERE (User_ID IN (:u1, :u2) OR Family_User_ID IN (:u1, :u2))
            ORDER BY User_ID
        """, u1=user1_id, u2=user2_id)
        
        all_rels = cursor.fetchall()
        for u1, u2, rel, status in all_rels:
            print(f"   {u1} → {u2}: {rel} ({status})")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✓ Debug test completed")
        print("="*60)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_family_accept()
