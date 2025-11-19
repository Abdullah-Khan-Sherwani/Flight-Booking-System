"""
Database Migration Script for Flight Booking System
Automates execution of SQL migration files in correct order
Usage: python migrate_database.py
"""

import oracledb
import os
from datetime import datetime
import sys

# Database configuration
DB_CONFIG = {
    'user': 'flight_admin',
    'password': 'flight123',
    'dsn': 'localhost:1521/XEPDB1'
}

# SQL files to execute in order
SQL_FILES = [
    '01_backup_existing_data.sql',
    '02_drop_old_tables.sql',
    '03_create_new_schema.sql',
    '04_create_procedures.sql',
    '05_create_triggers.sql',
    '06_create_indexes.sql'
]

def log_message(message, log_file):
    """Write message to console and log file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    log_file.write(log_entry + '\n')
    log_file.flush()

def execute_sql_file(connection, filename, log_file):
    """Execute SQL statements from file"""
    log_message(f"\n{'='*60}", log_file)
    log_message(f"Executing: {filename}", log_file)
    log_message(f"{'='*60}", log_file)
    
    if not os.path.exists(filename):
        log_message(f"ERROR: File not found: {filename}", log_file)
        return False
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Split by forward slash on its own line (PL/SQL block terminator)
        statements = sql_content.split('\n/\n')
        
        cursor = connection.cursor()
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            
            # Skip empty statements and comments
            if not statement or statement.startswith('--'):
                continue
            
            # Skip SET commands
            if statement.upper().startswith('SET '):
                continue
            
            # Skip SELECT queries that are just for display
            if statement.upper().startswith('SELECT ') and 'FROM user_' in statement:
                log_message(f"  Skipping display query: {statement[:50]}...", log_file)
                continue
            
            try:
                cursor.execute(statement)
                success_count += 1
                
                # Fetch output from DBMS_OUTPUT if available
                try:
                    cursor.execute("BEGIN DBMS_OUTPUT.GET_LINE(:line, :status); END;",
                                 line=cursor.var(str), status=cursor.var(int))
                    if cursor.fetchone()[1] == 0:  # status = 0 means line available
                        log_message(f"  {cursor.fetchone()[0]}", log_file)
                except:
                    pass
                    
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                log_message(f"  ERROR in statement {i}: {error_msg[:200]}", log_file)
                
                # For critical files, stop on error
                if filename in ['02_drop_old_tables.sql', '03_create_new_schema.sql']:
                    log_message(f"  CRITICAL ERROR - Stopping migration", log_file)
                    cursor.close()
                    return False
        
        cursor.close()
        log_message(f"✓ Completed: {success_count} statements executed, {error_count} errors", log_file)
        return error_count == 0
        
    except Exception as e:
        log_message(f"ERROR reading/executing file: {str(e)}", log_file)
        return False

def verify_migration(connection, log_file):
    """Verify migration success"""
    log_message(f"\n{'='*60}", log_file)
    log_message("VERIFICATION", log_file)
    log_message(f"{'='*60}", log_file)
    
    cursor = connection.cursor()
    
    try:
        # Check tables
        cursor.execute("""
            SELECT COUNT(*) FROM user_tables 
            WHERE table_name IN ('PASSENGER', 'BOOKING', 'RESERVATION', 
                                'CANCELLATION_LOG', 'FLIGHT_CHANGE_LOG')
        """)
        table_count = cursor.fetchone()[0]
        log_message(f"New tables created: {table_count}/5", log_file)
        
        # Check procedures
        cursor.execute("""
            SELECT COUNT(*) FROM user_procedures 
            WHERE object_name LIKE 'SP_%'
        """)
        proc_count = cursor.fetchone()[0]
        log_message(f"Stored procedures created: {proc_count}", log_file)
        
        # Check triggers
        cursor.execute("""
            SELECT COUNT(*) FROM user_triggers 
            WHERE trigger_name LIKE 'TRG_%' AND status = 'ENABLED'
        """)
        trigger_count = cursor.fetchone()[0]
        log_message(f"Triggers created and enabled: {trigger_count}", log_file)
        
        # Check indexes
        cursor.execute("""
            SELECT COUNT(*) FROM user_indexes 
            WHERE table_name IN ('PASSENGER', 'BOOKING', 'RESERVATION')
            AND index_name NOT LIKE 'SYS_%'
        """)
        index_count = cursor.fetchone()[0]
        log_message(f"Indexes created: {index_count}", log_file)
        
        success = (table_count == 5 and proc_count >= 7 and trigger_count >= 5)
        
        if success:
            log_message("\n✓ MIGRATION SUCCESSFUL!", log_file)
        else:
            log_message("\n⚠ MIGRATION COMPLETED WITH WARNINGS", log_file)
            log_message("  Please review log file for details", log_file)
        
        cursor.close()
        return success
        
    except Exception as e:
        log_message(f"ERROR during verification: {str(e)}", log_file)
        cursor.close()
        return False

def main():
    """Main migration function"""
    print("="*60)
    print("FLIGHT BOOKING SYSTEM - DATABASE MIGRATION")
    print("="*60)
    print()
    
    # Create log file
    log_filename = f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        log_file = open(log_filename, 'w', encoding='utf-8')
        log_message("Migration started", log_file)
        log_message(f"Database: {DB_CONFIG['dsn']}", log_file)
        log_message(f"User: {DB_CONFIG['user']}", log_file)
        
        # Connect to database
        log_message("\nConnecting to database...", log_file)
        connection = oracledb.connect(**DB_CONFIG)
        log_message("✓ Connected successfully", log_file)
        
        # Execute SQL files in order
        all_success = True
        for sql_file in SQL_FILES:
            if not execute_sql_file(connection, sql_file, log_file):
                all_success = False
                log_message(f"\n⚠ Error in {sql_file}", log_file)
                
                response = input(f"\nError in {sql_file}. Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    log_message("Migration aborted by user", log_file)
                    break
        
        # Verify migration
        if all_success or input("\nProceed to verification? (y/n): ").lower() == 'y':
            verify_migration(connection, log_file)
        
        # Commit changes
        connection.commit()
        log_message("\n✓ Changes committed", log_file)
        
        # Close connection
        connection.close()
        log_message("✓ Connection closed", log_file)
        
        log_message(f"\n{'='*60}", log_file)
        log_message(f"Migration completed - Log saved to: {log_filename}", log_file)
        log_message(f"{'='*60}", log_file)
        
        log_file.close()
        
        print(f"\n{'='*60}")
        print("MIGRATION COMPLETE")
        print(f"Log file: {log_filename}")
        print(f"{'='*60}")
        
    except oracledb.Error as e:
        error_msg = f"Database error: {str(e)}"
        print(f"\nERROR: {error_msg}")
        if 'log_file' in locals():
            log_message(f"\nFATAL ERROR: {error_msg}", log_file)
            log_file.close()
        sys.exit(1)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"\nERROR: {error_msg}")
        if 'log_file' in locals():
            log_message(f"\nFATAL ERROR: {error_msg}", log_file)
            log_file.close()
        sys.exit(1)

if __name__ == '__main__':
    main()
