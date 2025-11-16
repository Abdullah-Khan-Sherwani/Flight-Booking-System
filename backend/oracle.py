import oracledb


def get_connection():
    return oracledb.connect(
        user="flight_app_user",
        password="flight123",
        dsn="localhost:1521/XEPDB1"
    )