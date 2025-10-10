import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS streams (
        name TEXT PRIMARY KEY,
        url TEXT,
        m3u8 TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def update_stream(name, url, m3u8):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''REPLACE INTO streams (name, url, m3u8) VALUES (?, ?, ?)''', (name, url, m3u8))
    conn.commit()
    conn.close()

def get_stream(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT m3u8 FROM streams WHERE name = ?', (name,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None