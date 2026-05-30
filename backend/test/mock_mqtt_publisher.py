import time
import json
import base64
import random
import math
import numpy as np
import cv2
import paho.mqtt.client as mqtt

# MQTT Setup
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_METRICS = "oracle_rohan_123/node1/metrics"
TOPIC_HEATMAP = "oracle_rohan_123/node1/heatmap"
TOPIC_ACTUATION = "oracle_rohan_123/node1/actuation"
TOPIC_ALERT = "oracle_rohan_123/node1/alert"
TOPIC_CAMERA = "oracle_rohan_123/node1/camera"

client = mqtt.Client(client_id="mock-publisher")

def main():
    print(f"[MOCK] Connecting to MQTT Broker at {BROKER}:{PORT}...")
    try:
        client.connect(BROKER, PORT, 60)
    except Exception as e:
        print(f"[ERROR] Could not connect: {e}. Is Mosquitto running on port 1883?")
        return

    client.loop_start()
    print("[MOCK] Publishing started. Press Ctrl+C to stop.")

    # Evolving states: we will simulate a full crowd flow cycle:
    # Safe -> Rising Density -> Warning (Half-Open Gate) -> Critical (Closed Gate) -> Safe Again
    t = 0
    while True:
        # Simulate cyclically changing crowd parameters using sine wave
        # Sine wave runs from -1 to 1, shifted to 0 to 1
        cycle = (math.sin(t * 0.15) + 1.0) / 2.0  # 0.0 to 1.0
        
        # 1. Metrics Calculation
        count = int(cycle * 15)  # 0 to 15 people
        density = cycle * 5.5    # 0.0 to 5.5 persons/m²
        flow_mag = 1.0 + cycle * 4.0 + random.uniform(-0.5, 0.5)  # 1.0 to 5.0
        divergence = 0.5 - cycle * 1.5 + random.uniform(-0.1, 0.1) # 0.5 to -1.0 (compression)
        chaos = cycle * 2.5 + random.uniform(-0.2, 0.2)  # 0.0 to 2.5 std of angles

        # Normalise inputs (similar to RiskEngine)
        rho_hat = max(0.0, min(1.0, (density - 0.0) / 6.0))
        v_hat = max(0.0, min(1.0, (flow_mag - 0.0) / 15.0))
        div_hat = max(0.0, min(1.0, (divergence - (-2.0)) / 4.0))
        compression_hat = max(0.0, min(1.0, 1.0 - div_hat))
        chaos_hat = max(0.0, min(1.0, (chaos - 0.0) / math.pi))

        # Composite Risk Score
        risk_score = 0.40 * rho_hat + 0.20 * v_hat + 0.25 * compression_hat + 0.15 * chaos_hat
        risk_score = max(0.0, min(1.0, risk_score))

        # Alert level + Gate command
        if risk_score >= 0.75:
            alert_level = "CRITICAL"
            gate_command = "GATE_CLOSE"
            alert_msg = "CRITICAL crowd density. Gate closed immediately."
        elif risk_score >= 0.55:
            alert_level = "WARNING"
            gate_command = "GATE_HALF"
            alert_msg = f"WARNING: Rising crowd risk. Gate half-open. Critical in {max(1.0, 30.0 - t % 30):.1f}s."
        else:
            alert_level = "SAFE"
            gate_command = "GATE_OPEN"
            alert_msg = "Crowd density within safe limits. Gate open."

        timestamp = int(time.time() * 1000)

        # 2. Publish Metrics
        metrics_payload = {
            "count": count,
            "density": round(density, 4),
            "risk_score": round(risk_score, 4),
            "flow_mag": round(flow_mag, 4),
            "divergence": round(divergence, 6),
            "chaos": round(chaos, 4),
            "alert_level": alert_level,
            "timestamp": timestamp
        }
        client.publish(TOPIC_METRICS, json.dumps(metrics_payload))

        # 3. Publish Actuation & Alert
        actuation_payload = {
            "command": gate_command,
            "timestamp": timestamp
        }
        client.publish(TOPIC_ACTUATION, json.dumps(actuation_payload))

        alert_payload = {
            "level": alert_level,
            "message": alert_msg,
            "predicted_time_to_critical": round(30.0 - t % 30, 1) if alert_level == "WARNING" else None,
            "timestamp": timestamp
        }
        client.publish(TOPIC_ALERT, json.dumps(alert_payload))

        # 4. Generate & Publish Mock Heatmap & Camera Frames
        # Create a dark frame for mock camera feed (320x240)
        cam_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Background grid to make it look technical
        for y in range(0, 240, 20):
            cv2.line(cam_frame, (0, y), (320, y), (15, 23, 42), 1)
        for x in range(0, 320, 20):
            cv2.line(cam_frame, (x, 0), (x, 240), (15, 23, 42), 1)

        # Create a canvas for mock heatmap
        heatmap_canvas = np.zeros((240, 320), dtype=np.float32)

        # Simulate people walking
        num_sim_people = max(1, count)
        for i in range(num_sim_people):
            # Angular offset based on time + person index
            angle = t * 0.08 + i * (2 * math.pi / num_sim_people)
            radius = 50 + 25 * math.sin(t * 0.03 + i)
            cx = int(160 + radius * 1.2 * math.cos(angle))
            cy = int(120 + radius * math.sin(angle))

            # Bounding box width/height
            bw, bh = 22, 38
            x1, y1 = cx - bw//2, cy - bh//2
            x2, y2 = cx + bw//2, cy + bh//2

            # Draw bounding box + red centroid on camera frame
            cv2.rectangle(cam_frame, (x1, y1), (x2, y2), (99, 102, 241), 1)
            cv2.circle(cam_frame, (cx, cy), 3, (239, 68, 68), -1)
            
            # Label
            cv2.putText(cam_frame, f"p{i}", (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (99, 102, 241), 1)

            # Draw Gaussian-like splat on heatmap
            cv2.circle(heatmap_canvas, (cx, cy), 20, 1.0, -1)

        # Blur the heatmap to make it smooth
        heatmap_blurred = cv2.GaussianBlur(heatmap_canvas, (31, 31), 15)
        # Normalise to 0-255
        if heatmap_blurred.max() > 0:
            heatmap_blurred = (heatmap_blurred / heatmap_blurred.max() * 255).astype(np.uint8)
        else:
            heatmap_blurred = heatmap_blurred.astype(np.uint8)
        
        # Apply JET colormap
        heatmap_bgr = cv2.applyColorMap(heatmap_blurred, cv2.COLORMAP_JET)

        # HUD annotations on camera frame
        hud_color = (34, 197, 94) if alert_level == "SAFE" else ((245, 158, 11) if alert_level == "WARNING" else (239, 68, 68))
        cv2.putText(cam_frame, f"LIVE MOCK FEED - Count: {count}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        cv2.putText(cam_frame, f"Risk: {risk_score:.3f} [{alert_level}]", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.35, hud_color, 1)
        cv2.putText(cam_frame, f"Gate: {gate_command}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.35, hud_color, 1)

        # Encode & publish frames
        _, cam_buf = cv2.imencode(".jpg", cam_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        cam_b64 = base64.b64encode(cam_buf).decode("utf-8")
        client.publish(TOPIC_CAMERA, cam_b64)

        _, heat_buf = cv2.imencode(".jpg", heatmap_bgr, [cv2.IMWRITE_JPEG_QUALITY, 60])
        heat_b64 = base64.b64encode(heat_buf).decode("utf-8")
        client.publish(TOPIC_HEATMAP, heat_b64)

        print(f"[MOCK] t={t:03d} | Risk={risk_score:.3f} | Lvl={alert_level:8s} | Count={count:2d} | Actuation={gate_command}")

        t += 1
        time.sleep(0.5)  # 2 Hz simulation speed

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[MOCK] Stopping publisher...")
        client.disconnect()
