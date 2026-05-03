"""
eval/generate_test_data.py
Generates 200 benchmark test scenarios from VehicleData and registers
them in parking.db as pre-bookings, ready for multi-model evaluation.

Usage:
    python eval/generate_test_data.py
"""

import sys, os, json, random, csv
from pathlib import Path
from datetime import datetime, timedelta
from io import StringIO

# ---------- paths ----------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlite_helper import get_conn, init_db, get_booking_by_plate, create_booking

# ---------- VehicleData ----------
VEHICLE_DATA_PATH = ROOT / "test_data" / "VehicleData"

def load_vehicles():
    rows = []
    with open(VEHICLE_DATA_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "model": row["Vehicle Model"].strip(),
                "category": row["Category"].strip(),
                "size": row["Vehicle Size"].strip().lower(),
            })
    return rows

# ---------- helper lookups ----------
BRANDS = {
    "Hero": ["Hero Splendor Plus", "Hero Xtreme 160R"],
    "Honda": ["Honda Activa 6G", "Honda Shine 125", "Honda SP 125", "Honda WR-V", "Honda Elevate", "Honda Amaze", "Honda City"],
    "Royal Enfield": ["Royal Enfield Classic 350", "Royal Enfield Bullet 350", "Royal Enfield Hunter 350",
                      "Royal Enfield Himalayan 450", "Royal Enfield Meteor 350"],
    "Bajaj": ["Bajaj Pulsar 150", "Bajaj Platina 100", "Bajaj Chetak", "Bajaj Dominar 400"],
    "TVS": ["TVS Jupiter", "TVS NTorq 125", "TVS Apache RTR 160", "TVS Ronin"],
    "Suzuki": ["Suzuki Access 125"],
    "Yamaha": ["Yamaha MT-15 V2", "Yamaha R15 V4"],
    "KTM": ["KTM Duke 390"],
    "Ola": ["Ola S1 Pro"],
    "Ather": ["Ather 450X"],
    "Maruti Suzuki": ["Maruti Suzuki Alto K10", "Maruti Suzuki Swift", "Maruti Suzuki Baleno",
                      "Maruti Suzuki Wagon R", "Maruti Suzuki Celerio", "Maruti Suzuki Ignis",
                      "Maruti Suzuki Brezza", "Maruti Suzuki Fronx", "Maruti Suzuki Grand Vitara",
                      "Maruti Suzuki Ertiga", "Maruti Suzuki XL6", "Maruti Suzuki Dzire",
                      "Maruti Suzuki Ciaz", "Maruti Suzuki Jimny"],
    "Tata": ["Tata Tiago", "Tata Altroz", "Tata Nexon", "Tata Punch", "Tata Harrier",
             "Tata Safari", "Tata Tigor", "Tata Nexon EV"],
    "Hyundai": ["Hyundai Grand i10 Nios", "Hyundai i20", "Hyundai Venue", "Hyundai Exter",
                "Hyundai Creta", "Hyundai Alcazar", "Hyundai Tucson", "Hyundai Aura", "Hyundai Verna"],
    "Renault": ["Renault Kwid", "Renault Kiger"],
    "Citroen": ["Citroen C3"],
    "Toyota": ["Toyota Glanza", "Toyota Taisor", "Toyota Innova Crysta", "Toyota Innova Hycross",
               "Toyota Fortuner", "Toyota Camry"],
    "MG": ["MG Comet EV", "MG Astor", "MG Hector", "MG Gloster"],
    "Kia": ["Kia Sonet", "Kia Seltos", "Kia Carens"],
    "Mahindra": ["Mahindra XUV300", "Mahindra XUV700", "Mahindra Scorpio-N",
                 "Mahindra Scorpio Classic", "Mahindra Thar"],
    "Nissan": ["Nissan Magnite"],
    "Ford": ["Ford EcoSport", "Ford Endeavour"],
    "Skoda": ["Skoda Kushaq", "Skoda Superb", "Skoda Slavia", "Skoda Kodiaq"],
    "Volkswagen": ["Volkswagen Taigun", "Volkswagen Virtus", "Volkswagen Tiguan"],
    "Force": ["Force Gurkha"],
    "Land Rover": ["Land Rover Defender", "Land Rover Range Rover"],
    "BMW": ["BMW X1", "BMW X5", "BMW 3 Series"],
    "Mercedes-Benz": ["Mercedes-Benz C-Class", "Mercedes-Benz E-Class", "Mercedes-Benz S-Class"],
    "Audi": ["Audi Q3", "Audi Q7"],
}

def get_brand(model):
    for brand, models in BRANDS.items():
        if model in models:
            return brand
    return model.split()[0]

def get_fuel(category, model):
    electric = ["Ola S1 Pro", "Ather 450X", "Bajaj Chetak", "MG Comet EV", "Tata Nexon EV"]
    if model in electric:
        return "Electric"
    diesel = ["Toyota Fortuner", "Ford Endeavour", "MG Gloster", "Land Rover Defender",
              "Land Rover Range Rover", "Mahindra Scorpio-N", "Mahindra Scorpio Classic",
              "Toyota Innova Crysta", "Toyota Innova Hycross", "Mahindra Thar",
              "Mahindra XUV700", "Force Gurkha", "Skoda Kodiaq"]
    if model in diesel:
        return "Diesel"
    cng = ["Maruti Suzuki Wagon R", "Maruti Suzuki Ertiga", "Maruti Suzuki XL6",
           "Maruti Suzuki Dzire", "Hyundai Aura", "Tata Tigor"]
    if model in cng:
        return random.choice(["CNG", "Petrol"])
    return "Petrol"

PREFERENCES_POOL = [
    "Covered",
    "EV Charging",
    "Near Stairs",
    "Covered, Near Stairs",
    "EV Charging, Covered",
    "",  # no preference
    "",  # no preference (weighted higher)
    "",
]

SIZE_MAP = {
    "small": "small",
    "medium": "medium",
    "large": "large",
}

NAMES = [
    "Aarav Sharma", "Ishaan Patel", "Priya Nair", "Riya Ghosh", "Arjun Mehta",
    "Ananya Sen", "Vikram Rao", "Kavya Iyer", "Rohan Kumar", "Neha Verma",
    "Aditya Joshi", "Shruti Das", "Raj Kapoor", "Pooja Singh", "Amit Bose",
    "Divya Reddy", "Siddharth Malhotra", "Tanvi Chatterjee", "Karan Saxena",
    "Meera Krishnan", "Dev Pandey", "Sana Ahmed", "Varun Gupta", "Sneha Agarwal",
    "Harsh Bajaj", "Lakshmi Pillai", "Nikhil Jain", "Ayesha Khan", "Rahul Dutta",
    "Simran Kaur", "Aryan Sharma", "Kritika Banerjee", "Akash Patel", "Ritu Desai",
    "Manav Shah", "Deepika Choudhury", "Suraj Mishra", "Ankita Roy", "Gaurav Nath",
    "Preeti Bhatt",
]

def make_plate(idx: int) -> str:
    """Generate unique West Bengal-style plates: WB-XX-AA-NNNN"""
    state = "WB"
    district = f"{(idx // 1000) + 10:02d}"
    alpha = chr(65 + (idx // 100) % 26) + chr(65 + (idx // 10) % 26)
    num = f"{(idx * 37 + 1000) % 9000 + 1000}"
    return f"{state}{district}{alpha}{num}"

def make_time_pair():
    entry_h = random.randint(6, 20)
    duration_h = random.randint(1, 8)
    entry = datetime(2026, 5, 10, entry_h, 0)
    exit_t = entry + timedelta(hours=duration_h)
    return entry.strftime("%H:%M:%S"), exit_t.strftime("%H:%M:%S")

# ---------- SCENARIO TYPES ----------
# 180 regular booked (valid, eligible)
# 10 edge: no-booking scenario (plate not registered)
# 10 edge: already-entered (double entry attempt)

def generate_scenarios(vehicles, n_regular=180, n_no_booking=10, n_double=10):
    random.seed(42)
    all_vehicles = vehicles * 10  # allow repetition
    random.shuffle(all_vehicles)

    scenarios = []
    idx = 1

    # --- Regular scenarios ---
    for i in range(n_regular):
        v = all_vehicles[i]
        plate = make_plate(idx)
        entry_time, exit_time = make_time_pair()
        prefs = random.choice(PREFERENCES_POOL)
        # Only EV vehicles get EV Charging preference
        if "EV Charging" in prefs and get_fuel(v["category"], v["model"]) != "Electric":
            prefs = prefs.replace("EV Charging, ", "").replace(", EV Charging", "").replace("EV Charging", "").strip().strip(",").strip()

        scenarios.append({
            "type": "regular",
            "plate": plate,
            "name": random.choice(NAMES),
            "model": v["model"],
            "brand": get_brand(v["model"]),
            "category": v["category"],
            "size": SIZE_MAP.get(v["size"], "medium"),
            "entry_time": entry_time,
            "exit_time": exit_time,
            "preferences": prefs,
            "fuel_type": get_fuel(v["category"], v["model"]),
            "expected_status": "entered",
        })
        idx += 1

    # --- No-booking scenarios (plate not in DB, agent should deny) ---
    for i in range(n_no_booking):
        plate = f"XX{99 - i:02d}ZZ{7000 + i}"  # clearly fake plates
        scenarios.append({
            "type": "no_booking",
            "plate": plate,
            "name": "Ghost Driver",
            "model": "Unknown",
            "brand": "Unknown",
            "category": "Unknown",
            "size": "medium",
            "entry_time": "10:00:00",
            "exit_time": "12:00:00",
            "preferences": "",
            "fuel_type": "Petrol",
            "expected_status": "no_booking",
        })

    # --- Double-entry scenarios (will share plate with first 10 regular) ---
    for i in range(n_double):
        base = scenarios[i]
        scenarios.append({
            **base,
            "type": "double_entry",
            "expected_status": "no_booking",  # should be denied (status='entered')
        })

    return scenarios

def register_bookings(scenarios):
    init_db()
    conn = get_conn()
    registered = 0
    skipped = 0
    for s in scenarios:
        if s["type"] == "no_booking":
            continue  # intentionally not registered
        if s["type"] == "double_entry":
            continue  # already registered as 'regular'
        existing = get_booking_by_plate(s["plate"])
        if existing:
            skipped += 1
            continue
        create_booking(
            s["plate"], s["name"], s["brand"], s["model"],
            s["category"], s["size"],
            s["entry_time"], s["exit_time"],
            s["preferences"], s["fuel_type"]
        )
        registered += 1
    conn.close()
    return registered, skipped

def main():
    print("Loading vehicle data...")
    vehicles = load_vehicles()
    print(f"  {len(vehicles)} vehicle types loaded")

    print("Generating 200 test scenarios...")
    scenarios = generate_scenarios(vehicles, n_regular=180, n_no_booking=10, n_double=10)
    print(f"  {len(scenarios)} scenarios generated")
    print(f"    - Regular (bookable): {sum(1 for s in scenarios if s['type']=='regular')}")
    print(f"    - No-booking (deny):  {sum(1 for s in scenarios if s['type']=='no_booking')}")
    print(f"    - Double-entry (deny):{sum(1 for s in scenarios if s['type']=='double_entry')}")

    # Save scenario manifest
    out_path = Path(__file__).parent / "test_scenarios.json"
    with open(out_path, "w") as f:
        json.dump(scenarios, f, indent=2)
    print(f"\nScenarios saved to: {out_path}")

    print("\nRegistering bookings in parking.db...")
    registered, skipped = register_bookings(scenarios)
    print(f"  Registered: {registered} | Already existed: {skipped}")

    # Summary stats
    sizes = {}
    cats = {}
    for s in scenarios:
        if s["type"] == "regular":
            sizes[s["size"]] = sizes.get(s["size"], 0) + 1
            cats[s["category"]] = cats.get(s["category"], 0) + 1

    print("\n--- Size distribution (regular) ---")
    for k, v in sorted(sizes.items()):
        print(f"  {k}: {v}")

    print("\n--- Category distribution (top 10) ---")
    for k, v in sorted(cats.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: {v}")

    print("\n[OK] Test data generation complete.")

if __name__ == "__main__":
    main()
