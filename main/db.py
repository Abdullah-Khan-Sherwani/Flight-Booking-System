# db.py
import cx_Oracle
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

def get_connection():
    try:
        conn = cx_Oracle.connect(DB_USERNAME, DB_PASSWORD, DB_DSN)
        return conn
    except cx_Oracle.DatabaseError as e:
        print("Database connection error:", e)
        return None
