#!/usr/bin/env python3
"""
Debug the second family request accept issue
"""
import oracledb
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def test_second_request():
    try:
        conn = oracledb.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        cursor = conn.cursor()
        
        print("="*60)
        print("DEBUGGING SECOND REQUEST ISSUE")
        print("="*60)
        
        # Find all USER_FAMILY records
        print("\n1. All User_Family relationships:")
        cursor.execute("""
            SELECT User_ID, Family_User_ID, Relationship, Status, Created_At
            FROM User_Family
            ORDER BY Created_At DESC
        """)
        
        records = cursor.fetchall()
        for i, (uid, fid, rel, status, created) in enumerate(records, 1):
            print(f"   {i}. User {uid} → {fid}: {rel} ({status})")
        
        # Check if there are multiple pending requests from same user
        print("\n2. Checking for pending requests from same user to multiple recipients:")
        cursor.execute("""
            SELECT User_ID, COUNT(*) as pending_count
            FROM User_Family
            WHERE Status = 'PENDING'
            GROUP BY User_ID
            HAVING COUNT(*) > 1
        """)
        
        multi_pending = cursor.fetchall()
        if multi_pending:
            for uid, count in multi_pending:
                print(f"   User {uid} has {count} pending requests")
        else:
            print("   ✓ No duplicate pending requests found")
        
        # Check for ACCEPTED relationships that might be causing duplicates
        print("\n3. Checking for duplicate reciprocal relationships:")
        cursor.execute("""
            SELECT u1.User_ID, u1.Family_User_ID, u1.Status,
                   u2.User_ID, u2.Family_User_ID, u2.Status
            FROM User_Family u1
            LEFT JOIN User_Family u2 ON u1.Family_User_ID = u2.User_ID 
                AND u1.User_ID = u2.Family_User_ID
            WHERE u1.Status = 'ACCEPTED'
            ORDER BY u1.User_ID
        """)
        
        reciprocals = cursor.fetchall()
        for u1, f1, s1, u2, f2, s2 in reciprocals:
            if u2 is None:
                print(f"   ⚠️  {u1} → {f1} ({s1}) has NO reciprocal!")
            else:
                print(f"   ✓ {u1} → {f1} ({s1}) ↔ {u2} → {f2} ({s2})")
        
        # Get trigger source
        print("\n4. Current trigger logic:")
        cursor.execute("""
            SELECT trigger_body
            FROM user_triggers
            WHERE trigger_name = 'TRG_AUTO_RECIPROCAL_FAMILY'
        """)
        
        trigger = cursor.fetchone()
        if trigger:
            print("   Trigger exists ✓")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_second_request()
