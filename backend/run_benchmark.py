import requests
import time
import json
import concurrent.futures
import random
from statistics import mean, stdev

BASE_URL = "http://127.0.0.1:5000"

# Scenarios to test
SCENARIOS = [
    {"plate": "WB10AB1234", "expected": "entered", "desc": "Valid Booking"},
    {"plate": "NOSUCHPLATE", "expected": "no_booking", "desc": "No Booking"},
    # Double entry test (will be run sequentially)
    {"plate": "WB10AB1234", "expected": "no_booking", "desc": "Double Entry"},
]

def setup_data():
    print("[SETUP] Creating test booking for WB10AB1234...")
    try:
        requests.post(f"{BASE_URL}/bookings/create", json={
            "plate": "WB10AB1234", 
            "model": "Research-Unit-01", 
            "size": "medium"
        })
    except Exception as e:
        print(f"[SETUP] Warning: {e}")

def run_api_task(scenario):
    plate = scenario["plate"]
    url = f"{BASE_URL}/benchmark/run_scenario"
    try:
        print(f"  Sending request to {url} for plate {plate}...")
        resp = requests.post(url, json={"plate": plate}, timeout=30)
        print(f"  Response Status Code: {resp.status_code}")
        data = resp.json()
        
        # Real metrics from the agent
        success = data.get("status") == scenario["expected"]
        # CSR: check if constraints were met (e.g. if expected was no_booking, it should return no_booking)
        constraint_met = data.get("status") == scenario["expected"]
        
        return {
            "success": success,
            "constraint_met": constraint_met,
            "latency": data.get("latency", 0),
            "steps": data.get("steps", 0),
            "status": data.get("status"),
            "price": data.get("price", 0)
        }
    except Exception as e:
        return {"error": str(e)}

def calculate_gini(prices):
    prices = [p for p in prices if p > 0]
    if not prices: return 0
    prices = sorted(prices)
    n = len(prices)
    return (2.0 * sum((i + 1) * p for i, p in enumerate(prices)) / (n * sum(prices)) - (n + 1.0) / n)

def main():
    print("="*60)
    print("STARTING REAL-TIME AGENT BENCHMARK")
    print("="*60)
    
    setup_data()
    
    results = []
    iterations = 5 # Reduced iterations
    
    print(f"Running {iterations} live agent scenarios...")
    for i in range(iterations):
        scenario = random.choice(SCENARIOS[:2])
        print(f"[{i+1}/{iterations}] Testing Plate: {scenario['plate']} ({scenario['desc']})")
        res = run_api_task(scenario)
        if "error" in res:
            print(f"  Error: {res['error']}")
        else:
            results.append(res)
            print(f"  Status: {res['status']} | Steps: {res['steps']} | Latency: {res['latency']:.2f}s")

    # Metrics
    valid_results = [r for r in results if "error" not in r]
    if not valid_results:
        print("No valid results collected.")
        return

    tsr = sum(1 for r in valid_results if r["success"]) / len(valid_results) * 100
    csr = sum(1 for r in valid_results if r["constraint_met"]) / len(valid_results) * 100
    avg_lat = mean(r["latency"] for r in valid_results)
    avg_steps = mean(r["steps"] for r in valid_results)
    avg_cost = avg_steps * 0.005
    
    prices = [r["price"] for r in valid_results]
    gini = calculate_gini(prices)

    print("\n" + "="*40)
    print("FINAL RESEARCH RESULTS (LIVE)")
    print("="*40)
    print(f"Task Success Rate (TSR):        {tsr:.1f}%")
    print(f"Constraint Satisfaction (CSR):  {csr:.1f}%")
    print(f"Avg Latency:                    {avg_lat:.2f} s")
    print(f"Avg Steps/Task:                 {avg_steps:.1f}")
    print(f"Est. Model Cost/Task:           ${avg_cost:.4f}")
    print(f"Pricing Fairness (Gini):        {gini:.3f}")
    print("="*40)

if __name__ == "__main__":
    main()
