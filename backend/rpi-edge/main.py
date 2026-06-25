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
# pyrefly: ignore [missing-import]
import cv2
import yaml
import numpy as np

from detector     import PersonDetector
from density      import DensityMapper
from optical_flow import OpticalFlowAnalyser
from risk_engine  import RiskEngine
from mqtt_client  import MQTTPublisher
from utils        import encode_frame_base64


def _draw_text_with_shadow(frame, text, org, font_face, font_scale, color, thickness=1):
    """Draws text with a thick black drop shadow for absolute readability on any background."""
    # Draw drop shadow (black, slightly thicker)
    cv2.putText(frame, text, (org[0] + 1, org[1] + 1), font_face, font_scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
    # Draw foreground text
    cv2.putText(frame, text, org, font_face, font_scale, color, thickness, cv2.LINE_AA)


def _create_dashboard_canvas(portrait_frame, target_w=960, target_h=540):
    """Pillars the video frame into a clean, uniform landscape canvas to avoid stretching distortion."""
    ph, pw = portrait_frame.shape[:2]
    
    # Scale to fit target height while preserving aspect ratio
    scale = target_h / ph
    nw = int(pw * scale)
    nh = target_h
    
    resized = cv2.resize(portrait_frame, (nw, nh), interpolation=cv2.INTER_AREA)
    
    # Create black canvas
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    
    # Center the resized frame
    dx = (target_w - nw) // 2
    canvas[0:target_h, dx:dx+nw] = resized
    
    return canvas, dx, nw


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


def _annotate_hud(canvas, count: int, density: float, level: str,
                  risk_score: float, alert_level: str, gate_command: str,
                  trend_slope: float, ttc, flow_mag: float, divergence: float, chaos: float,
                  dx: int):
    """Draws a clean sidebar HUD card in the left pillarbox margin of the canvas."""
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
        ("Smooth Risk:", f"{risk_score:.3f}", theme_colour),
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

    # Draw dark panel card in the left margin area
    # Leave 15px margin around the card: x1=15, y1=15, x2=310, y2=525 (height=540)
    x1, y1 = 15, 15
    x2, y2 = 310, 525
    
    overlay = canvas.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (25, 20, 16), -1)  # Deep slate panel background
    cv2.addWeighted(overlay, 0.90, canvas, 0.10, 0, canvas)
    
    # Draw themed border around the HUD card
    cv2.rectangle(canvas, (x1, y1), (x2, y2), theme_colour, 1, cv2.LINE_AA)

    y_offset = y1 + 30
    line_spacing = 30  # Larger vertical spacing since we have 510px height
    
    for label, value, val_color in hud_data:
        if label is None:
            # Draw section header
            _draw_text_with_shadow(canvas, value, (x1 + 18, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, val_color, thickness=1)
            y_offset += line_spacing
        else:
            # Draw metric label in muted gray
            _draw_text_with_shadow(canvas, label, (x1 + 18, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), thickness=1)
            # Draw value aligned to the right (x = 155)
            _draw_text_with_shadow(canvas, value, (x1 + 155, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, val_color, thickness=1)
            y_offset += line_spacing
            
    return canvas


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _run_profile(config_path: str, profile: str, show_display: bool) -> str:
    cfg    = _load_config(config_path)
    if "profiles" in cfg:
        p = profile if profile in cfg["profiles"] else "0"
        profile_cfg = cfg["profiles"][p]
    else:
        profile_cfg = cfg
    source = profile_cfg["camera"]["source"]

    # ---- Instantiate pipeline components -----------------------------------
    detector = PersonDetector(config_path, profile=profile)
    print(f"[INFO] ✓ Detector: {detector.backend_name}  |  Device: {detector.device.upper()}")
    mapper   = DensityMapper(config_path, profile=profile)
    flow_analyser = OpticalFlowAnalyser()
    engine   = RiskEngine(config_path, profile=profile)
    mqtt_pub = MQTTPublisher(config_path, profile=profile)

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

    frame_idx    = 0
    mqtt_tick    = 0   # counts up; publish MQTT every N frames
    MQTT_EVERY   = 5   # publish MQTT / encode frames every 5 frames (~6 Hz at 30 FPS)
    PRINT_EVERY  = 15  # console summary every N frames (reduces stdout stall)

    # ---- FPS tracking (rolling window of last 30 frame durations) -----------
    from collections import deque
    _frame_times: deque = deque(maxlen=30)
    _t_last = time.perf_counter()
    fps_display = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] End of stream or read error.")
                break

            # ---- FPS: measure time since last frame -------------------------
            _t_now = time.perf_counter()
            _frame_times.append(_t_now - _t_last)
            _t_last = _t_now
            if len(_frame_times) >= 2:
                fps_display = len(_frame_times) / sum(_frame_times)

            # Resize frame to configured resolution for high performance and proper window sizing
            res = profile_cfg["camera"].get("resolution")
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
            raw_risk     = result["risk_score"]
            risk_score   = result["smoothed_risk"] # Use smoothed for GUI and logic
            alert_level  = result["alert_level"]
            gate_command = result["gate_command"]
            trend_slope  = result["trend_slope"]
            ttc          = result["time_to_critical_s"]
            alert_msg    = result["alert_message"]

            # ---- Console summary (throttled to avoid stdout stall) ----------
            if frame_idx % PRINT_EVERY == 0:
                print(
                    f"[{frame_idx:05d}] "
                    f"count={len(centroids):3d}  "
                    f"density={density:.2f}  "
                    f"R(raw)={raw_risk:.3f}  "
                    f"R(sm)={risk_score:.3f}  "
                    f"level={alert_level:8s}  "
                    f"gate={gate_command:10s}  "
                    f"slope={trend_slope:+.4f}  "
                    f"ttc={f'{ttc:.1f}s' if ttc else 'N/A'}"
                )

            # Generate the fully annotated visualization frame (bounding boxes, heatmap, flow overlays)
            vis = detector.draw_detections(frame, centroids, boxes)
            vis = mapper.overlay(vis, heatmap_bgr, labels, centroids, density, los_level)
            vis = flow_analyser.overlay(vis, flow_bgr, flow_metrics, alpha=0.25)
            
            # Center the portrait frame into a landscape 960x540 canvas to lock aspect ratio
            canvas, dx, nw = _create_dashboard_canvas(vis, target_w=960, target_h=540)
            
            # Draw side HUD metrics on the landscape canvas (in the black margin)
            canvas = _annotate_hud(canvas, len(centroids), density, los_level,
                                   risk_score, alert_level, gate_command,
                                   trend_slope, ttc, flow_mag, divergence, chaos,
                                   dx)

            # ---- FPS badge — top-right corner of canvas --------------------
            fps_text  = f"FPS: {fps_display:5.1f}"
            fps_color = (
                (74, 222, 128)  if fps_display >= 20 else   # green  — smooth
                (36, 191, 251)  if fps_display >= 10 else   # amber  — ok
                (68,  68, 239)                              # red    — lagging
            )
            (tw, th), _ = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            badge_x = canvas.shape[1] - tw - 18
            badge_y = 38
            # Semi-transparent dark pill behind the text
            _ov = canvas.copy()
            cv2.rectangle(_ov, (badge_x - 8, badge_y - th - 6),
                          (badge_x + tw + 6, badge_y + 4), (20, 20, 20), -1)
            cv2.addWeighted(_ov, 0.75, canvas, 0.25, 0, canvas)
            _draw_text_with_shadow(canvas, fps_text, (badge_x, badge_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.55, fps_color, thickness=1)

            # ---- Phase 3B: MQTT publishing (every MQTT_EVERY frames) --------
            mqtt_tick += 1
            if mqtt_pub.connected and mqtt_tick % MQTT_EVERY == 0:
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

                # Publish the annotated camera feed (most expensive encode — throttled)
                camera_b64 = encode_frame_base64(canvas, quality=50)
                mqtt_pub.publish_camera(camera_b64)

                mqtt_pub.publish_actuation(gate_command)
                mqtt_pub.publish_alert(alert_level, alert_msg, ttc)

            # ---- Display (optional) ----------------------------------------
            if show_display:
                cv2.imshow("Oracle - Crowd Safety Pipeline", canvas)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("[INFO] Quit requested.")
                    return "QUIT"
                elif key in [ord('0'), ord('1'), ord('2'), ord('3')]:
                    return chr(key)

            frame_idx += 1

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
        return "QUIT"

    finally:
        cap.release()
        if show_display:
            cv2.destroyAllWindows()
        mqtt_pub.disconnect()
        print("[INFO] Pipeline shut down cleanly.")


def run(config_path: str = "config.yaml", show_display: bool = True):
    current_profile = "0"
    while True:
        print(f"\n[INFO] Starting profile: {current_profile}")
        next_action = _run_profile(config_path, current_profile, show_display)
        if next_action == "QUIT" or next_action is None:
            break
        current_profile = next_action


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Oracle crowd-safety pipeline")
    parser.add_argument("--config",   default="config.yaml",
                        help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--no-display", action="store_true",
                        help="Run headless (no OpenCV window)")
    args = parser.parse_args()

    run(config_path=args.config, show_display=not args.no_display)
