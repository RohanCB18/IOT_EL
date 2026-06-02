import cv2
import yaml
from ultralytics import YOLO
from pathlib import Path

class PersonDetector:
    def __init__(self, config_path="config.yaml"):
        # Load configuration
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)["detection"]
        
        self.conf_threshold = self.config["confidence"]
        self.imgsz = self.config["imgsz"]
        self.model_path = self.config["model_path"]
        
        print(f"[INFO] Loading YOLO model from {self.model_path}...")
        self.model = YOLO(self.model_path)
        print("[INFO] Model loaded.")

    def detect(self, frame):
        """
        Runs person detection on a frame.
        Returns a list of centroids and bounding boxes.
        """
        # We only care about the person class (class id 0 in COCO)
        results = self.model(frame, imgsz=self.imgsz, conf=self.conf_threshold, classes=[0], verbose=False)
        
        centroids = []
        boxes = []
        
        for r in results:
            for box in r.boxes:
                # Bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Compute centroid
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                
                centroids.append((cx, cy))
                boxes.append((int(x1), int(y1), int(x2), int(y2)))
                
        return centroids, boxes

    def draw_detections(self, frame, centroids, boxes):
        """
        Helper method to visualize detections on the frame.
        """
        vis_frame = frame.copy()
        
        for (x1, y1, x2, y2), (cx, cy) in zip(boxes, centroids):
            # Draw bounding box (sleek thickness 1)
            cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
            # Draw centroid (sleek radius 3)
            cv2.circle(vis_frame, (int(cx), int(cy)), 3, (0, 0, 255), -1)
            
        return vis_frame

# Quick test script when run directly
if __name__ == "__main__":
    import os
    
    detector = PersonDetector("config.yaml")
    
    # Override model path if NCNN export doesn't exist yet
    if not os.path.exists("models/yolov8n_ncnn_model"):
        print("[WARNING] NCNN model not found. Falling back to yolov8n.pt")
        detector.model = YOLO("yolov8n.pt")
    
    # Initialize camera (0 is usually the built-in webcam)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        exit(1)
        
    print("[INFO] Starting video stream... Press 'q' to exit.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Detect
        centroids, boxes = detector.detect(frame)
        
        # Visualize
        vis_frame = detector.draw_detections(frame, centroids, boxes)
        
        # Add count text
        cv2.putText(vis_frame, f"Count: {len(centroids)}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                    
        cv2.imshow("Person Detection Test", vis_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
