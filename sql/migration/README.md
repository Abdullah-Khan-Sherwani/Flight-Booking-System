# Flight Booking System - Database Migration

## Quick Start

### Automated Migration (Recommended)

```bash
cd sql/migration
python migrate_database.py
```

### Manual Migration

Run SQL files in this order:

1. `01_backup_existing_data.sql` - Creates backup tables
2. `02_drop_old_tables.sql` - Drops old schema
3. `03_create_new_schema.sql` - Creates new tables
4. `04_create_procedures.sql` - Creates stored procedures
5. `05_create_triggers.sql` - Creates triggers
6. `06_create_indexes.sql` - Creates performance indexes
7. `07_repopulate_data.sql` - Populates with sample data

### After Migration

1. Check migration_log.txt for any errors
2. Run repopulation script if needed
3. Test with sample queries (see docs/MIGRATION_AND_UPGRADE_GUIDE.md)
4. Update app.py (Phase 3)

### Rollback

If migration fails, restore from backup:

```sql
DROP TABLE Passenger CASCADE CONSTRAINTS;
DROP TABLE Booking CASCADE CONSTRAINTS;
DROP TABLE Reservation CASCADE CONSTRAINTS;

CREATE TABLE Passenger AS SELECT * FROM Passenger_BACKUP;
CREATE TABLE Reservation AS SELECT * FROM Reservation_BACKUP;
CREATE TABLE Payment_Status AS SELECT * FROM Payment_Status_BACKUP;
```

### Requirements

- Python 3.7+
- python-oracledb package: `pip install oracledb`
- Oracle Database 19c or later
- Database user: flight_admin with CREATE TABLE privileges

### Support

See `docs/MIGRATION_AND_UPGRADE_GUIDE.md` for detailed documentation.
