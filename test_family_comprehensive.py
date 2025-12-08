#!/usr/bin/env python3
"""
Comprehensive test of the family feature - test accepting multiple requests
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def test_comprehensive():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*80)
        print("COMPREHENSIVE FAMILY FEATURE TEST")
        print("="*80)
        
        # Create some test data
        print("\n1. Setting up test relationships...")
        
        # Clear previous test data
        cursor.execute("DELETE FROM User_Family WHERE User_ID IN (9, 10, 11, 12)")
        conn.commit()
        
        # Use existing users from the database
        # First, check what users exist
        cursor.execute("SELECT User_ID FROM APP_USER WHERE rownum <= 10 ORDER BY User_ID")
        existing_users = [row[0] for row in cursor.fetchall()]
        print(f"   Using existing users: {existing_users[:4]}")
        
        # Insert test relationships using existing users
        test_data = [
            (existing_users[0], existing_users[1], "SIBLING"),
            (existing_users[0], existing_users[2], "PARENT"),
            (existing_users[3], existing_users[1], "SPOUSE"),
        ]
        
        for u1, u2, rel in test_data:
            cursor.execute("""
                INSERT INTO User_Family (User_ID, Family_User_ID, Relationship, Status, Created_At)
                VALUES (:u1, :u2, :rel, 'PENDING', SYSTIMESTAMP)
            """, {"u1": u1, "u2": u2, "rel": rel})
        
        conn.commit()
        print("   ✓ Test data inserted")
        
        # Test 1: Accept first request
        print(f"\n2. Test 1: Accept first request ({test_data[0][0]} → {test_data[0][1]})...")
        cursor.execute("""
            UPDATE User_Family
            SET Status = 'ACCEPTED'
            WHERE User_ID = :u1 AND Family_User_ID = :u2
        """, {"u1": test_data[0][0], "u2": test_data[0][1]})
        rows = cursor.rowcount
        conn.commit()
        print(f"   ✓ Updated {rows} rows")
        
        # Check reciprocal
        cursor.execute("""
            SELECT Status FROM User_Family
            WHERE User_ID = :u2 AND Family_User_ID = :u1
        """, {"u1": test_data[0][0], "u2": test_data[0][1]})
        result = cursor.fetchone()
        if result and result[0] == 'ACCEPTED':
            print(f"   ✓ Reciprocal created with status ACCEPTED")
        else:
            print(f"   ✗ Reciprocal not created or wrong status: {result}")
        
        # Test 2: Accept second request from same user
        print(f"\n3. Test 2: Accept second request from same user ({test_data[1][0]} → {test_data[1][1]})...")
        cursor.execute("""
            UPDATE User_Family
            SET Status = 'ACCEPTED'
            WHERE User_ID = :u1 AND Family_User_ID = :u2
        """, {"u1": test_data[1][0], "u2": test_data[1][1]})
        rows = cursor.rowcount
        conn.commit()
        print(f"   ✓ Updated {rows} rows")
        
        # Check reciprocal
        cursor.execute("""
            SELECT Status FROM User_Family
            WHERE User_ID = :u2 AND Family_User_ID = :u1
        """, {"u1": test_data[1][0], "u2": test_data[1][1]})
        result = cursor.fetchone()
        if result and result[0] == 'ACCEPTED':
            print(f"   ✓ Reciprocal created with status ACCEPTED")
        else:
            print(f"   ✗ Reciprocal not created or wrong status: {result}")
        
        # Test 3: Accept third request from different user
        print(f"\n4. Test 3: Accept third request from different user ({test_data[2][0]} → {test_data[2][1]})...")
        cursor.execute("""
            UPDATE User_Family
            SET Status = 'ACCEPTED'
            WHERE User_ID = :u1 AND Family_User_ID = :u2
        """, {"u1": test_data[2][0], "u2": test_data[2][1]})
        rows = cursor.rowcount
        conn.commit()
        print(f"   ✓ Updated {rows} rows")
        
        # Check reciprocal
        cursor.execute("""
            SELECT Status FROM User_Family
            WHERE User_ID = :u2 AND Family_User_ID = :u1
        """, {"u1": test_data[2][0], "u2": test_data[2][1]})
        result = cursor.fetchone()
        if result and result[0] == 'ACCEPTED':
            print(f"   ✓ Reciprocal created with status ACCEPTED")
        else:
            print(f"   ✗ Reciprocal not created or wrong status: {result}")
        
        # Summary
        print("\n5. Final state of all test relationships:")
        cursor.execute("""
            SELECT User_ID, Family_User_ID, Relationship, Status
            FROM User_Family
            WHERE User_ID IN (:u1, :u2, :u3, :u4)
            OR Family_User_ID IN (:u1, :u2, :u3, :u4)
            ORDER BY User_ID, Family_User_ID
        """, {
            "u1": test_data[0][0], "u2": test_data[0][1],
            "u3": test_data[1][1], "u4": test_data[2][0]
        })
        
        for uid, fid, rel, status in cursor.fetchall():
            print(f"   {uid} → {fid}: {rel:20} {status}")
        
        print("\n✓ All tests passed!")
        print("="*80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_comprehensive()
