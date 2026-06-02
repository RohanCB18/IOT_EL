"""
main.py — Full pipeline orchestrator (Phase 3C)

Pipeline per frame:
    webcam / video
        └─► PersonDetector   (Phase 1)  → centroids, boxes
        └─► DensityMapper    (Phase 2A) → density, labels, heatmap, level
        └─► OpticalFlowAnalyser (Phase 2B) → flow metrics, flow_bgr
        └─► RiskEngine       (Phase 3A) → risk_score, alert_level, gate_command
        └─► MQTTPublisher    (Phase 3B) → publish all topics
        └─► cv2.imshow        (display)
"""

import sys
import time
import cv2
import yaml

from detector     import PersonDetector
from density      import DensityMapper
from optical_flow import OpticalFlowAnalyser
from risk_engine  import RiskEngine
from mqtt_client  import MQTTPublisher
from utils        import encode_frame_base64


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _open_capture(source):
    """Opens a cv2 VideoCapture. source can be int (webcam) or str (video path)."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video source: {source}")
        sys.exit(1)
    return cap


def _annotate_hud(frame, count: int, density: float, level: str,
                  risk_score: float, alert_level: str, gate_command: str,
                  trend_slope: float, ttc, flow_mag: float, divergence: float, chaos: float):
    """Writes a clean, modern HUD overlay with a semi-transparent background."""
    # Define Alert colors (BGR format)
    colours = {
        "SAFE":     (74, 222, 128),   # BGR mint green
        "WARNING":  (36, 191, 251),   # BGR bright amber
        "CRITICAL": (68, 68, 239),    # BGR bright vibrant red
    }
    theme_colour = colours.get(alert_level, (255, 255, 255))
    
    # Structure metrics into sections for supreme readability: (label, value, value_color)
    hud_data = [
        # --- Section 1: System Metrics ---
        (None, "[ SYSTEM METRICS ]", (220, 220, 220)),
        ("People Count:", f"{count}", (255, 255, 255)),
        ("Density:", f"{density:.2f} p/m^2", theme_colour),
        ("LOS Level:", f"{level}", theme_colour),
        
        # --- Section 2: Risk Analysis ---
        (None, "[ RISK ANALYSIS ]", (220, 220, 220)),
        ("Composite Risk:", f"{risk_score:.3f}", theme_colour),
        ("Alert Level:", f"{alert_level}", theme_colour),
        ("Gate Actuator:", f"{gate_command}", theme_colour),
        
        # --- Section 3: Motion Flow ---
        (None, "[ MOTION FLOW ]", (220, 220, 220)),
        ("Trend Slope:", f"{trend_slope:+.4f} R/s", (255, 255, 255)),
        ("Time-To-Crit:", f"{f'{ttc:.1f}s' if ttc is not None else 'N/A'}", (255, 255, 255)),
        ("Flow Speed:", f"{flow_mag:.2f} px/f", (255, 255, 255)),
        ("Divergence:", f"{divergence:+.4f}", (255, 255, 255)),
        ("Crowd Chaos:", f"{chaos:.3f} rad", (255, 255, 255)),
    ]

    # Draw semi-transparent dark slate background box with ample padding
    # Box dimensions: width = 250px, height = 270px
    x1, y1 = 10, 10
    x2, y2 = 260, 280
    
    overlay_box = frame.copy()
    cv2.rectangle(overlay_box, (x1, y1), (x2, y2), (25, 18, 12), -1)  # Dark slate background
    cv2.addWeighted(overlay_box, 0.8, frame, 0.2, 0, frame)
    
    # Draw a thin borders themed with alert state for premium aesthetic
    cv2.rectangle(frame, (x1, y1), (x2, y2), theme_colour, 1, cv2.LINE_AA)

    y_offset = y1 + 18
    for label, value, val_color in hud_data:
        if label is None:
            # Draw section header
            cv2.putText(frame, value, (x1 + 12, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, val_color, 1, cv2.LINE_AA)
            y_offset += 16
        else:
            # Draw metric label in muted gray
            cv2.putText(frame, label, (x1 + 12, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 180, 180), 1, cv2.LINE_AA)
            # Draw value aligned to the right (x = 125)
            cv2.putText(frame, value, (x1 + 125, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, val_color, 1, cv2.LINE_AA)
            y_offset += 16
            
    return frame


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(config_path: str = "config.yaml", show_display: bool = True):
    cfg    = _load_config(config_path)
    source = cfg["camera"]["source"]

    # ---- Instantiate pipeline components -----------------------------------
    detector = PersonDetector(config_path)
    mapper   = DensityMapper(config_path)
    flow_analyser = OpticalFlowAnalyser()
    engine   = RiskEngine(config_path)
    mqtt_pub = MQTTPublisher(config_path)

    # ---- Connect MQTT (non-blocking) ---------------------------------------
    mqtt_pub.connect()
    time.sleep(0.8)   # allow handshake

    if not mqtt_pub.connected:
        print("[WARNING] MQTT broker not reachable. Pipeline continues without publishing.")

    # ---- Open video source --------------------------------------------------
    cap = _open_capture(source)
    print(f"[INFO] Pipeline running. Source={source}  Press 'q' to quit.")

    if show_display:
        cv2.namedWindow("Oracle - Crowd Safety Pipeline", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Oracle - Crowd Safety Pipeline", cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_KEEPRATIO)

    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] End of stream or read error.")
                break

            # Resize frame to configured resolution for high performance and proper window sizing
            res = cfg["camera"].get("resolution")
            if res and isinstance(res, list) and len(res) == 2:
                frame = cv2.resize(frame, (res[0], res[1]))

            # ---- Phase 1: Detection ----------------------------------------
            centroids, boxes = detector.detect(frame)

            # ---- Phase 2A: Density -----------------------------------------
            density, labels, heatmap_bgr, los_level = mapper.compute(centroids, frame.shape)

            # ---- Phase 2B: Optical flow ------------------------------------
            flow_metrics, flow_bgr, _ = flow_analyser.compute(frame)
            flow_mag  = flow_metrics["flow_magnitude"]
            divergence = flow_metrics["divergence"]
            chaos     = flow_metrics["chaos"]

            # ---- Phase 3A: Risk engine --------------------------------------
            result = engine.update(
                density=density,
                flow_magnitude=flow_mag,
                divergence=divergence,
                chaos=chaos,
            )
            risk_score   = result["risk_score"]
            alert_level  = result["alert_level"]
            gate_command = result["gate_command"]
            trend_slope  = result["trend_slope"]
            ttc          = result["time_to_critical_s"]
            alert_msg    = result["alert_message"]

            # ---- Console summary -------------------------------------------
            print(
                f"[{frame_idx:05d}] "
                f"count={len(centroids):3d}  "
                f"density={density:.2f}  "
                f"R={risk_score:.3f}  "
                f"level={alert_level:8s}  "
                f"gate={gate_command:10s}  "
                f"slope={trend_slope:+.4f}  "
                f"ttc={f'{ttc:.1f}s' if ttc else 'N/A'}"
            )

            # Generate the fully annotated visualization frame (bounding boxes, heatmap, flow overlays, and HUD)
            vis = detector.draw_detections(frame, centroids, boxes)
            vis = mapper.overlay(vis, heatmap_bgr, labels, centroids, density, los_level)
            vis = flow_analyser.overlay(vis, flow_bgr, flow_metrics, alpha=0.25)
            vis = _annotate_hud(vis, len(centroids), density, los_level,
                                risk_score, alert_level, gate_command,
                                trend_slope, ttc, flow_mag, divergence, chaos)

            # ---- Phase 3B: MQTT publishing ----------------------------------
            if mqtt_pub.connected:
                mqtt_pub.publish_metrics(
                    count=len(centroids),
                    density=density,
                    risk_score=risk_score,
                    flow_magnitude=flow_mag,
                    divergence=divergence,
                    chaos=chaos,
                    alert_level=alert_level,
                )
                heatmap_b64 = encode_frame_base64(heatmap_bgr, quality=50)
                mqtt_pub.publish_heatmap(heatmap_b64)
                
                # Publish the fully annotated live camera feed
                camera_b64 = encode_frame_base64(vis, quality=55)
                mqtt_pub.publish_camera(camera_b64)
                
                mqtt_pub.publish_actuation(gate_command)
                mqtt_pub.publish_alert(alert_level, alert_msg, ttc)

            # ---- Display (optional) ----------------------------------------
            if show_display:
                cv2.imshow("Oracle - Crowd Safety Pipeline", vis)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("[INFO] Quit requested.")
                    break

            frame_idx += 1

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")

    finally:
        cap.release()
        if show_display:
            cv2.destroyAllWindows()
        mqtt_pub.disconnect()
        print("[INFO] Pipeline shut down cleanly.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Oracle crowd-safety pipeline")
    parser.add_argument("--config",   default="config.yaml",
                        help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--no-display", action="store_true",
                        help="Run headless (no OpenCV window)")
    args = parser.parse_args()

    run(config_path=args.config, show_display=not args.no_display)
