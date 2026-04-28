import sys
import os
import random
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from backend.sqlite_helper import create_booking, get_conn

def generate_random_plate():
    states = ["WB", "MH", "DL", "KA", "TN", "UP", "HR"]
    state = random.choice(states)
    dist = str(random.randint(1, 99)).zfill(2)
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
    num = str(random.randint(1, 9999)).zfill(4)
    return f"{state}{dist}{letters}{num}"

def generate_mock_data(count=120):
    models = ["Honda City", "Toyota Fortuner", "Hyundai i20", "Tata Nexon", "Maruti Swift", "Kia Seltos", "Mahindra XUV700", "BMW 3 Series", "Mercedes C-Class", "Audi A4"]
    sizes = ["small", "medium", "large"]
    
    print(f"Generating {count} mock bookings...")
    
    # Reset bookings table first (optional, but good for clean tests)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM bookings")
    cur.execute("DELETE FROM entries")
    cur.execute("DELETE FROM detections")
    conn.close()
    
    generated_plates = set()
    while len(generated_plates) < count:
        plate = generate_random_plate()
        if plate not in generated_plates:
            model = random.choice(models)
            size = random.choice(sizes)
            create_booking(plate, model, size)
            generated_plates.add(plate)
    
    print(f"Successfully generated {len(generated_plates)} bookings in parking.db")
    return list(generated_plates)

if __name__ == "__main__":
    generate_mock_data()
