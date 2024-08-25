import os
import psycopg2

from main import LOGGER


class AWS:
    def __init__(self):
        self.db = dict()
        try:
            self.conn = psycopg2.connect(
                host=os.getenv('DB_END'),
                database=os.getenv('DB_INSTANCE'),
                user=os.getenv('DB_USERNAME'),
                password=os.getenv('DB_PASS'),
                port=5432
            )
            self.cur = self.conn.cursor()
            self.cur.execute("""
                    CREATE TABLE IF NOT EXISTS receiver_table (
                        username VARCHAR(255) PRIMARY KEY,
                        chat_id INT UNIQUE NOT NULL
                    );
                """)
            self.conn.commit()

        except Exception as e:
            print("Database connection failed due to {}".format(e))

    def save_to_database(self, chat_id, username):
        self.db[username.lower()] = chat_id
        self.cur.execute("INSERT INTO receiver_table (username, chat_id) VALUES (%s, %s);", (username.lower(), chat_id))
        self.conn.commit()

    def check_in_database(self, username: str):
        usr = username.lower()
        if usr in self.db:
            return self.db[usr]
        self.cur.execute("SELECT chat_id FROM receiver_table WHERE username=%s;", (usr,))
        rows = self.cur.fetchall()
        if len(rows) == 1:
            LOGGER.info(rows)
            return rows[0]

    def close(self):
        self.cur.close()
        self.conn.close()
