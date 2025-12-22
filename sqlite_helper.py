
import sqlite3, os
from contextlib import closing
from typing import Optional, Dict, Any, List

DB_PATH = os.environ.get("PARK_DB_PATH", "parking.db")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT UNIQUE,
            model TEXT,
            size TEXT,
            slot_id INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT,
            model TEXT,
            size TEXT,
            slot_id INTEGER,
            price REAL,
            entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            plate TEXT PRIMARY KEY,
            allowed INTEGER DEFAULT 1,
            note TEXT
        )""")
        conn.commit()

def create_booking(plate: str, model: str, size: str, slot_id: Optional[int]=None) -> int:
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO bookings (plate, model, size, slot_id, status) VALUES (?, ?, ?, ?, ?)",
                  (plate.upper(), model, size, slot_id, "pending"))
        conn.commit()
        return c.lastrowid

def get_booking_by_plate(plate: str) -> Optional[Dict[str, Any]]:
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("SELECT id, plate, model, size, slot_id, status, created_at FROM bookings WHERE plate = ?", (plate.upper(),))
        r = c.fetchone()
        if not r: return None
        keys = ["id","plate","model","size","slot_id","status","created_at"]
        return dict(zip(keys, r))

def mark_booking_assigned(plate: str, slot_id: int):
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("UPDATE bookings SET slot_id = ?, status = ? WHERE plate = ?", (slot_id, "assigned", plate.upper()))
        conn.commit()

def mark_entry(plate: str, model: str, size: str, slot_id: int, price: float):
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO entries (plate, model, size, slot_id, price) VALUES (?, ?, ?, ?, ?)",
                  (plate.upper(), model, size, slot_id, price))
        conn.commit()

def get_occupancy_counts() -> Dict[str,int]:
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM entries")
        entries = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM bookings WHERE status IN ('assigned','pending')")
        pending = c.fetchone()[0] or 0
    return {"entries": entries, "pending": pending}

def list_bookings(limit:int=50) -> List[Dict[str,Any]]:
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("SELECT id, plate, model, size, slot_id, status, created_at FROM bookings ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
    keys = ["id","plate","model","size","slot_id","status","created_at"]
    return [dict(zip(keys,r)) for r in rows]

if __name__=="__main__":
    init_db()
    print("DB initialized at", DB_PATH)
