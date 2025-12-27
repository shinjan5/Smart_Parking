from flask import Flask, request, jsonify
from agentic import vision_agent_process, entry_recognition_agent
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

def get_majority_value(values):
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1

    # pick value with max count
    majority_value = max(counts, key=counts.get)
    return majority_value, counts


@app.route("/vision/detect_plate", methods=["POST"])
def detect_plate():
    """
    Endpoint for license plate detection and entry processing
    Accepts: multipart/form-data with 'file' field
    Returns: JSON with detection and entry status
    """
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty filename"}), 400
        
        # Read image bytes
        image_bytes = file.read()
        
        # Run vision agent
        vision = vision_agent_process(image_bytes)
        
        
        if not vision.get("plate"):
            return jsonify({"status": "no_plate_detected"})
        
        # Run entry recognition agent
        result = entry_recognition_agent(vision)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok"})


@app.route("/upload-video", methods=["POST"])
def upload_video():
    """
    Simple video upload endpoint - saves file only
    """
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty filename"}), 400
        
        # Create temp directory
        import tempfile
        from pathlib import Path
        
        temp_dir = Path(tempfile.gettempdir()) / "smart_parking_uploads"
        temp_dir.mkdir(exist_ok=True)
        
        # Save video
        video_path = temp_dir / file.filename
        file.save(str(video_path))
        
        return jsonify({
            "status": "uploaded",
            "path": str(video_path),
            "message": f"Video saved. Use /process-video endpoint for plate detection."
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


def get_most_frequent_plate(plate_detections):
    """
    Get the most frequently detected plate from a list of detections
    Returns the plate with highest count and the detection statistics
    """
    if not plate_detections:
        return None, {}
    
    from collections import Counter
    plate_counts = Counter(plate_detections)
    most_common_plate = plate_counts.most_common(1)[0][0]
    
    return most_common_plate, dict(plate_counts)


@app.route("/process-video", methods=["POST"])
def process_video():
    """
    Upload AND automatically process video
    Processes 5 frames per second and uses majority voting for plate detection
    """
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty filename"}), 400
        
        # Create temp directory
        import tempfile
        from pathlib import Path
        import cv2
        
        temp_dir = Path(tempfile.gettempdir()) / "smart_parking_uploads"
        temp_dir.mkdir(exist_ok=True)
        
        # Save video
        video_path = temp_dir / file.filename
        file.save(str(video_path))
        
        # Process video
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            return jsonify({
                "status": "error",
                "message": "Cannot open video file"
            }), 400
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        # Process 5 frames per second
        frame_interval = max(1, int(fps / 5))
        
        print(f"Starting video processing: {file.filename}")
        print(f"Video FPS: {fps}, Processing every {frame_interval} frames (5 FPS)")
        
        frame_count = 0
        detected_plates = []  # Store all detected plates for majority voting
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Check if frame is valid
            if frame is None or frame.size == 0:
                frame_count += 1
                continue
            
            # Process every Nth frame to achieve 5 FPS processing
            if frame_count % frame_interval == 0:
                # Encode frame as JPEG
                success, jpg = cv2.imencode(".jpg", frame)
                if not success:
                    frame_count += 1
                    continue
                    
                image_bytes = jpg.tobytes()
                
                # Run vision agent
                vision = vision_agent_process(image_bytes)
                
                if vision.get("plate"):
                    plate = vision["plate"]
                    detected_plates.append(plate)
                    print(f"Frame {frame_count} ({frame_count/fps:.1f}s): Detected plate {plate}")
            
            frame_count += 1
        
        cap.release()
        
        # Use majority voting to get the final plate
        if detected_plates:
            final_plate, plate_statistics = get_most_frequent_plate(detected_plates)
            
            print(f"Plate detection summary:")
            print(f"  Total detections: {len(detected_plates)}")
            print(f"  Unique plates: {list(plate_statistics.keys())}")
            print(f"  Detection counts: {plate_statistics}")
            print(f"  Selected plate: {final_plate}")
            
            # Process the final selected plate
            result = entry_recognition_agent({"plate": final_plate})
            
            return jsonify({
                "status": "completed",
                "video_path": str(video_path),
                "total_frames": frame_count,
                "processed_frames": len(detected_plates),
                "plate": final_plate,
                "entry_result": result
            })
        else:
            print("No plates detected in video")
            return jsonify({
                "status": "no_plates_detected",
                "video_path": str(video_path),
                "total_frames": frame_count,
                "message": "No license plates detected in the video"
            })
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error processing video: {error_details}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "details": error_details
        }), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)