# run_db_test.py
# Quick script to test Oracle DB connectivity using the project's `db.get_connection()`.

from db import get_connection


def main():
    try:
        conn = get_connection()
        print("Connected to DB:", conn)

        cur = conn.cursor()
        try:
            # Lightweight check: get DB server time
            cur.execute("SELECT TO_CHAR(SYSDATE,'YYYY-MM-DD HH24:MI:SS') FROM DUAL")
            row = cur.fetchone()
            print("DB SYSDATE:", row[0] if row else "(no result)")
        except Exception as qerr:
            print("Query failed:", qerr)
        finally:
            cur.close()
            conn.close()

    except Exception as err:
        print("Connection test failed:", err)


if __name__ == '__main__':
    main()
