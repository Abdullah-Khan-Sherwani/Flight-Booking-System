# db.py
"""Database connection helper.

This module tries to use `oracledb` (python-oracledb) first, and falls back
to `cx_Oracle` if needed. `get_connection()` will return an open connection
or raise an exception with a clear message so calling code can see the real
failure instead of getting a None and failing with AttributeError.
"""
# NOTE: Service name must be XEPDB1 for gvenzl/oracle-xe Docker images.
import os
from config import DB_USERNAME, DB_PASSWORD, DB_DSN

# Force using python-oracledb in thin mode (no Instant Client required).
try:
    import oracledb as _db_driver
except Exception:
    _db_driver = None


def get_connection():
    """Return an open Oracle connection.

    It reads credentials from these environment variables if present:
    `DB_USERNAME`, `DB_PASSWORD`, `DB_DSN`. Otherwise it uses values from
    `config.py`.

    Raises: Exception with the underlying driver error when connection fails.
    """
    user = os.environ.get('DB_USERNAME', DB_USERNAME)
    pwd = os.environ.get('DB_PASSWORD', DB_PASSWORD)
    dsn = os.environ.get('DB_DSN', DB_DSN or "127.0.0.1:1521/XEPDB1")

    if _db_driver is None:
        raise RuntimeError(
            'python-oracledb is not installed. Install it with: `py -3 -m pip install oracledb`'
        )

    try:
        # By default python-oracledb runs in thin mode (no Instant Client)
        # so this connect should not require Oracle Instant Client.
        conn = _db_driver.connect(user=user, password=pwd, dsn=dsn)
        return conn
    except Exception as e:
        # Print a helpful message and re-raise so caller sees the original error
        print(f"DB connection failed. user={user} dsn={dsn} error={e}")
        raise
