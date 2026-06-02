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
    lines = [
        f"People: {count}",
        f"Density: {density:.2f} p/m² [{level}]",
        f"Risk: {risk_score:.3f} [{alert_level}]",
        f"Gate: {gate_command}",
        f"Trend: {trend_slope:+.4f} R/s",
        f"TTC: {f'{ttc:.1f}s' if ttc is not None else 'N/A'}",
        f"Flow Speed: {flow_mag:.2f} px/f",
        f"Divergence: {divergence:+.4f}",
        f"Chaos: {chaos:.3f} rad",
    ]
    colours = {
        "SAFE":     (128, 222, 74),   # BGR green
        "WARNING":  (36, 191, 251),   # BGR amber
        "CRITICAL": (68, 68, 239),    # BGR red
    }
    colour = colours.get(alert_level, (255, 255, 255))

    # Draw semi-transparent dark slate-900 background box
    overlay_box = frame.copy()
    cv2.rectangle(overlay_box, (5, 5), (210, 180), (42, 23, 15), -1)
    cv2.addWeighted(overlay_box, 0.7, frame, 0.3, 0, frame)

    for i, line in enumerate(lines):
        cv2.putText(frame, line, (12, 22 + i * 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, colour, 1, cv2.LINE_AA)
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
