import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def get_db_connection(db_path='data/media_monitor.db'):
    """Context manager for database connections with proper error handling."""
    # Ensure the data directory exists
    Path(db_path).parent.mkdir(exist_ok=True)
    
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        # Enable WAL mode for better concurrency and performance
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA foreign_keys = ON')
        yield conn
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        logging.error(f"Unexpected database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def init_db(db_path='data/media_monitor.db'):
    """Initialize database schema. Returns True if successful."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS last_checked (
                    source TEXT NOT NULL,
                    last_checked TIMESTAMP NOT NULL,
                    PRIMARY KEY (source) 
                );
            ''')
            conn.commit()
            logging.info("Database initialized successfully")
            return True
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        return False

def get_last_checked(source, db_path='data/media_monitor.db'):
    """Get the last checked timestamp for a source."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT last_checked FROM last_checked WHERE source = ?', (source,))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logging.error(f"Failed to get last checked time for {source}: {e}")
        return None

def update_last_checked(source, timestamp, db_path='data/media_monitor.db'):
    """Update the last checked timestamp for a source."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO last_checked (source, last_checked) VALUES (?, ?)
            ''', (source, timestamp))
            conn.commit()
            logging.debug(f"Updated last checked time for {source}: {timestamp}")
            return True
    except Exception as e:
        logging.error(f"Failed to update last checked time for {source}: {e}")
        return False

# Legacy functions for backward compatibility with existing tests
def get_last_checked_with_conn(conn, source):
    """Legacy function for backward compatibility with tests."""
    cursor = conn.cursor()
    cursor.execute('SELECT last_checked FROM last_checked WHERE source = ?', (source,))
    row = cursor.fetchone()
    return row[0] if row else None

def update_last_checked_with_conn(conn, source, timestamp):
    """Legacy function for backward compatibility with tests."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO last_checked (source, last_checked) VALUES (?, ?)
    ''', (source, timestamp))
    conn.commit()