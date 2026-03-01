import sqlite3
from datetime import datetime

DB_PATH = "orders.db"

def init_orders_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            product TEXT,
            details TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_order(user_id: str, product: str, details: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO orders (user_id, product, details, timestamp)
        VALUES (?, ?, ?, ?)
    """, (user_id, product, details, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()