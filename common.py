from datetime import timedelta, timezone
import sqlite3

DBNAME = "rec.db"

DTFORMAT = "%a %d %b %H_%M_%S"
TIMEZONES = {"Europe/Moscow": timezone(timedelta(hours=3))}

# В какую временную зону форматировать utc timestamps
UTCTZ = TIMEZONES["Europe/Moscow"]

con = sqlite3.connect(DBNAME)


def create_common_tables():
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY,
            utc INTEGER,
            nickname TEXT,
            fullname TEXT,
            channel TEXT
        )"""
    )
    cur.close()
