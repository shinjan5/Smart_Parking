import cv2
import time
import requests
import argparse
from pathlib import Path

FLASK_URL = "http://localhost:5000/vision/detect_plate"


def ingest_camera(source, interval=1.0):
    """
    Ingest frames from camera/video and send to Flask backend
    
    Args:
        source: Camera index (0), RTSP URL, or video/image file path
        interval: Seconds between frame processing
    """
    # Check if source is an image file
    source_path = Path(source) if isinstance(source, str) else None
    
    if source_path and source_path.exists() and source_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
        # Process single image
        print(f"Processing image: {source}")
        image = cv2.imread(str(source_path))
        
        if image is None:
            print(f"Error: Could not read image from {source}")
            return
        
        _, jpg = cv2.imencode(".jpg", image)
        files = {"file": jpg.tobytes()}
        
        try:
            r = requests.post(FLASK_URL, files=files, timeout=10)
            print(f"Response: {r.json()}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Display image
        cv2.imshow("Image (press 'q' to quit)", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return
    
    # Process video/camera stream
    cap = cv2.VideoCapture(source if isinstance(source, str) else int(source))
    
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera/video: {source}")
    
    print(f"Opened source: {source}")
    print(f"Processing interval: {interval}s")
    print("Press 'q' to quit")
    
    last_sent = 0
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("End of stream or error reading frame")
            break
        
        frame_count += 1
        now = time.time()
        
        # Send frame at specified interval
        if now - last_sent >= interval:
            _, jpg = cv2.imencode(".jpg", frame)
            files = {"file": jpg.tobytes()}
            
            try:
                r = requests.post(FLASK_URL, files=files, timeout=10)
                response = r.json()
                print(f"Frame {frame_count} - Response: {response}")
                
                # If plate detected, draw on frame
                if response.get("plate"):
                    cv2.putText(
                        frame,
                        f"Plate: {response['plate']}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2
                    )
            
            except requests.exceptions.Timeout:
                print(f"Frame {frame_count} - Request timeout")
            except Exception as e:
                print(f"Frame {frame_count} - Error: {e}")
            
            last_sent = now
        
        # Display frame
        cv2.imshow("Camera Ingest (q to quit)", frame)
        
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print(f"Processed {frame_count} frames")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest camera/video/image for ANPR processing"
    )
    parser.add_argument(
        "--source",
        default=0,
        help="Camera index (0), RTSP URL, video file path, or image file path"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.5,
        help="Seconds between frame processing"
    )
    
    args = parser.parse_args()
    
    # Convert source to appropriate type
    source = args.source
    if isinstance(source, str) and source.isdigit():
        source = int(source)
    
    ingest_camera(source, args.interval)