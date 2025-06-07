import sqlite3

def init_db():
    conn = sqlite3.connect('data/media_monitor.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS last_checked (
            source TEXT NOT NULL,
            last_checked TIMESTAMP NOT NULL,
            PRIMARY KEY (source) 
        );
    ''')
    
    conn.commit()
    return conn

def get_last_checked(conn, source):
    cursor = conn.cursor()
    cursor.execute('SELECT last_checked FROM last_checked WHERE source = ?', (source,))
    row = cursor.fetchone()
    return row[0] if row else None

def update_last_checked(conn, source, timestamp):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO last_checked (source, last_checked) VALUES (?, ?)
    ''', (source, timestamp))
    conn.commit()