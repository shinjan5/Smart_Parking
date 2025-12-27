# backend/agentic.py
import torch



import os
import json
import io
import cv2
import numpy as np
import easyocr
from math import isfinite
from typing import Dict, Any, Optional, TypedDict
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from ultralytics import YOLO
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from sqlite_helper import (
    init_db,
    log_plate_detection,
    get_booking_by_plate,
    mark_booking_assigned,
    mark_entry,
    get_occupancy_counts,
)

# Paths & constants
BASE_DIR = Path(__file__).parent.parent
YOLO_MODEL_PATH = str(BASE_DIR / "models" / "last (3).pt")
DIGITAL_TWIN_PATH = str(BASE_DIR / "backend" / "mock_digital_twin.json")

BASE_PRICE = 50
ELASTICITY = 1.2

# Init models & DB
yolo = YOLO(YOLO_MODEL_PATH)
if(torch.cuda.is_available()):
    reader = easyocr.Reader(["en"], gpu=True)
else:
    reader = easyocr.Reader(["en"], gpu=False)


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    google_api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
)

init_db()

# OCR helpers
def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # image = cv2.GaussianBlur(image, (5, 5), 0)

    # image = cv2.adaptiveThreshold(
    #     image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    #     cv2.THRESH_BINARY, 11, 2
    # )

    # kernel = np.ones((2, 2), np.uint8)
    # return cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
    return image

# def run_easyocr(image: np.ndarray) -> str:
#     results = reader.readtext(image)
#     chars = [
#         c for _, text, conf in results if conf > 0.1 for c in text if c.isalnum()
#     ]
#     return "".join(chars).upper()


def run_easyocr(processed_image)->str:
    """
    Takes a preprocessed image and returns text
    """

    results = reader.readtext(processed_image)

    extracted_text = []
    print(results)

    for box, text, confidence in results:
        if confidence > 0.1:
            for char in text:
                if char in "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUWVXYZ":
                    extracted_text.append(char)

    return "".join(extracted_text)


def normalize_plate(text: str) -> str:
    return "".join(c for c in text.upper() if c.isalnum())


# Vision agent (NO LLM)
def vision_agent_process(image_bytes: bytes) -> Dict[str, Any]:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        frame = np.array(image)

        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        results = yolo(frame)
        h, w = frame.shape[:2]

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                processed = preprocess_for_ocr(crop)
                raw = run_easyocr(processed)
                plate = normalize_plate(raw)

                if plate and len(plate) >= 4:
                    log_plate_detection(plate)
                    print(f"[VISION] Plate detected: {plate}")
                    return {"plate": plate, "raw_plate": raw}

        return {"plate": None}

    except Exception as e:
        print(f"[VISION] Error: {e}")
        return {"plate": None}


# Digital twin helpers
def load_twin() -> dict:
    with open(DIGITAL_TWIN_PATH) as f:
        return json.load(f)


def save_twin(dt: dict):
    with open(DIGITAL_TWIN_PATH, "w") as f:
        json.dump(dt, f, indent=2)


def pricing() -> float:
    """
    Dynamic pricing based on occupancy
    - Base price: ₹50
    - Increases as parking fills up (above 50% capacity)
    """
    dt = load_twin()
    total = len(dt["slots"]) or 1
    occ = get_occupancy_counts()["entries"]
    ratio = occ / total

    price = BASE_PRICE * (1 + ELASTICITY * max(0, ratio - 0.5))
    final_price = round(price if isfinite(price) else BASE_PRICE, 2)
    
    print(f"[PRICING] Occupancy: {occ}/{total} ({ratio*100:.1f}%) → Price: ₹{final_price}")
    return final_price


def size_compatible_strict(slot_size: str, vehicle_size: str) -> bool:
    """
    STRICT size matching: Each vehicle size can ONLY use slots of the same size
    - Small car → Small slot ONLY
    - Medium car → Medium slot ONLY
    - Large car → Large slot ONLY
    """
    return slot_size == vehicle_size


# Slot selection (LLM with strict constraints)
slot_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a parking slot assignment system. 
    CRITICAL RULES:
    1. ONLY select slots where status is "free"
    2. Select the slot with the SMALLEST distance value (closest to entrance)
    3. Return ONLY valid JSON: {{"slot_id": number}}
    4. If multiple slots qualify, choose the one with minimum distance
    """),
    ("human", """Available slots (already filtered for correct size and free status):
{slots}

Vehicle needing parking:
{vehicle}

Select the CLOSEST free slot (minimum distance). Return only: {{"slot_id": number}}""")
])


def llm_select_slot(vehicle: Dict[str, Any]) -> Optional[int]:
    """
    Select optimal parking slot with STRICT size matching
    """
    dt = load_twin()
    size = vehicle.get("size", "medium")
    plate = vehicle.get("plate", "UNKNOWN")

    print(f"[SLOT] Finding slot for {plate} (size: {size})")
    print(f"[SLOT] Current slots state: {json.dumps(dt['slots'], indent=2)}")

    # STRICT FILTERING: Only slots that match size exactly AND are free
    free = [
        s for s in dt["slots"]
        if s["status"] == "free" and size_compatible_strict(s["size"], size)
    ]

    if not free:
        print(f"[SLOT] ❌ No free {size} slots available!")
        print(f"[SLOT] Available slots by size:")
        for slot_size in ["small", "medium", "large"]:
            count = sum(1 for s in dt["slots"] if s["size"] == slot_size and s["status"] == "free")
            print(f"  - {slot_size}: {count} free")
        return None

    print(f"[SLOT] Found {len(free)} free {size} slot(s): {[s['id'] for s in free]}")

    # If only one option, use it directly
    if len(free) == 1:
        slot_id = free[0]["id"]
        print(f"[SLOT] Only one option available: slot {slot_id}")
    else:
        # Use LLM to pick the best (closest) slot
        try:
            msg = slot_prompt.invoke({
                "slots": json.dumps(free),
                "vehicle": json.dumps(vehicle),
            })
            res = llm.invoke(msg)
            slot_id = json.loads(res.content).get("slot_id")
            print(f"[SLOT] LLM selected slot {slot_id}")
        except Exception as e:
            print(f"[SLOT] LLM error, using closest fallback: {e}")
            # Fallback: Choose slot with minimum distance
            slot_id = min(free, key=lambda s: s["distance"])["id"]
            print(f"[SLOT] Fallback to closest slot: {slot_id}")

    # Mark slot as occupied
    for s in dt["slots"]:
        if s["id"] == slot_id:
            if s["status"] != "free":
                print(f"[SLOT] ⚠️ WARNING: Slot {slot_id} status is '{s['status']}', not 'free'!")
            s["status"] = "occupied"
            save_twin(dt)
            print(f"[SLOT] ✅ Assigned slot {slot_id} (size: {s['size']}, distance: {s['distance']}m)")
            return slot_id

    print(f"[SLOT] ❌ ERROR: Could not mark slot {slot_id} as occupied")
    return None


# LangGraph state definition
class EntryState(TypedDict, total=False):
    plate: str
    status: str
    message: str
    booking: dict
    model: str
    size: str
    slot_id: int
    price: float


def reservation_node(state: EntryState) -> EntryState:
    """Check if vehicle has a pre-booking"""
    plate = state.get("plate")
    
    if not plate:
        print(f"[RESERVATION] ERROR: No plate in state: {state}")
        return {
            **state,
            "status": "error",
            "message": "No plate provided to reservation node"
        }

    print(f"[RESERVATION] Checking booking for {plate}")
    booking = get_booking_by_plate(plate)

    if not booking:
        print(f"[RESERVATION] ❌ No booking found for {plate}")
        return {
            **state,
            "status": "no_booking",
            "message": f"Vehicle {plate} not pre-booked",
        }

    print(f"[RESERVATION] ✅ Found booking: {booking}")
    return {
        **state,
        "status": "booked",
        "booking": booking,
        "model": booking["model"],
        "size": booking["size"],
    }


def slot_node(state: EntryState) -> EntryState:
    """Assign an optimal parking slot with STRICT size matching"""
    plate = state.get("plate", "UNKNOWN")
    size = state.get("size", "medium")
    
    print(f"[SLOT] === Slot Assignment for {plate} (size: {size}) ===")

    slot = llm_select_slot({
        "plate": plate,
        "model": state.get("model"),
        "size": size,
    })

    if not slot:
        print(f"[SLOT] ❌ No compatible {size} slot available for {plate}")
        return {
            **state,
            "status": "no_slot",
            "message": f"No {size} slot available",
        }

    print(f"[SLOT] ✅ Assigned slot {slot} to {plate}")
    return {
        **state,
        "slot_id": slot
    }


def pricing_node(state: EntryState) -> EntryState:
    """Calculate dynamic pricing"""
    price = pricing()
    return {
        **state,
        "price": price
    }


def persist_node(state: EntryState) -> EntryState:
    """Save entry to database"""
    try:
        plate = state.get("plate")
        slot_id = state.get("slot_id")
        model = state.get("model")
        size = state.get("size")
        price = state.get("price")
        
        print(f"[PERSIST] Saving entry for {plate}")
        mark_booking_assigned(plate, slot_id)
        mark_entry(plate, model, size, slot_id, price)
        
        print(f"[PERSIST] ✅ {plate} entered successfully → Slot {slot_id} @ ${price}")
        return {
            **state,
            "status": "entered",
            "message": f"Vehicle {plate} entered successfully",
        }
    except Exception as e:
        print(f"[PERSIST] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state,
            "status": "error",
            "message": str(e),
        }


def router(state: EntryState) -> str:
    """Route to next node based on status"""
    status = state.get("status")
    print(f"[ROUTER] Current status: {status}")
    
    if status in ["no_booking", "no_slot", "error"]:
        return END
    return "slot"


# Entry agent
def entry_recognition_agent(vision_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry recognition workflow using LangGraph
    """
    plate = vision_payload.get("plate")
    if not plate:
        return {"status": "no_plate"}

    print(f"\n{'='*60}")
    print(f"[ENTRY AGENT] Starting workflow for plate: {plate}")
    print(f"{'='*60}\n")

    # Build graph (thread-safe per call)
    graph = StateGraph(EntryState)
    graph.add_node("reservation", reservation_node)
    graph.add_node("slot", slot_node)
    graph.add_node("pricing", pricing_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("reservation")
    graph.add_conditional_edges(
        "reservation",
        router,
        {"slot": "slot", END: END}
    )
    graph.add_edge("slot", "pricing")
    graph.add_edge("pricing", "persist")
    graph.add_edge("persist", END)

    entry_graph = graph.compile()

    try:
        # Initial state with plate
        initial_state: EntryState = {"plate": plate}
        print(f"[ENTRY AGENT] Initial state: {initial_state}")
        
        result = entry_graph.invoke(initial_state)
        
        print(f"\n[ENTRY AGENT] Final result: {result}")
        print(f"{'='*60}\n")
        return dict(result)
    except Exception as e:
        print(f"\n[ENTRY AGENT] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "plate": plate,
            "message": f"Graph execution error: {str(e)}",
        }