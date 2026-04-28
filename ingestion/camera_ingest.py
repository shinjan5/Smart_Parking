"""
camera_ingest.py  — Frame ingest client for the Smart Parking gate camera
Sends frames from a webcam, video file, RTSP stream, or still image to the
Flask backend for ANPR processing.

Usage:
    python camera_ingest.py --source 0              # webcam
    python camera_ingest.py --source car.jpg        # image
    python camera_ingest.py --source gate.mp4       # video file
    python camera_ingest.py --source rtsp://...     # IP camera
"""
import cv2
import time
import requests
import argparse
from pathlib import Path

FLASK_URL = "http://localhost:5000/vision/detect_plate"


def _post_frame(image_bytes: bytes) -> dict | None:
    """
    POST one JPEG frame to the detection endpoint.

    FIX: requests.post expects files as a 3-tuple
         (filename, file_object_or_bytes, content_type)
    The old code used  {"file": bytes}  which sends raw bytes without a
    filename or MIME type — Flask's request.files["file"].filename was ""
    and the content-type header was missing, causing subtle failures on
    some server configurations.
    """
    try:
        r = requests.post(
            FLASK_URL,
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            timeout=10,
        )
        return r.json()
    except requests.exceptions.Timeout:
        print("  [WARN] Request timed out")
        return None
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def _annotate_frame(frame, response: dict):
    """Draw plate text on the frame if detected."""
    plate = response.get("plate") or (response.get("entry_result") or {}).get("plate")
    if plate:
        cv2.putText(
            frame,
            f"Plate: {plate}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
    status = response.get("status", "")
    color  = (0, 200, 0) if status == "entered" else (0, 165, 255)
    cv2.putText(frame, status, (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


def ingest_camera(source, interval: float = 1.0):
    """
    Ingest frames from camera / video / image and send to the Flask backend.

    Args:
        source:   Camera index (int), RTSP URL, video file path, or image path.
        interval: Seconds between frame submissions (video/camera mode only).
    """
    # ── still image path ─────────────────────────────────────────────────────
    source_path = Path(source) if isinstance(source, str) else None
    IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    if source_path and source_path.exists() and source_path.suffix.lower() in IMAGE_EXTS:
        print(f"[INGEST] Processing image: {source}")
        image = cv2.imread(str(source_path))

        if image is None:
            print(f"[ERROR] Cannot read image: {source}")
            return

        success, jpg = cv2.imencode(".jpg", image)
        if not success:
            print("[ERROR] JPEG encoding failed")
            return

        response = _post_frame(jpg.tobytes())
        print(f"[INGEST] Response: {response}")

        if response:
            _annotate_frame(image, response)

        cv2.imshow("Image — press any key to close", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return

    # ── video / camera stream ─────────────────────────────────────────────────
    cap_source = int(source) if isinstance(source, str) and source.isdigit() else source
    cap = cv2.VideoCapture(cap_source)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open source: {source}")

    print(f"[INGEST] Opened: {source}")
    print(f"[INGEST] Sending every {interval} s — press 'q' to quit")

    last_sent   = 0.0
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[INGEST] End of stream or read error")
            break

        frame_count += 1
        now = time.time()

        if now - last_sent >= interval:
            success, jpg = cv2.imencode(".jpg", frame)
            if success:
                response = _post_frame(jpg.tobytes())
                if response:
                    print(f"[INGEST] Frame {frame_count}: {response}")
                    _annotate_frame(frame, response)
            last_sent = now

        cv2.imshow("Camera Ingest — q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"[INGEST] Done — processed {frame_count} frames total")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ANPR frame ingest client for the Smart Parking gate"
    )
    parser.add_argument(
        "--source",
        default=0,
        help="Camera index (0), RTSP URL, video file path, or image file path",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.5,
        help="Seconds between frame submissions (default: 1.5)",
    )

    args   = parser.parse_args()
    source = args.source

    # If user passes "0", "1" etc as string, convert to int for cv2
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    ingest_camera(source, args.interval)