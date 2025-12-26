from flask import Flask, request, jsonify
from agentic import vision_agent_process, entry_recognition_agent
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

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
    Endpoint for uploading video - saves only, doesn't process
    """
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty filename"}), 400
        
        # Create temp directory if it doesn't exist (Windows compatible)
        import tempfile
        from pathlib import Path
        
        temp_dir = Path(tempfile.gettempdir()) / "smart_parking_uploads"
        temp_dir.mkdir(exist_ok=True)
        
        # Save video to temp directory
        video_path = temp_dir / file.filename
        file.save(str(video_path))
        
        return jsonify({
            "status": "uploaded",
            "path": str(video_path),
            "message": f"Video saved. Use: python ingestion/camera_ingest.py --source \"{video_path}\""
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/process-video", methods=["POST"])
def process_video():
    """
    Upload AND automatically process video
    Extracts frames at interval and detects plates
    """
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"status": "error", "message": "Empty filename"}), 400
        
        # Get interval parameter (default 1.5 seconds)
        interval = float(request.form.get('interval', 1.5))
        
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
        
        results = []
        processed_plates = set()  # Track plates already processed to avoid duplicates
        frame_count = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = int(fps * interval)
        
        print(f"Starting video processing: {file.filename}")
        print(f"FPS: {fps}, Frame interval: {frame_interval}")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame at interval
            if frame_count % frame_interval == 0:
                # Encode frame as JPEG
                _, jpg = cv2.imencode(".jpg", frame)
                image_bytes = jpg.tobytes()
                
                # Run vision agent
                vision = vision_agent_process(image_bytes)
                
                if vision.get("plate"):
                    plate = vision["plate"]
                    print(f"Frame {frame_count}: Detected plate {plate}")
                    
                    # Only process each unique plate once per video
                    if plate not in processed_plates:
                        processed_plates.add(plate)
                        
                        # Run entry recognition agent
                        result = entry_recognition_agent(vision)
                        
                        print(f"Entry recognition result: {result}")
                        
                        results.append({
                            "frame": frame_count,
                            "timestamp": frame_count / fps,
                            "plate": plate,
                            "result": result
                        })
                        
                        # If entry was successful, stop processing this plate
                        if result.get("status") == "entered":
                            print(f"Plate {plate} successfully entered. Continuing to look for other vehicles...")
                    else:
                        print(f"Frame {frame_count}: Plate {plate} already processed, skipping")
            
            frame_count += 1
        
        cap.release()
        
        print(f"Video processing complete. Total frames: {frame_count}, Unique plates: {len(results)}")
        
        return jsonify({
            "status": "completed",
            "video_path": str(video_path),
            "total_frames": frame_count,
            "unique_plates_detected": len(results),
            "detections": results
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
    app.run(debug=True, host="0.0.0.0", port=5000)