import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TWIN_PATH = ROOT_DIR / "backend" / "mock_digital_twin.json"

def scale_twin(count=150):
    sizes = ["small", "medium", "large"]
    slots = []
    
    for i in range(1, count + 1):
        size = sizes[i % 3]
        slots.append({
            "id": i,
            "size": size,
            "distance": 10 + (i * 2),
            "status": "free"
        })
    
    twin = {"slots": slots}
    
    with open(TWIN_PATH, "w") as f:
        json.dump(twin, f, indent=2)
    
    print(f"Digital twin scaled to {count} slots.")

if __name__ == "__main__":
    scale_twin()
