import os, json, requests, time
from typing import Dict, Any, Optional, List, Tuple
from sqlite_helper import get_occupancy_counts, create_booking, get_booking_by_plate, mark_booking_assigned, mark_entry, init_db
from math import isfinite

# env config
MOCK_PATH = os.environ.get("MOCK_JSON_PATH", "mock_digital_twin.json")
BASE_PRICE = float(os.environ.get("BASE_PRICE", 50.0))
ELASTICITY = float(os.environ.get("PRICE_ELASTICITY", 1.0))
GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")  
LANGRAPH_KEY = os.environ.get("LANGRAPH_API_KEY")
LANGRAPH_URL = os.environ.get("LANGRAPH_API_URL")  


_gemini_client = None
if GEMINI_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        _gemini_client = genai
    except Exception as e:
        _gemini_client = None

# ----- digital twin helpers (file-backed mock) -----
def load_digital_twin() -> Dict[str,Any]:
    with open(MOCK_PATH,"r") as f:
        return json.load(f)

def save_digital_twin(data: Dict[str,Any]):
    with open(MOCK_PATH,"w") as f:
        json.dump(data, f, indent=2)

# ----- Vision agent (mock) -----
def vision_agent_process(payload: Dict[str,Any]) -> Dict[str,Any]:
    if payload.get("plate"):
        return {"plate": payload["plate"].upper(), "model": payload.get("model","unknown"), "size": payload.get("size","small"), "confidence": 0.95}
    # fallback to sample
    dt = load_digital_twin()
    sample = dt.get("cnn_samples",[None])[0]
    return sample["detected"] if sample else {"plate":None,"model":None,"size":"small","confidence":0.0}

# ----- Reservation -----
def reservation_agent_check(plate: str) -> Optional[Dict[str,Any]]:
    return get_booking_by_plate(plate)

# ----- Security -----
def security_agent_verify(plate: str) -> Tuple[bool,str]:
    conn = None
    try:
        import sqlite3
        conn = sqlite3.connect(os.environ.get("PARK_DB_PATH","parking.db"))
        c = conn.cursor()
        c.execute("SELECT allowed, note FROM vehicles WHERE plate = ?", (plate.upper(),))
        r = c.fetchone()
        if r:
            return (r[0]==1, r[1] or "")
        return (True, "no record (default allow)")
    finally:
        if conn: conn.close()

# ----- Dynamic pricing -----
def dynamic_pricing_agent(base_price: float = BASE_PRICE, elasticity: float = ELASTICITY) -> float:
    dt = load_digital_twin()
    total_slots = len(dt.get("slots",[])) or 1
    occ = get_occupancy_counts()
    occupied = occ["entries"]
    occupancy_ratio = min(max(occupied / total_slots, 0.0), 1.0)
    target = 0.5
    delta = occupancy_ratio - target
    price = base_price * (1 + elasticity * delta)
    if not isfinite(price) or price <= 0: price = base_price
    return round(price,2)

# ----- Langraph orchestration (template) -----
def call_langraph_orchestration(spec: Dict[str,Any]) -> Dict[str,Any]:
    """
    Template: send orchestration spec to Langraph. Replace LANGRAPH_URL with the correct endpoint.
    If LANGRAPH_KEY not provided, raises.
    """
    if not LANGRAPH_KEY or not LANGRAPH_URL:
        raise RuntimeError("Langraph not configured. Set LANGRAPH_API_KEY and LANGRAPH_API_URL.")
    headers = {"Authorization": f"Bearer {LANGRAPH_KEY}", "Content-Type":"application/json"}
    r = requests.post(LANGRAPH_URL, json=spec, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()

# ----- Use Gemini for agentic slot selection -----
def gemini_slot_selector_prompt(slots: List[Dict[str,Any]], vehicle: Dict[str,Any], context: Dict[str,Any]) -> str:
    # concise, structured prompt that asks Gemini to pick a slot id and explain briefly
    prompt = {
      "instruction": "Select the best parking slot for the incoming vehicle. Reply JSON only {slot_id:int, reason:str}.",
      "slots": slots,
      "vehicle": vehicle,
      "context": context,
      "rules": [
        "Pick a free slot whose size fits the vehicle (size equal or larger).",
        "Prefer minimal walking distance (distance_m).",
        "Balance load: avoid always picking same slot id if distances equal.",
        "If no suitable slot return {slot_id:null, reason:'no suitable slot'}."
      ]
    }
    return json.dumps(prompt)

def gemini_select_slot(slots: List[Dict[str,Any]], vehicle: Dict[str,Any], context: Dict[str,Any]) -> Optional[int]:
    if not _gemini_client:
        return None
    prompt = gemini_slot_selector_prompt(slots, vehicle, context)
    try:
        # Use the built-in text output model; prompt asks for JSON
        resp = _gemini_client.generate(model="gemini-1.0", prompt=prompt, max_output_tokens=200)
        text = resp.result[0].content[0].text if hasattr(resp,"result") else resp.text
        # attempt to extract JSON
        j = json.loads(text.strip())
        return j.get("slot_id")
    except Exception as e:
        # if Gemini fails, fallback later
        return None

# Local fallback allocation
def local_slot_allocate(size: str) -> Optional[int]:
    dt = load_digital_twin()
    size_rank = {"small":1,"medium":2,"large":3}
    prefer = size_rank.get(size.lower(),1)
    candidates = [s for s in dt["slots"] if s["status"]=="free" and size_rank.get(s["size"],1) >= prefer]
    if not candidates: return None
    candidates.sort(key=lambda x:(x["distance_m"], x["id"]))
    chosen = candidates[0]
    for s in dt["slots"]:
        if s["id"] == chosen["id"]:
            s["status"] = "reserved (incoming)"; break
    save_digital_twin(dt)
    return chosen["id"]

# ----- Slot manager (tries Gemini -> Langraph -> local) -----
def slot_manager_allocate(size: str, vehicle: Dict[str,Any]) -> Optional[int]:
    dt = load_digital_twin()
    slots = dt.get("slots", [])
    context = {"occupancy": get_occupancy_counts(), "timestamp": time.time()}
    # 1) try Gemini
    try:
        slot_id = gemini_select_slot(slots, vehicle, context)
        if slot_id:
            # mark reserved
            for s in slots:
                if s["id"] == slot_id and s["status"]=="free":
                    s["status"] = "reserved (incoming)"; save_digital_twin(dt); return slot_id
    except Exception:
        pass
    # 2) optionally call Langraph orchestration (template)
    if LANGRAPH_KEY and LANGRAPH_URL:
        spec = {
            "name":"parking_slot_alloc",
            "input":{"slots":slots,"vehicle":vehicle,"context":context},
            "instructions":"Return {'slot_id':int or null, 'reason':str}"
        }
        try:
            res = call_langraph_orchestration(spec)
            # assume Langraph returns JSON with 'slot_id'
            slot_id = res.get("slot_id") or (res.get("output",{}).get("slot_id"))
            if slot_id:
                for s in slots:
                    if s["id"] == slot_id and s["status"]=="free":
                        s["status"]="reserved (incoming)"; save_digital_twin(dt); return slot_id
        except Exception:
            pass
    # 3) local fallback
    return local_slot_allocate(size)

# Orchestration: entry recognition
def entry_recognition_agent(camera_payload: Dict[str,Any]) -> Dict[str,Any]:
    init_db()
    vision = vision_agent_process(camera_payload)
    plate = vision.get("plate")
    model = vision.get("model")
    size = vision.get("size","small")
    if not plate:
        return {"status":"error","message":"no plate detected"}

    # FIXED: Actually use the reservation_agent_check function
    booking = reservation_agent_check(plate)
    ok, sec_note = security_agent_verify(plate)
    if not ok:
        return {"status":"rejected","reason":sec_note}

    assigned_slot = None
    price = dynamic_pricing_agent()

    if booking and booking.get("status") in ("pending","assigned"):
        if booking.get("slot_id"):
            assigned_slot = booking["slot_id"]
            mark_booking_assigned(plate, assigned_slot)
        else:
            assigned_slot = slot_manager_allocate(size, vision)
            if assigned_slot:
                mark_booking_assigned(plate, assigned_slot)
    else:
        # walk-in: allocate slot via agent
        assigned_slot = slot_manager_allocate(size, vision)
        create_booking(plate, model, size, assigned_slot)

    if not assigned_slot:
        return {"status":"no_slot","message":"No suitable slot available"}

    # mark slot occupied and persist
    dt = load_digital_twin()
    for s in dt.get("slots",[]):
        if s["id"] == assigned_slot:
            s["status"] = "occupied"
    save_digital_twin(dt)
    mark_entry(plate, model, size, assigned_slot, price)

    return {"status":"ok","plate":plate,"model":model,"size":size,"slot_id":assigned_slot,"price":price,"security":sec_note}

# small convenience if run directly
if __name__=="__main__":
    init_db()
    print("Dynamic price:", dynamic_pricing_agent())