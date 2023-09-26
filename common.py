import os
import sqlite3


def getenv(name):
    if (value := os.getenv(name)) is None:
        raise ValueError(f"envvar {name} is not set")
    return value


DBNAME = "rec.db"

DTFORMAT = "%a %d %b, %H:%M:%S"

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
