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
        name TEXT,
        model TEXT,
        brand TEXT,
        category TEXT,
        size TEXT,
        entry_time TEXT,
        exit_time TEXT,
        preferences TEXT,
        fuel_type TEXT,
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


def create_booking(plate, name, brand, model, category, size, entry_time, exit_time, preferences, fuel_type, slot_id=None):
    """Create or update a booking"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bookings (plate, name, model, brand, category, size, entry_time, exit_time, preferences, fuel_type, slot_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (plate, name, model, brand, category, size, entry_time, exit_time, preferences, fuel_type, slot_id, 'pending', datetime.utcnow().isoformat())
    )
    conn.close()


def get_booking_by_plate(plate):
    """Get booking information by plate number"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT plate, name, model, brand, category, size, entry_time, exit_time, preferences, fuel_type, slot_id, status FROM bookings WHERE plate=?", (plate,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "plate": row[0],
        "name": row[1],
        "model": row[2],
        "brand": row[3],
        "category": row[4],
        "size": row[5],
        "entry_time": row[6],
        "exit_time": row[7],
        "preferences": row[8],
        "fuel_type": row[9],
        "slot_id": row[10],
        "status": row[11]
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
    print(f"[SQLITE] Entry recorded: {plate} -> Slot {slot_id} @ ₹{price}")
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

def get_all_entries():
    """Get all entries for detailed logging"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT plate, model, size, slot_id, price, entered_at, exited_at FROM entries ORDER BY entered_at DESC"
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

def get_active_entries_with_details():
    """Get active entries joined with booking details if available"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT 
            e.slot_id, e.plate, e.model, 
            b.name, b.brand, b.category, b.fuel_type
        FROM entries e
        LEFT JOIN bookings b ON e.plate = b.plate
        WHERE e.exited_at IS NULL
    ''')
    rows = cur.fetchall()
    conn.close()
    
    mapping = {}
    for r in rows:
        mapping[r[0]] = {
            "plate": r[1],
            "model": r[2],
            "name": r[3] or "Unknown",
            "brand": r[4] or "Unknown",
            "category": r[5] or "Unknown",
            "fuel_type": r[6] or "Unknown"
        }
    return mapping