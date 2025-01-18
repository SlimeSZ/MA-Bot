import sqlite3
from datetime import datetime

def create_tables():
    conn = sqlite3.connect('MCDB.db')
    cursor = conn.cursor()

    # Main multialerts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS multialerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_name TEXT,
        ca TEXT UNIQUE NOT NULL,
        alert_time TIMESTAMP NOT NULL,
        swt_sol_amount REAL,
        fresh_sol_amount REAL,
        swt_wallet_type TEXT,
        fresh_wallet_type TEXT,
        has_x BOOLEAN,
        has_tg BOOLEAN,
        liquidity REAL,
        initial_marketcap REAL,
        volume_5m REAL,
        volume_1h REAL,
        volume_6h REAL,
        volume_24h REAL,
        buys_5m INTEGER,
        sells_5m INTEGER,
        buys_1h INTEGER,
        sells_1h INTEGER,
        buys_24h INTEGER,
        sells_24h INTEGER,
        price_change_5m REAL,
        price_change_1h REAL,
        price_change_24h REAL
    )
    ''')

    # Individual wallet amounts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS wallet_amounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER,
        wallet_type TEXT,
        amount REAL,
        FOREIGN KEY (alert_id) REFERENCES multialerts(id)
    )
    ''')

    conn.commit()
    conn.close()
    print(f"DB Created Successfully!")

if __name__ == "__main__":
    create_tables()