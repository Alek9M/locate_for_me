import os
import psycopg2
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_END'),
        database=os.getenv('DB_INSTANCE'),
        user=os.getenv('DB_USERNAME'),
        password=os.getenv('DB_PASS'),
        port=5432
    )
    cur = conn.cursor()
except Exception as e:
    print("Database connection failed due to {}". format(e))

db = dict()

def create_table():
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receiver_table (
            username VARCHAR(255) PRIMARY KEY,
            chat_id BIGINT UNIQUE NOT NULL,
            PRIMARY KEY (chat_id)
        )
    """)
    conn.commit()

def save_to_database(chat_id, username):
    db[username.lower()] = chat_id
    cur.execute("INSERT INTO receiver_table (username, chat_id) VALUES (%s, %s)", (username.lower(), chat_id))
    conn.commit()

def check_in_database(username: str):
    usr = username.lower()
    if usr in db:
        return db[usr]
    cur.execute("SELECT chat_id FROM receiver_table WHERE username=%s", (usr,))
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]


def close():
    cur.close()
    conn.close()