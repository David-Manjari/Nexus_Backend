import sqlite3

from backend.config import DATABASE_PATH, BASE_DIR

def get_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def init_db():
    connection = get_db()
    try:
        schema_path = BASE_DIR + "/schema.sql"
        with open(schema_path, encoding="utf-8") as schema_file:
            connection.executescript(schema_file.read())
        connection.commit()
    finally:
        connection.close()
