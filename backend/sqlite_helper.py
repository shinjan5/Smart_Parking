import sqlite3
import os
from datetime import datetime
from pathlib import Path

# Use absolute path for database
DB_DIR = Path(__file__).parent.parent
DB_PATH = str(DB_DIR / "parking.db")


def get_conn():
    """Get database connection with immediate isolation level for real-time updates"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    # Use WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    # Ensure immediate visibility of changes
    conn.isolation_level = None  # autocommit mode
    return conn


def init_db():
    """Initialize database with all required tables"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        plate TEXT PRIMARY KEY,
        model TEXT,
        size TEXT,
        slot_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT,
        model TEXT,
        size TEXT,
        slot_id INTEGER,
        price REAL,
        entered_at TEXT,
        exited_at TEXT DEFAULT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate TEXT,
        source TEXT,
        detected_at TEXT
    )
    """)

    # Add index for faster lookups
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_entries_plate ON entries(plate, entered_at DESC)
    """)
    
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_detections_plate ON detections(plate, detected_at DESC)
    """)

    conn.close()


def create_booking(plate, model, size, slot_id=None):
    """Create or update a booking"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bookings (plate, model, size, slot_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (plate, model, size, slot_id, 'pending', datetime.utcnow().isoformat())
    )
    conn.close()


def get_booking_by_plate(plate):
    """Get booking information by plate number"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT plate, model, size, slot_id, status FROM bookings WHERE plate=?", (plate,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "plate": row[0],
        "model": row[1],
        "size": row[2],
        "slot_id": row[3],
        "status": row[4]
    }


def log_plate_detection(plate, source="gate_camera"):
    """Log a plate detection event"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO detections (plate, source, detected_at) VALUES (?, ?, ?)",
        (plate, source, datetime.utcnow().isoformat())
    )
    conn.close()


def mark_booking_assigned(plate, slot_id):
    """Assign a slot to a booking and mark as entered"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE bookings SET slot_id = ?, status = ? WHERE plate = ?",
        (slot_id, 'entered', plate)
    )
    conn.close()


def mark_entry(plate, model, size, slot_id, price):
    """Record a vehicle entry"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if entry already exists for this plate (avoid duplicates)
    cur.execute(
        "SELECT id FROM entries WHERE plate = ? AND exited_at IS NULL",
        (plate,)
    )
    existing = cur.fetchone()
    
    if existing:
        print(f"[SQLITE] Entry already exists for plate {plate}, skipping duplicate")
        conn.close()
        return
    
    cur.execute(
        "INSERT INTO entries (plate, model, size, slot_id, price, entered_at) VALUES (?, ?, ?, ?, ?, ?)",
        (plate, model, size, slot_id, price, datetime.utcnow().isoformat())
    )
    print(f"[SQLITE] Entry recorded: {plate} -> Slot {slot_id} @ ${price}")
    conn.close()


def mark_exit(plate):
    """Record a vehicle exit"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE entries SET exited_at = ? WHERE plate = ? AND exited_at IS NULL",
        (datetime.utcnow().isoformat(), plate)
    )
    # Also update booking status
    cur.execute(
        "UPDATE bookings SET status = ? WHERE plate = ?",
        ('exited', plate)
    )
    conn.close()


def get_occupancy_counts():
    """Get current occupancy count (entries without exits)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM entries WHERE exited_at IS NULL")
    count = cur.fetchone()[0]
    conn.close()
    return {"entries": count}


def get_recent_detections(limit=10):
    """Get recent plate detections"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT plate, detected_at FROM detections ORDER BY detected_at DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_recent_entries(limit=10):
    """Get recent entries"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT plate, slot_id, price, entered_at FROM entries ORDER BY entered_at DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_entry_by_plate(plate):
    """Get the most recent entry for a plate"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT slot_id, price, entered_at FROM entries WHERE plate=? AND exited_at IS NULL ORDER BY entered_at DESC LIMIT 1",
        (plate,)
    )
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "slot_id": row[0],
        "price": row[1],
        "entered_at": row[2]
    }