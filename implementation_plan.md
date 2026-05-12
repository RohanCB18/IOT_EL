# 🏟️ Intelligent Crowd Flow & Density Safety Oracle — Implementation Plan (v5)

> **Strategy:** Complete ALL software on your laptop first. Then integrate hardware step-by-step in the lab.

---

## Architecture Recap

| Device | Role |
|---|---|
| **USB Webcam → RPi 4** | Video capture → YOLOv8-tiny (NCNN/ONNX, 320×320) → DBSCAN → optical flow → risk engine → MQTT |
| **ESP32 DevKit** | Subscribes to MQTT → drives servo + LEDs + buzzer |
| **Laptop** | React dashboard subscribes to RPi's MQTT via WebSocket |

---

# PART A: SOFTWARE DEVELOPMENT (On Your Laptop)

> [!TIP]
> Everything in Part A runs on your **laptop** using your laptop's webcam or a downloaded crowd test video. No RPi, no ESP32, no breadboard needed yet.

---

## Phase 0: Environment Setup *(Day 1)*

| # | Task | Details |
|---|---|---|
| 0.1 | Install Python 3.9+ | `python -m venv venv && venv\Scripts\activate` |
| 0.2 | Install Python deps | `pip install ultralytics opencv-python scikit-learn numpy scipy paho-mqtt pyyaml` |
| 0.3 | Install Mosquitto MQTT broker | Windows installer from [mosquitto.org](https://mosquitto.org/download/) |
| 0.4 | Configure Mosquitto | See config below |
| 0.5 | Install Node.js 18+ | For React dashboard |
| 0.6 | Install Arduino IDE | For writing ESP32 firmware (writing only, no flashing yet) |
| 0.7 | Scaffold folder structure | See below |
| 0.8 | Git init | `.gitignore` → `node_modules/`, `venv/`, `models/*.pt`, `__pycache__/` |

**Mosquitto config** (`mosquitto.conf`):
```
listener 1883
allow_anonymous true
listener 9001
protocol websockets
```

**Folder structure:**
```
IOT_EL/
├── esp32-actuator/              # ESP32 firmware (write now, flash later)
│   ├── src/main.cpp
│   └── platformio.ini
├── rpi-edge/                    # Python pipeline (develop on laptop, deploy to RPi later)
│   ├── config.yaml
│   ├── main.py
│   ├── detector.py
│   ├── density.py
│   ├── optical_flow.py
│   ├── risk_engine.py
│   ├── mqtt_client.py
│   ├── utils.py
│   ├── models/
│   └── requirements.txt
├── dashboard/                   # React dashboard
├── test/
│   ├── mock_mqtt_publisher.py
│   └── test_videos/
└── README.md
```

**Checkpoint:** Python venv active, Mosquitto running on localhost, `mosquitto_pub` / `mosquitto_sub` works between two terminals.

---

## Phase 1: Person Detection — YOLOv8-tiny *(Days 2–5)*

> Using your **laptop webcam** or a crowd test video as input.

| # | Task | Details |
|---|---|---|
| 1.1 | Download YOLOv8n weights | `from ultralytics import YOLO; model = YOLO('yolov8n.pt')` |
| 1.2 | Export to NCNN format | `model.export(format='ncnn')` — same format used on RPi later |
| 1.3 | Write `config.yaml` | Source, thresholds, weights, MQTT topics |
| 1.4 | Write `detector.py` | Filter class `person` (0), confidence ≥ 0.45, imgsz=320 |
| 1.5 | Test with laptop webcam | `cv2.VideoCapture(0)` — stand in front of your laptop |
| 1.6 | Test with crowd video | Download a crowd walking video, use `cv2.VideoCapture("test_videos/crowd.mp4")` |
| 1.7 | Overlay bounding boxes + centroids | `cv2.rectangle()` + `cv2.circle()` |

**`config.yaml`:**
```yaml
camera:
  source: 0                    # 0 = webcam, or "test_videos/crowd.mp4"
  resolution: [320, 240]

detection:
  model_path: "models/yolov8n_ncnn_model"
  confidence: 0.45
  imgsz: 320

density:
  eps: 50
  min_samples: 3
  pixels_per_meter: 100
  sigma: 30

risk:
  weights: [0.40, 0.20, 0.25, 0.15]   # density, speed, compression, chaos
  warning_threshold: 0.55
  critical_threshold: 0.75
  window_size: 10

mqtt:
  broker: "localhost"                    # Change to RPi IP during hardware integration
  port: 1883
  topics:
    metrics: "oracle/node1/metrics"
    heatmap: "oracle/node1/heatmap"
    actuation: "oracle/node1/actuation"
    alert: "oracle/node1/alert"
```

**Checkpoint:** Running `detector.py` on your laptop shows bounding boxes + centroids on webcam feed or crowd video.

---

## Phase 2: Density Mapping + Optical Flow *(Days 6–10)*

#### 2A — DBSCAN Density Mapping

| # | Task | Details |
|---|---|---|
| 2A.1 | Write `density.py` | Centroids → DBSCAN clusters → Gaussian heatmap |
| 2A.2 | DBSCAN clustering | `eps=50, min_samples=3` |
| 2A.3 | Gaussian heatmap | `scipy.ndimage.gaussian_filter(sigma=30)` |
| 2A.4 | Density classification (Fruin LoS) | Safe <2.0, Caution 2.0–3.5, Warning 3.5–5.0, Critical ≥5.0 persons/m² |
| 2A.5 | Overlay heatmap on frame | `cv2.addWeighted()` with colormap |

#### 2B — Farneback Optical Flow

| # | Task | Details |
|---|---|---|
| 2B.1 | Write `optical_flow.py` | Dense flow between consecutive frames |
| 2B.2 | Mean flow magnitude `\|v̄\|` | `np.mean(np.sqrt(fx² + fy²))` |
| 2B.3 | Flow divergence `∇·v` | `np.gradient(fx, axis=1) + np.gradient(fy, axis=0)` |
| 2B.4 | Flow uniformity `σθ` | `np.std(np.arctan2(fy, fx))` |
| 2B.5 | HSV flow overlay | Color-coded visualization on frame |

**Checkpoint:** Laptop shows density heatmap + flow arrows over webcam feed. Console prints density (persons/m²), speed, divergence, chaos values.

---

## Phase 3: Risk Engine + MQTT *(Days 11–15)*

#### 3A — Composite Risk Scoring

| # | Task | Details |
|---|---|---|
| 3A.1 | Write `risk_engine.py` | `R = 0.40·ρ̂ + 0.20·|v̂| + 0.25·(1−∇·v̂) + 0.15·σ̂θ` |
| 3A.2 | Normalize inputs to [0, 1] | Min-max with empirical bounds |
| 3A.3 | Sliding window (10 readings) | `collections.deque(maxlen=10)` |
| 3A.4 | Linear regression on window | `np.polyfit()` → slope = trend |
| 3A.5 | Extrapolate time-to-critical | `time = (0.75 - R) / slope` if slope > 0 |
| 3A.6 | Alert levels | R > 0.75 → Critical, R > 0.55 → Warning |
| 3A.7 | Gate commands | Safe→`GATE_OPEN`, Warning→`GATE_HALF`, Critical→`GATE_CLOSE` |

#### 3B — MQTT Publishing

| # | Task | Details |
|---|---|---|
| 3B.1 | Write `mqtt_client.py` | Publishes JSON to local Mosquitto on localhost |
| 3B.2 | Publish every frame | Metrics + heatmap + actuation + alert topics |

#### 3C — Main Pipeline Orchestrator

| # | Task | Details |
|---|---|---|
| 3C.1 | Write `main.py` | Ties everything: webcam → detector → density → flow → risk → MQTT |
| 3C.2 | Test full loop on laptop | Run `main.py`, open another terminal: `mosquitto_sub -t "oracle/#"` |

**MQTT Topics (all published by pipeline):**

| Topic | Payload |
|---|---|
| `oracle/node1/metrics` | `{count, density, risk_score, flow_mag, divergence, chaos, alert_level, timestamp}` |
| `oracle/node1/heatmap` | Base64-encoded heatmap image |
| `oracle/node1/actuation` | `{command: "GATE_OPEN" / "GATE_HALF" / "GATE_CLOSE"}` |
| `oracle/node1/alert` | `{level, message, predicted_time_to_critical, timestamp}` |

**Checkpoint:** Running `main.py` on laptop → `mosquitto_sub -t "oracle/#"` shows live JSON streaming with correct risk scores.

---

## Phase 4: React Dashboard *(Days 16–22)*

| # | Task | Details |
|---|---|---|
| 4.1 | Scaffold Vite + React | `npx -y create-vite@latest ./ --template react` in `dashboard/` |
| 4.2 | Install deps | `npm install mqtt recharts react-gauge-chart` |
| 4.3 | `useMqtt.js` hook | Connect to `ws://localhost:9001` (laptop Mosquitto for now) |
| 4.4 | `RiskGauge.jsx` | Semicircular gauge R ∈ [0,1] with Safe/Warning/Critical color zones |
| 4.5 | `DensityHeatmap.jsx` | Renders base64 heatmap overlay |
| 4.6 | `FlowVectorOverlay.jsx` | Flow direction arrows |
| 4.7 | `AlertLog.jsx` | Timestamped scrolling alert list with severity colors |
| 4.8 | `CameraFeed.jsx` | Displays annotated frame from pipeline |
| 4.9 | `GateStatus.jsx` | Shows gate state (Open/Half/Closed) + LED indicators |
| 4.10 | Risk trend line chart | R over last 60 seconds using `recharts` |
| 4.11 | Dark theme + polish | Premium dark UI, glassmorphism, micro-animations |

**Testing without hardware:** Run `main.py` (pipeline) and `npm run dev` (dashboard) simultaneously on your laptop. Dashboard subscribes to `ws://localhost:9001` and shows live data.

**Checkpoint:** Dashboard shows live gauge, heatmap, alerts, gate status — all fed from the pipeline running on the same laptop.

---

## Phase 5: ESP32 Firmware (Write Code Only) *(Days 23–24)*

> [!IMPORTANT]
> You're only **writing** the firmware code here. Flashing and wiring happens in Part B (lab).

| # | Task | Details |
|---|---|---|
| 5.1 | Create `esp32-actuator/src/main.cpp` | Full firmware code |
| 5.2 | Wi-Fi + MQTT connection logic | `WiFi.begin()` + `PubSubClient` setup |
| 5.3 | MQTT callback handler | Parse JSON from `oracle/node1/actuation` |
| 5.4 | Gate state logic | `GATE_OPEN`→servo 0°+green, `GATE_HALF`→90°+amber, `GATE_CLOSE`→180°+red+buzzer |
| 5.5 | Create `platformio.ini` | Board config, library deps |

**Checkpoint:** Firmware code compiles in Arduino IDE / PlatformIO (no upload yet).

---

## 🧪 Software Testing Checklist (Before Going to Lab)

Before you touch any hardware, verify ALL of these pass on your laptop:

| # | Test | How |
|---|---|---|
| ✅ 1 | YOLOv8 detects people | Run `detector.py` with webcam or video |
| ✅ 2 | Density heatmap renders | Run pipeline, check OpenCV window |
| ✅ 3 | Optical flow computes | Check console for magnitude/divergence/chaos values |
| ✅ 4 | Risk score changes with crowd size | More people → higher R |
| ✅ 5 | MQTT publishes correctly | `mosquitto_sub -t "oracle/#"` shows JSON |
| ✅ 6 | Dashboard receives live data | Open dashboard, verify gauge/heatmap/alerts update |
| ✅ 7 | Gate command changes with risk | Watch `oracle/node1/actuation` topic change from OPEN→HALF→CLOSE |
| ✅ 8 | ESP32 firmware compiles | Arduino IDE → Verify (compile) passes |

---

# PART B: HARDWARE INTEGRATION (In the Lab)

> [!IMPORTANT]
> Only proceed here after **all 8 software tests above pass**. You should walk into the lab with all code ready — just deploy, wire, and test.

---

## Step 1: Set Up Raspberry Pi *(30 min)*

| # | Do This | Details |
|---|---|---|
| 1.1 | Flash RPi SD card | Raspberry Pi OS 64-bit (Bookworm), enable SSH + Wi-Fi during flash |
| 1.2 | Boot RPi and SSH in | `ssh pi@<RPi_IP>` |
| 1.3 | Update system | `sudo apt update && sudo apt upgrade -y` |
| 1.4 | Install Python 3 + venv | `sudo apt install python3-venv python3-pip -y` |
| 1.5 | Install OpenCV | `sudo apt install python3-opencv -y` |
| 1.6 | Install Mosquitto | `sudo apt install mosquitto mosquitto-clients -y` |
| 1.7 | Configure Mosquitto | Copy the same `mosquitto.conf` (ports 1883 + 9001 WebSocket) |
| 1.8 | Start Mosquitto | `sudo systemctl enable mosquitto && sudo systemctl start mosquitto` |
| 1.9 | Create project directory | `mkdir ~/oracle && cd ~/oracle` |
| 1.10 | Create Python venv | `python3 -m venv venv && source venv/bin/activate` |
| 1.11 | Install Python deps | `pip install ultralytics opencv-python scikit-learn numpy scipy paho-mqtt pyyaml` |

---

## Step 2: Deploy Pipeline Code to RPi *(15 min)*

| # | Do This | Details |
|---|---|---|
| 2.1 | Copy `rpi-edge/` folder to RPi | `scp -r rpi-edge/ pi@<RPi_IP>:~/oracle/` |
| 2.2 | Copy NCNN model to RPi | `scp -r rpi-edge/models/ pi@<RPi_IP>:~/oracle/models/` |
| 2.3 | Update `config.yaml` on RPi | Change `broker` from `localhost` to `0.0.0.0` (so external devices can connect) |
| 2.4 | Verify Python imports | `python3 -c "import ultralytics, cv2, sklearn, paho.mqtt; print('OK')"` |

---

## Step 3: Connect USB Webcam to RPi *(5 min)*

| # | Do This | Details |
|---|---|---|
| 3.1 | Plug USB webcam into RPi USB port | Any USB webcam works |
| 3.2 | Verify detection | `ls /dev/video*` → should show `/dev/video0` |
| 3.3 | Test with OpenCV | `python3 -c "import cv2; print(cv2.VideoCapture(0).isOpened())"` → `True` |
| 3.4 | Set config source | In `config.yaml`: `source: 0` |

---

## Step 4: Test Pipeline on RPi *(15 min)*

| # | Do This | Details |
|---|---|---|
| 4.1 | Run `main.py` on RPi | `cd ~/oracle && python3 main.py` |
| 4.2 | Check inference speed | Should see 200–500ms per frame on RPi CPU |
| 4.3 | Verify MQTT from laptop | On laptop: `mosquitto_sub -h <RPi_IP> -t "oracle/#"` → should see JSON |
| 4.4 | Point dashboard to RPi | In `useMqtt.js`: change `ws://localhost:9001` → `ws://<RPi_IP>:9001` |
| 4.5 | Run dashboard on laptop | `npm run dev` → verify live data from RPi appears |

---

## Step 5: Wire ESP32 Actuator Circuit *(20 min)*

> [!WARNING]
> Double-check all connections before powering on. Wrong wiring can damage components.

**What you need:** ESP32 DevKit, breadboard, SG90 servo, 3 LEDs (green/amber/red), active buzzer, 3× 220Ω resistors, jumper wires.

**Wiring steps (one by one):**

| # | Connect This | To This |
|---|---|---|
| 5.1 | ESP32 → Breadboard | Place ESP32 on breadboard |
| 5.2 | ESP32 **GPIO 13** | → Servo **signal wire** (orange/yellow) |
| 5.3 | ESP32 **5V** | → Servo **VCC wire** (red) |
| 5.4 | ESP32 **GND** | → Servo **GND wire** (brown) |
| 5.5 | ESP32 **GPIO 25** | → **220Ω resistor** → **Green LED anode (+)** |
| 5.6 | Green LED **cathode (−)** | → **GND rail** on breadboard |
| 5.7 | ESP32 **GPIO 26** | → **220Ω resistor** → **Amber LED anode (+)** |
| 5.8 | Amber LED **cathode (−)** | → **GND rail** |
| 5.9 | ESP32 **GPIO 27** | → **220Ω resistor** → **Red LED anode (+)** |
| 5.10 | Red LED **cathode (−)** | → **GND rail** |
| 5.11 | ESP32 **GPIO 14** | → **Buzzer positive (+)** |
| 5.12 | Buzzer **negative (−)** | → **GND rail** |
| 5.13 | ESP32 **GND** | → **GND rail** on breadboard (common ground) |

**Visual check:** 4 wires from GPIO pins (13, 25, 26, 27, 14), servo plugged in, all grounds connected.

---

## Step 6: Flash ESP32 Firmware *(10 min)*

| # | Do This | Details |
|---|---|---|
| 6.1 | Connect ESP32 to laptop via USB | It should appear as a COM port |
| 6.2 | Open `esp32-actuator/src/main.cpp` in Arduino IDE | — |
| 6.3 | Update Wi-Fi credentials | Set your lab Wi-Fi `ssid` and `password` in the code |
| 6.4 | Update MQTT broker IP | Set to `<RPi_IP>` (the Raspberry Pi's IP address) |
| 6.5 | Select board: "ESP32 Dev Module" | Tools → Board → ESP32 Dev Module |
| 6.6 | Select correct COM port | Tools → Port → COMx |
| 6.7 | Upload firmware | Click Upload (→) button |
| 6.8 | Open Serial Monitor | 115200 baud — should see "Connected to WiFi" and "Connected to MQTT" |

---

## Step 7: Test ESP32 Actuator Independently *(10 min)*

| # | Do This | Expected Result |
|---|---|---|
| 7.1 | From laptop, publish GATE_OPEN | `mosquitto_pub -h <RPi_IP> -t "oracle/node1/actuation" -m '{"command":"GATE_OPEN"}'` → **Servo 0°, Green LED ON** |
| 7.2 | Publish GATE_HALF | Same command with `GATE_HALF` → **Servo 90°, Amber LED ON** |
| 7.3 | Publish GATE_CLOSE | Same with `GATE_CLOSE` → **Servo 180°, Red LED ON, Buzzer ON** |
| 7.4 | Publish GATE_OPEN again | → **Servo back to 0°, Green LED, Buzzer OFF** |

> If any step fails: check Serial Monitor for errors, verify Wi-Fi connection, verify MQTT broker IP.

---

## Step 8: Full End-to-End Integration *(30 min)*

Now connect everything:

```
USB Webcam ──→ Raspberry Pi 4 ──MQTT──→ ESP32 (servo + LEDs + buzzer)
                    │
                    └──MQTT──→ Laptop (React Dashboard)
```

| # | Do This | Verify |
|---|---|---|
| 8.1 | Ensure all 3 devices on same Wi-Fi | RPi, ESP32, Laptop — same network |
| 8.2 | Start Mosquitto on RPi | `sudo systemctl start mosquitto` |
| 8.3 | Start pipeline on RPi | `python3 main.py` |
| 8.4 | Start dashboard on laptop | `npm run dev` → open in browser |
| 8.5 | Check dashboard receives data | Gauge, heatmap, alerts should update live |
| 8.6 | Walk people in front of webcam | Density increases → risk score rises |
| 8.7 | Verify gate actuates | As risk crosses Warning (0.55) → servo moves to 90°, amber LED |
| 8.8 | Increase crowd density | Risk crosses Critical (0.75) → servo moves to 180°, red LED, buzzer |
| 8.9 | People walk away | Risk drops → servo returns to 0°, green LED |
| 8.10 | Measure latency | Time from person appearing → servo moving. Target: < 500ms |

---

## Step 9: Calibration & Fine-Tuning *(20 min)*

| # | Adjust | How |
|---|---|---|
| 9.1 | `pixels_per_meter` in `config.yaml` | Measure real distance in camera FOV, calculate ratio |
| 9.2 | DBSCAN `eps` | If clusters are too big/small, adjust epsilon |
| 9.3 | Risk weights `[0.40, 0.20, 0.25, 0.15]` | Increase density weight if density should dominate |
| 9.4 | Confidence threshold | Lower to 0.35 if people are being missed, raise to 0.50 if false positives |

---

## Step 10: Record Demo & Document *(20 min)*

| # | Do This |
|---|---|
| 10.1 | Record screen capture of dashboard while people walk in front of camera |
| 10.2 | Record video of ESP32 actuator responding (servo moving, LEDs changing, buzzer sounding) |
| 10.3 | Take screenshots of: dashboard, terminal output, circuit |
| 10.4 | Write `README.md` with setup instructions + architecture diagram |

---

## 📊 Timeline Summary

| Phase | What | Days | Where |
|---|---|---|---|
| **PART A** | | | |
| Phase 0 | Environment setup | Day 1 | Laptop |
| Phase 1 | YOLOv8-tiny detection | Days 2–5 | Laptop |
| Phase 2 | Density + optical flow | Days 6–10 | Laptop |
| Phase 3 | Risk engine + MQTT + main.py | Days 11–15 | Laptop |
| Phase 4 | React dashboard | Days 16–22 | Laptop |
| Phase 5 | ESP32 firmware (code only) | Days 23–24 | Laptop |
| **PART B** | | | |
| Steps 1–3 | RPi setup + webcam | 50 min | Lab |
| Steps 4–6 | Deploy pipeline + flash ESP32 | 40 min | Lab |
| Steps 7–8 | Test + full integration | 40 min | Lab |
| Steps 9–10 | Calibrate + record demo | 40 min | Lab |
| | **Total lab time** | **~3 hours** | |
