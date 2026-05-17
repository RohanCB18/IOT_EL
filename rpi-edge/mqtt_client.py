import json
import threading
import yaml
import paho.mqtt.client as mqtt
from utils import timestamp_ms


class MQTTPublisher:
    """
    Thin wrapper around paho-mqtt that publishes pipeline data to all four
    oracle topics defined in config.yaml.

    Topics published:
        oracle/node1/metrics    — JSON metrics dict (every frame)
        oracle/node1/heatmap    — Base64 JPEG string (every frame)
        oracle/node1/actuation  — JSON gate command (every frame)
        oracle/node1/alert      — JSON alert dict (every frame)
    """

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)["mqtt"]

        self.broker  = cfg["broker"]
        self.port    = cfg["port"]
        self.topics  = cfg["topics"]

        self._client = mqtt.Client(client_id="oracle-pipeline", protocol=mqtt.MQTTv311)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_publish    = self._on_publish

        self._connected = False
        self._lock      = threading.Lock()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self):
        """Connects to the broker and starts the background network loop."""
        print(f"[MQTT] Connecting to {self.broker}:{self.port} …")
        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()   # background thread

    def disconnect(self):
        """Gracefully stops the loop and disconnects."""
        self._client.loop_stop()
        self._client.disconnect()
        print("[MQTT] Disconnected.")

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Publishing helpers
    # ------------------------------------------------------------------

    def publish_metrics(self, count: int, density: float, risk_score: float,
                        flow_magnitude: float, divergence: float, chaos: float,
                        alert_level: str):
        """Publishes the per-frame metrics JSON."""
        payload = {
            "count":          count,
            "density":        round(density, 4),
            "risk_score":     round(risk_score, 4),
            "flow_mag":       round(flow_magnitude, 4),
            "divergence":     round(divergence, 6),
            "chaos":          round(chaos, 4),
            "alert_level":    alert_level,
            "timestamp":      timestamp_ms(),
        }
        self._publish(self.topics["metrics"], payload)

    def publish_heatmap(self, heatmap_b64: str):
        """Publishes the base64-encoded heatmap image."""
        self._client.publish(self.topics["heatmap"], heatmap_b64, qos=0)

    def publish_actuation(self, gate_command: str):
        """Publishes the gate command JSON."""
        payload = {
            "command":   gate_command,
            "timestamp": timestamp_ms(),
        }
        self._publish(self.topics["actuation"], payload)

    def publish_alert(self, level: str, message: str, time_to_critical):
        """Publishes the alert JSON."""
        payload = {
            "level":                    level,
            "message":                  message,
            "predicted_time_to_critical": time_to_critical,
            "timestamp":                timestamp_ms(),
        }
        self._publish(self.topics["alert"], payload)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, topic: str, payload: dict, qos: int = 0):
        if not self._connected:
            return
        with self._lock:
            self._client.publish(topic, json.dumps(payload), qos=qos)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            print(f"[MQTT] Connected to broker at {self.broker}:{self.port}")
        else:
            print(f"[MQTT] Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            print(f"[MQTT] Unexpected disconnection (rc={rc}). Will retry via loop.")

    def _on_publish(self, client, userdata, mid):
        pass   # suppress per-message noise; enable for debugging if needed


# ------------------------------------------------------------------
# Quick standalone test  (requires Mosquitto running on localhost)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import time

    pub = MQTTPublisher("config.yaml")
    pub.connect()
    time.sleep(1)   # allow connection to establish

    if pub.connected:
        pub.publish_metrics(5, 2.1, 0.42, 3.5, -0.1, 1.1, "WARNING")
        pub.publish_actuation("GATE_HALF")
        pub.publish_alert("WARNING", "Test alert from mqtt_client.py", 12.5)
        print("[MQTT] Test messages published. Check: mosquitto_sub -t 'oracle/#' -v")
        time.sleep(1)
    else:
        print("[MQTT] Not connected — is Mosquitto running on localhost:1883?")

    pub.disconnect()
