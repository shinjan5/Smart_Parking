"""
backend/flask_backend.py
Flask REST API — Smart Parking System
"""
from flask import Flask, request, jsonify
from agentic import vision_agent_process, entry_recognition_agent
import os, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Path to the digital twin — resolved relative to this file so it works
# regardless of the working directory the server is launched from.
DIGITAL_TWIN_PATH = Path(__file__).parent / "mock_digital_twin.json"

app = Flask(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_twin() -> dict:
    with open(DIGITAL_TWIN_PATH) as f:
        return json.load(f)


def _save_twin(dt: dict):
    with open(DIGITAL_TWIN_PATH, "w") as f:
        json.dump(dt, f, indent=2)


def _free_slot_in_twin(slot_id: int):
    """Mark a slot as free in the digital twin."""
    dt = _load_twin()
    for s in dt["slots"]:
        if s["id"] == slot_id:
            s["status"] = "free"
            _save_twin(dt)
            return True
    return False


def get_majority_value(values):
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    majority_value = max(counts, key=counts.get)
    return majority_value, counts


def get_most_frequent_plate(plate_detections):
    if not plate_detections:
        return None, {}
    from collections import Counter
    plate_counts = Counter(plate_detections)
    most_common_plate = plate_counts.most_common(1)[0][0]
    return most_common_plate, dict(plate_counts)


# ── health ───────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ── booking creation (called by frontend) ────────────────────────────────────

@app.route("/bookings/create", methods=["POST"])
def create_booking_endpoint():
    """
    Create a new pre-booking.

    Accepts JSON:  { "plate": "...", "model": "...", "size": "small|medium|large" }
    Returns:       { "status": "created" | "exists" | "error", "booking": {...} }
    """
    try:
        data = request.get_json(force=True)
        plate = (data.get("plate") or "").strip().upper()
        model = (data.get("model") or "").strip()
        size  = (data.get("size")  or "medium").strip().lower()

        if not plate or not model:
            return jsonify({"status": "error", "message": "plate and model are required"}), 400

        if len(plate) < 4:
            return jsonify({"status": "error", "message": "plate must be at least 4 characters"}), 400

        if size not in ("small", "medium", "large"):
            return jsonify({"status": "error", "message": "size must be small, medium, or large"}), 400

        from sqlite_helper import get_booking_by_plate, create_booking

        existing = get_booking_by_plate(plate)
        if existing:
            return jsonify({"status": "exists", "booking": existing})

        create_booking(plate, model, size)
        booking = get_booking_by_plate(plate)
        return jsonify({"status": "created", "booking": booking})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── plate detection + entry pipeline ─────────────────────────────────────────

@app.route("/vision/detect_plate", methods=["POST"])
def detect_plate():
    """
    Accepts: multipart/form-data  { file: <image> }
    Returns: JSON with detection and pipeline status
    """
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "Empty filename"}), 400

        image_bytes = file.read()
        vision = vision_agent_process(image_bytes)

        if not vision.get("plate"):
            return jsonify({"status": "no_plate_detected"})

        result = entry_recognition_agent(vision)
        return jsonify(result)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── vehicle exit ─────────────────────────────────────────────────────────────

@app.route("/exit", methods=["POST"])
def vehicle_exit():
    """
    Record a vehicle exit, free the DB entry, and reset the slot in the
    digital twin so it can be re-assigned.

    Accepts JSON:  { "plate": "..." }
    Returns:       { "status": "exited" | "not_found" | "error", ... }
    """
    try:
        data  = request.get_json(force=True)
        plate = (data.get("plate") or "").strip().upper()

        if not plate:
            return jsonify({"status": "error", "message": "plate is required"}), 400

        from sqlite_helper import mark_exit, get_entry_by_plate

        # Get the slot_id BEFORE marking exit (so we can free it in the twin)
        entry = get_entry_by_plate(plate)
        if not entry:
            return jsonify({"status": "not_found", "message": f"No active entry for {plate}"})

        slot_id = entry["slot_id"]

        # Mark exit in DB
        mark_exit(plate)

        # Free the slot in the digital twin
        freed = _free_slot_in_twin(slot_id)

        return jsonify({
            "status":  "exited",
            "plate":   plate,
            "slot_id": slot_id,
            "twin_slot_freed": freed,
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── video upload (save only) ──────────────────────────────────────────────────

@app.route("/upload-video", methods=["POST"])
def upload_video():
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "Empty filename"}), 400

        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "smart_parking_uploads"
        temp_dir.mkdir(exist_ok=True)
        video_path = temp_dir / file.filename
        file.save(str(video_path))

        return jsonify({
            "status":  "uploaded",
            "path":    str(video_path),
            "message": "Video saved. Use /process-video for plate detection.",
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── video processing ──────────────────────────────────────────────────────────

@app.route("/process-video", methods=["POST"])
def process_video():
    """
    Upload and process a video file.
    Samples at 5 FPS, applies majority-vote plate selection, runs entry pipeline.
    """
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "Empty filename"}), 400

        import tempfile, cv2
        temp_dir = Path(tempfile.gettempdir()) / "smart_parking_uploads"
        temp_dir.mkdir(exist_ok=True)
        video_path = temp_dir / file.filename
        file.save(str(video_path))

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return jsonify({"status": "error", "message": "Cannot open video file"}), 400

        fps            = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(fps / 5))
        print(f"[VIDEO] FPS={fps}, processing every {frame_interval} frames")

        frame_count     = 0
        detected_plates = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame is None or frame.size == 0:
                frame_count += 1
                continue
            if frame_count % frame_interval == 0:
                success, jpg = cv2.imencode(".jpg", frame)
                if success:
                    vision = vision_agent_process(jpg.tobytes())
                    if vision.get("plate"):
                        detected_plates.append(vision["plate"])
                        print(f"[VIDEO] Frame {frame_count}: {vision['plate']}")
            frame_count += 1

        cap.release()

        if not detected_plates:
            return jsonify({
                "status":       "no_plates_detected",
                "total_frames": frame_count,
                "message":      "No licence plates detected in the video",
            })

        final_plate, stats = get_most_frequent_plate(detected_plates)
        result = entry_recognition_agent({"plate": final_plate})

        return jsonify({
            "status":           "completed",
            "total_frames":     frame_count,
            "processed_frames": len(detected_plates),
            "plate":            final_plate,
            "detection_stats":  stats,
            "entry_result":     result,
        })

    except Exception as e:
        import traceback
        return jsonify({
            "status":  "error",
            "message": str(e),
            "details": traceback.format_exc(),
        }), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)