# backend/agentic.py
import torch

import os
import json
import io
import re
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
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

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
if torch.cuda.is_available():
    reader = easyocr.Reader(["en"], gpu=True)
else:
    reader = easyocr.Reader(["en"], gpu=False)

llm = ChatOpenAI(
    model="openai/gpt-oss-120b:free",
    temperature=0,
    openai_api_key=os.environ.get("OPENROUTER_API_KEY"),
    openai_api_base="https://openrouter.ai/api/v1",
)

init_db()


# ---------------------------------------------------------------------------
# Content-extraction helper
# ---------------------------------------------------------------------------

def _extract_text(content) -> str:
    """
    Normalise an LLM response's `.content` field to a plain string.

    Gemini (and other providers) sometimes return a *list* of content blocks
    instead of a bare string, e.g.:
        [{'type': 'text', 'text': '{"status": "booked", ...}', ...}]

    This helper handles both shapes so downstream ``re.search`` calls always
    receive a ``str``.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return str(content)


# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------

def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def run_easyocr(processed_image) -> str:
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


# ---------------------------------------------------------------------------
# Vision agent (NO LLM)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Digital twin helpers
# ---------------------------------------------------------------------------

def load_twin() -> dict:
    with open(DIGITAL_TWIN_PATH) as f:
        return json.load(f)


def save_twin(dt: dict):
    with open(DIGITAL_TWIN_PATH, "w") as f:
        json.dump(dt, f, indent=2)


# ---------------------------------------------------------------------------
# RESERVATION TOOLS (used by the reservation agent)
# ---------------------------------------------------------------------------

@tool
def lookup_booking(plate: str) -> dict:
    """
    Query the bookings table for a pre-existing reservation matching the
    given licence plate.

    Args:
        plate: normalised alphanumeric licence plate string

    Returns a dict with keys:
        found   (bool)  - whether a booking exists
        booking (dict)  - full booking record if found, else {}
        message (str)   - human-readable summary
    """
    result = get_booking_by_plate(plate)
    if not result:
        msg = f"No booking found for plate {plate}"
        print(f"[TOOL:lookup_booking] {msg}")
        return {"found": False, "booking": {}, "message": msg}

    msg = (
        f"Booking found for {plate}: "
        f"model={result['model']}, size={result['size']}, status={result['status']}"
    )
    print(f"[TOOL:lookup_booking] {msg}")
    return {"found": True, "booking": result, "message": msg}


@tool
def validate_booking_status(plate: str, booking_status: str) -> dict:
    """
    Validate that a found booking is in an admissible state for entry.
    Only bookings with status 'pending' are eligible; 'entered' and 'exited'
    bookings are rejected to prevent double-entry.

    Args:
        plate:          licence plate
        booking_status: the status field from the booking record

    Returns a dict with keys:
        eligible (bool) - whether the booking may proceed to slot assignment
        reason   (str)  - explanation
    """
    ADMISSIBLE = {"pending"}
    eligible = booking_status in ADMISSIBLE
    if eligible:
        reason = f"Booking for {plate} is '{booking_status}' — eligible for entry"
    else:
        reason = (
            f"Booking for {plate} is '{booking_status}' "
            f"— NOT eligible (must be 'pending'; already entered or exited)"
        )
    print(f"[TOOL:validate_booking_status] {reason}")
    return {"eligible": eligible, "reason": reason}


# ---------------------------------------------------------------------------
# PRICING TOOLS (used by the pricing agent)
# ---------------------------------------------------------------------------

@tool
def get_current_occupancy() -> dict:
    """
    Fetch the current number of vehicles inside the parking facility
    and the total number of slots from the digital twin.
    Returns a dict with 'occupied' and 'total' counts.
    """
    dt = load_twin()
    total = len(dt["slots"])
    occupied = get_occupancy_counts()["entries"]
    ratio = round(occupied / total, 4) if total else 0
    print(f"[TOOL:occupancy] occupied={occupied}, total={total}, ratio={ratio}")
    return {"occupied": occupied, "total": total, "ratio": ratio}


@tool
def calculate_dynamic_price(occupied: int, total: int) -> dict:
    """
    Apply the dynamic pricing formula to derive the current parking fee.

    Formula:
        price = BASE_PRICE * (1 + ELASTICITY * max(0, ratio - 0.5))
        where ratio = occupied / total

    BASE_PRICE  = 50  (INR)
    ELASTICITY  = 1.2

    Args:
        occupied: number of currently occupied slots
        total:    total number of slots in the facility

    Returns a dict with 'price' (float, rounded to 2 dp) and a 'reasoning' string.
    """
    ratio = occupied / total if total else 0
    raw_price = BASE_PRICE * (1 + ELASTICITY * max(0, ratio - 0.5))
    price = round(raw_price if isfinite(raw_price) else BASE_PRICE, 2)
    reasoning = (
        f"ratio={ratio:.2%}, surcharge_factor={max(0, ratio - 0.5):.4f}, "
        f"raw_price=INR {raw_price:.4f} -> final=INR {price}"
    )
    print(f"[TOOL:pricing] {reasoning}")
    return {"price": price, "reasoning": reasoning}


# ---------------------------------------------------------------------------
# PERSIST TOOLS (used by the persist agent)
# ---------------------------------------------------------------------------

@tool
def assign_slot_to_booking(plate: str, slot_id: int) -> dict:
    """
    Mark the given slot as assigned to a booking in the database,
    updating the booking status to 'entered'.

    Args:
        plate:   vehicle licence plate (normalised, alphanumeric)
        slot_id: the parking slot id that was allocated

    Returns a dict with 'success' bool and a 'message'.
    """
    try:
        mark_booking_assigned(plate, slot_id)
        msg = f"Booking for {plate} updated -> slot {slot_id}, status=entered"
        print(f"[TOOL:assign_slot] {msg}")
        return {"success": True, "message": msg}
    except Exception as e:
        print(f"[TOOL:assign_slot] ERROR: {e}")
        return {"success": False, "message": str(e)}


@tool
def record_vehicle_entry(plate: str, model: str, size: str, slot_id: int, price: float) -> dict:
    """
    Insert a new entry record into the entries table.
    Skips if an active (non-exited) entry already exists for this plate
    to prevent duplicates.

    Args:
        plate:   vehicle licence plate
        model:   vehicle model name
        size:    vehicle/slot size class (small | medium | large)
        slot_id: allocated parking slot id
        price:   dynamic parking fee in INR

    Returns a dict with 'success' bool and a 'message'.
    """
    try:
        mark_entry(plate, model, size, slot_id, price)
        msg = f"Entry recorded: {plate} ({model}, {size}) -> slot {slot_id} @ INR {price}"
        print(f"[TOOL:record_entry] {msg}")
        return {"success": True, "message": msg}
    except Exception as e:
        print(f"[TOOL:record_entry] ERROR: {e}")
        return {"success": False, "message": str(e)}


# ---------------------------------------------------------------------------
# LLM instances bound to their respective tool-sets
# ---------------------------------------------------------------------------

reservation_tools = [lookup_booking, validate_booking_status]
pricing_tools     = [get_current_occupancy, calculate_dynamic_price]
persist_tools     = [assign_slot_to_booking, record_vehicle_entry]

reservation_llm = llm.bind_tools(reservation_tools)
pricing_llm     = llm.bind_tools(pricing_tools)
persist_llm     = llm.bind_tools(persist_tools)


# ---------------------------------------------------------------------------
# Slot selection (LLM prompt + deterministic argmin fallback)
# ---------------------------------------------------------------------------

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


def size_compatible_strict(slot_size: str, vehicle_size: str) -> bool:
    return slot_size == vehicle_size


def llm_select_slot(vehicle: Dict[str, Any]) -> Optional[int]:
    dt = load_twin()
    size  = vehicle.get("size", "medium")
    plate = vehicle.get("plate", "UNKNOWN")

    print(f"[SLOT] Finding slot for {plate} (size: {size})")
    print(f"[SLOT] Current slots state: {json.dumps(dt['slots'], indent=2)}")

    free = [
        s for s in dt["slots"]
        if s["status"] == "free" and size_compatible_strict(s["size"], size)
    ]

    if not free:
        print(f"[SLOT] No free {size} slots available!")
        for slot_size in ["small", "medium", "large"]:
            count = sum(
                1 for s in dt["slots"]
                if s["size"] == slot_size and s["status"] == "free"
            )
            print(f"  - {slot_size}: {count} free")
        return None

    print(f"[SLOT] Found {len(free)} free {size} slot(s): {[s['id'] for s in free]}")

    if len(free) == 1:
        slot_id = free[0]["id"]
        print(f"[SLOT] Only one option available: slot {slot_id}")
    else:
        try:
            msg = slot_prompt.invoke({
                "slots": json.dumps(free),
                "vehicle": json.dumps(vehicle),
            })
            res = llm.invoke(msg)
            res_text = _extract_text(res.content)
            print(f"[SLOT] Raw LLM response: {res_text}")
            match = re.search(r'\{.*\}', res_text)
            if not match:
                raise ValueError("No JSON found in LLM response")
            slot_json = match.group()
            slot_id = json.loads(slot_json).get("slot_id")
            if slot_id is None:
                raise ValueError("slot_id missing in JSON")
            print(f"[SLOT] LLM selected slot {slot_id}")
        except Exception as e:
            print(f"[SLOT] LLM error, using closest fallback: {e}")
            slot_id = min(free, key=lambda s: s["distance"])["id"]
            print(f"[SLOT] Fallback to closest slot: {slot_id}")

    for s in dt["slots"]:
        if s["id"] == slot_id:
            if s["status"] != "free":
                print(f"[SLOT] WARNING: Slot {slot_id} status is '{s['status']}', not 'free'!")
            s["status"] = "occupied"
            save_twin(dt)
            print(
                f"[SLOT] Assigned slot {slot_id} "
                f"(size: {s['size']}, distance: {s['distance']}m)"
            )
            return slot_id

    print(f"[SLOT] ERROR: Could not mark slot {slot_id} as occupied")
    return None


# ---------------------------------------------------------------------------
# LangGraph state definition
# ---------------------------------------------------------------------------

class EntryState(TypedDict, total=False):
    plate: str
    status: str
    message: str
    booking: dict
    model: str
    size: str
    slot_id: int
    price: float
    # internal message histories (stripped before returning to caller)
    reservation_messages: list
    pricing_messages: list
    persist_messages: list


# ---------------------------------------------------------------------------
# RESERVATION AGENT — fully agentic ReAct loop
# ---------------------------------------------------------------------------

_RESERVATION_SYSTEM = """You are the reservation verification agent for a smart parking system.

Your job is to confirm whether an arriving vehicle has a valid pre-booking.

Follow these steps EXACTLY using the available tools:
1. Call `lookup_booking` with the plate number to check if a reservation exists.
2. If a booking IS found, call `validate_booking_status` with the plate and
   the booking's status field to confirm the booking is eligible for entry.
3. Based on the tool results, return ONLY one of these two JSON shapes:

   Vehicle may enter:
   {"status": "booked", "model": "<model>", "size": "<size>", "message": "<summary>"}

   Vehicle must be denied (no booking, or ineligible status):
   {"status": "no_booking", "message": "<reason>"}

Do NOT invent booking records. Do NOT skip tool calls."""


def reservation_node(state: EntryState) -> EntryState:
    """
    Fully agentic reservation node.
    The LLM autonomously calls lookup_booking then validate_booking_status
    via a ReAct loop, then emits a structured admission decision.
    """
    plate = state.get("plate")

    if not plate:
        print("[RESERVATION AGENT] ERROR: No plate in state")
        return {
            **state,
            "status": "error",
            "message": "No plate provided to reservation agent",
        }

    print(f"[RESERVATION AGENT] Starting agentic loop for plate: {plate} ...")

    messages = [
        {"role": "system", "content": _RESERVATION_SYSTEM},
        {
            "role": "user",
            "content": f"Check if vehicle with plate '{plate}' has a valid pre-booking.",
        },
    ]

    tool_executor = ToolNode(reservation_tools)

    # Safe defaults
    final_status  = "no_booking"
    final_message = "Reservation agent did not complete"
    booking_model = None
    booking_size  = None

    # ReAct loop — max 6 iterations
    for step in range(6):
        response = reservation_llm.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            # LLM finished — parse its structured JSON decision
            print(f"[RESERVATION AGENT] Final response: {response.content}")
            try:
                match = re.search(r'\{.*?\}', _extract_text(response.content), re.DOTALL)
                if match:
                    parsed        = json.loads(match.group())
                    final_status  = parsed.get("status", "no_booking")
                    final_message = parsed.get("message", "")
                    booking_model = parsed.get("model")
                    booking_size  = parsed.get("size")
            except Exception as e:
                print(f"[RESERVATION AGENT] Could not parse final response: {e}")
            break

        # Execute tool calls and append ToolMessage results
        tool_results = tool_executor.invoke({"messages": messages})
        for tm in tool_results.get("messages", []):
            messages.append(tm)
            print(f"[RESERVATION AGENT] Tool result: {tm.content}")

    print(f"[RESERVATION AGENT] status={final_status} | {final_message}")

    if final_status == "booked" and booking_model and booking_size:
        # Fetch full record so downstream nodes have the complete booking dict
        booking = get_booking_by_plate(plate) or {}
        return {
            **state,
            "status":  "booked",
            "booking": booking,
            "model":   booking_model,
            "size":    booking_size,
            "message": final_message,
            "reservation_messages": messages,
        }

    return {
        **state,
        "status":  final_status,
        "message": final_message,
        "reservation_messages": messages,
    }


# ---------------------------------------------------------------------------
# SLOT NODE
# ---------------------------------------------------------------------------

def slot_node(state: EntryState) -> EntryState:
    """Assign an optimal parking slot with STRICT size matching."""
    plate = state.get("plate", "UNKNOWN")
    size  = state.get("size", "medium")

    print(f"[SLOT] === Slot Assignment for {plate} (size: {size}) ===")

    slot = llm_select_slot({
        "plate": plate,
        "model": state.get("model"),
        "size":  size,
    })

    if not slot:
        print(f"[SLOT] No compatible {size} slot available for {plate}")
        return {
            **state,
            "status":  "no_slot",
            "message": f"No {size} slot available",
        }

    print(f"[SLOT] Assigned slot {slot} to {plate}")
    return {**state, "slot_id": slot}


# ---------------------------------------------------------------------------
# PRICING AGENT — fully agentic ReAct loop
# ---------------------------------------------------------------------------

_PRICING_SYSTEM = """You are the dynamic pricing agent for a smart parking system.

Your job is to determine the correct parking fee for a vehicle that is about to enter.

Follow these steps EXACTLY using the available tools:
1. Call `get_current_occupancy` to learn how many slots are occupied and the total capacity.
2. Call `calculate_dynamic_price` with the occupied and total values you just retrieved.
3. Return ONLY a JSON object: {"price": <number>}

Do NOT skip either tool call. Do NOT invent occupancy numbers."""


def pricing_node(state: EntryState) -> EntryState:
    """Fully agentic pricing node using a ReAct loop."""
    print("[PRICING AGENT] Starting agentic pricing loop ...")

    messages = [
        {"role": "system", "content": _PRICING_SYSTEM},
        {"role": "user",   "content": "Calculate the current dynamic parking fee."},
    ]

    tool_executor = ToolNode(pricing_tools)
    price = BASE_PRICE  # safe default

    for step in range(6):
        response = pricing_llm.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            print(f"[PRICING AGENT] Final response: {response.content}")
            try:
                match = re.search(r'\{.*?\}', _extract_text(response.content), re.DOTALL)
                if match:
                    price = float(json.loads(match.group()).get("price", BASE_PRICE))
            except Exception as e:
                print(f"[PRICING AGENT] Could not parse price: {e}")
            break

        tool_results = tool_executor.invoke({"messages": messages})
        for tm in tool_results.get("messages", []):
            messages.append(tm)
            print(f"[PRICING AGENT] Tool result: {tm.content}")

    print(f"[PRICING AGENT] Final price: INR {price}")
    return {**state, "price": price, "pricing_messages": messages}


# ---------------------------------------------------------------------------
# PERSIST AGENT — fully agentic ReAct loop
# ---------------------------------------------------------------------------

_PERSIST_SYSTEM = """You are the persistence agent for a smart parking system.

Your job is to durably record that a vehicle has entered the parking facility.
You have access to two tools:

1. `assign_slot_to_booking` - updates the booking record with the assigned slot.
2. `record_vehicle_entry`   - inserts the entry record (plate, model, size, slot, price).

Call BOTH tools. Call `assign_slot_to_booking` FIRST, then `record_vehicle_entry`.
After both succeed, respond with JSON: {"status": "entered", "message": "<summary>"}
If either tool fails, respond with JSON: {"status": "error", "message": "<reason>"}"""


def persist_node(state: EntryState) -> EntryState:
    """Fully agentic persist node using a ReAct loop."""
    plate   = state.get("plate", "UNKNOWN")
    slot_id = state.get("slot_id")
    model   = state.get("model", "unknown")
    size    = state.get("size", "medium")
    price   = state.get("price", BASE_PRICE)

    print(f"[PERSIST AGENT] Starting agentic persist loop for {plate} ...")

    user_msg = (
        f"Persist the parking entry for vehicle {plate}.\n"
        f"Details: model={model}, size={size}, slot_id={slot_id}, price={price}"
    )

    messages = [
        {"role": "system", "content": _PERSIST_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]

    tool_executor = ToolNode(persist_tools)
    final_status  = "error"
    final_message = "Persist agent did not complete"

    for step in range(8):
        response = persist_llm.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            print(f"[PERSIST AGENT] Final response: {response.content}")
            try:
                match = re.search(r'\{.*?\}', _extract_text(response.content), re.DOTALL)
                if match:
                    parsed        = json.loads(match.group())
                    final_status  = parsed.get("status", "error")
                    final_message = parsed.get("message", "")
            except Exception as e:
                print(f"[PERSIST AGENT] Could not parse final response: {e}")
            break

        tool_results = tool_executor.invoke({"messages": messages})
        for tm in tool_results.get("messages", []):
            messages.append(tm)
            print(f"[PERSIST AGENT] Tool result: {tm.content}")

    print(f"[PERSIST AGENT] status={final_status} | {final_message}")
    return {
        **state,
        "status":  final_status,
        "message": final_message,
        "persist_messages": messages,
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def router(state: EntryState) -> str:
    """Route to slot assignment or terminate based on reservation outcome."""
    status = state.get("status")
    print(f"[ROUTER] Current status: {status}")
    if status in ["no_booking", "no_slot", "error"]:
        return END
    return "slot"


# ---------------------------------------------------------------------------
# Entry agent — master LangGraph pipeline
# ---------------------------------------------------------------------------

def entry_recognition_agent(vision_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry recognition workflow using LangGraph.

    Graph topology:
        reservation --> [router] --> slot --> pricing --> persist --> END
                                 |
                                 +--> END  (on no_booking / no_slot / error)

    All four pipeline nodes are fully agentic ReAct loops:
        - reservation : lookup_booking, validate_booking_status
        - slot        : LLM prompt + deterministic argmin fallback
        - pricing     : get_current_occupancy, calculate_dynamic_price
        - persist     : assign_slot_to_booking, record_vehicle_entry
    """
    plate = vision_payload.get("plate")
    if not plate:
        return {"status": "no_plate"}

    print(f"\n{'='*60}")
    print(f"[ENTRY AGENT] Starting workflow for plate: {plate}")
    print(f"{'='*60}\n")

    graph = StateGraph(EntryState)
    graph.add_node("reservation", reservation_node)
    graph.add_node("slot",        slot_node)
    graph.add_node("pricing",     pricing_node)
    graph.add_node("persist",     persist_node)

    graph.set_entry_point("reservation")
    graph.add_conditional_edges(
        "reservation",
        router,
        {"slot": "slot", END: END}
    )
    graph.add_edge("slot",    "pricing")
    graph.add_edge("pricing", "persist")
    graph.add_edge("persist", END)

    entry_graph = graph.compile()

    try:
        initial_state: EntryState = {"plate": plate}
        print(f"[ENTRY AGENT] Initial state: {initial_state}")

        result = entry_graph.invoke(initial_state)

        # Strip internal message histories before returning to caller
        result.pop("reservation_messages", None)
        result.pop("pricing_messages",     None)
        result.pop("persist_messages",     None)

        print(f"\n[ENTRY AGENT] Final result: {result}")
        print(f"{'='*60}\n")
        return dict(result)

    except Exception as e:
        print(f"\n[ENTRY AGENT] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status":  "error",
            "plate":   plate,
            "message": f"Graph execution error: {str(e)}",
        }