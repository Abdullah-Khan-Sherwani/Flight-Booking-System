# routes/debug.py
# Debug routes - for development only, remove or disable in production

from flask import Blueprint
from db import get_connection

debug_bp = Blueprint('debug', __name__)


@debug_bp.route('/debug-schema')
def debug_schema():
    """Display database schema information"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check actual table names in the database
    cursor.execute("""
        SELECT table_name 
        FROM user_tables 
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    result = "<h1>Database Tables</h1><ul>"
    for table in tables:
        result += f"<li>{table[0]}</li>"
    result += "</ul>"
    
    # Show columns for key tables
    for table_name in ['AIRPORT', 'FLIGHT_INSTANCE', 'FLIGHT_ROUTE', 'AIRCRAFT_SEAT_MAP', 'PASSENGER', 'RESERVATION', 'BOOKING', 'PAYMENT']:
        try:
            cursor.execute(f"""
                SELECT column_name, data_type 
                FROM user_tab_columns 
                WHERE table_name = '{table_name}' 
                ORDER BY column_id
            """)
            columns = cursor.fetchall()
            
            result += f"<h2>{table_name} Columns:</h2><ul>"
            for col in columns:
                result += f"<li>{col[0]} - {col[1]}</li>"
            result += "</ul>"
        except:
            result += f"<h2>{table_name} - Table not found or error</h2>"
    
    cursor.close()
    conn.close()
    
    return result


@debug_bp.route('/debug-constraint')
def debug_constraint():
    """Debug constraint issues"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Find what constraint is causing the issue
        cursor.execute("""
            SELECT constraint_name, table_name, column_name 
            FROM user_cons_columns 
            WHERE constraint_name = 'SYS_C009170'
        """)
        constraint_info = cursor.fetchone()
        
        if constraint_info:
            return f"Constraint {constraint_info[0]} is on table {constraint_info[1]}, column {constraint_info[2]}"
        else:
            return "Constraint not found"
            
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()


@debug_bp.route('/debug-app-user')
def debug_app_user():
    """Debug App_User table"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check the current maximum User_ID
        cursor.execute("SELECT MAX(User_ID) FROM App_User")
        max_id = cursor.fetchone()[0]
        
        # Check if there's an identity sequence issue
        cursor.execute("""
            SELECT sequence_name, last_number 
            FROM user_sequences 
            WHERE sequence_name LIKE '%USER%' OR sequence_name LIKE '%APP_USER%'
        """)
        sequences = cursor.fetchall()
        
        result = f"<h1>App_User Debug</h1>"
        result += f"<p>Max User_ID: {max_id}</p>"
        result += f"<h2>Sequences:</h2><ul>"
        for seq in sequences:
            result += f"<li>{seq[0]} - Last Number: {seq[1]}</li>"
        result += "</ul>"
        
        return result
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        cursor.close()
        conn.close()
