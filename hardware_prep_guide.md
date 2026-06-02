# 🏟️ Intelligent Crowd Flow & Density Safety Oracle — Deployment & Presentation Guide

This guide is designed to prepare you and your team for the laboratory phase and final presentation. It provides two completely independent, step-by-step methods to deploy and demonstrate the project:

*   **METHOD A (Primary):** Full IoT Deployment using **Raspberry Pi + USB Webcam + ESP32 Actuator**.
*   **METHOD B (Alternative):** Streamlined Fallback Deployment using **Laptop (Built-in Webcam/Video) + ESP32 Actuator**.

---

## 🛠️ Section 1: Complete Hardware Components List

Ensure you have gathered the following components before heading to the lab:

### **Common Actuator Components (The "Gate" Node - Needed for Both Methods)**
- [ ] **ESP32 DevKit v1** (or any standard NodeMCU ESP32 board).
- [ ] **SG90 Micro Servo Motor** (Used to physically rotate the "gate").
- [ ] **Active Buzzer** (3.3V or 5V; sounds automatically when supplied with voltage).
- [ ] **LEDs (3 pieces):** 1× Green (Safe), 1× Amber (Warning), 1× Red (Critical).
- [ ] **Resistors:** 3× $220\Omega$ resistors (To protect the LEDs from burning out).
- [ ] **Solderless Breadboard** & Jumper Wires (~10× M-M, ~5× M-F).
- [ ] **Physical Gate Cardboard:** A small piece of cardboard/stick taped to the servo horn to visually show the gate rotating.

### **Method A Specific Components (Raspberry Pi Setup)**
- [ ] **Raspberry Pi 4 Model B** (with official 5V 3A USB-C Power Supply).
- [ ] **USB Webcam** (Standard 720p/1080p camera to plug into the RPi).
- [ ] **MicroSD Card** (16GB or 32GB, pre-flashed with RPi OS 64-bit Bookworm).
- [ ] **MicroSD Card Reader** (For laptop).

### **Method B Specific Components (Laptop-Only Setup)**
- [ ] **Laptop** (Using its built-in webcam or pre-recorded video).

### **Networking Device (Crucial for Both)**
- [ ] **Phone Hotspot (WPA2):** Standard lab Wi-Fi networks block device-to-device communication. Set up a personal phone hotspot. All devices (Laptop, ESP32, and RPi if using Method A) must connect to this same hotspot.

---

## 🔌 Section 2: Common ESP32 Actuator Circuit Wiring

Regardless of whether you choose Method A or Method B, wire the ESP32 circuit on the breadboard as follows:

> [!WARNING]
> **Check Grounding:** Ensure a common ground wire runs from the ESP32 `GND` pin to the breadboard's negative (-) rail. The grounds of the LEDs, buzzer, and servo must all connect to this same rail.

| Component | Pin Type | ESP32 GPIO Pin | Breadboard Connection |
| :--- | :---: | :---: | :--- |
| **SG90 Servo** | Signal (Yellow/Orange) | **GPIO 13** | Direct connection |
| **SG90 Servo** | Power VCC (Red) | **5V / VIN** | Connects to ESP32 5V pin |
| **SG90 Servo** | Ground (Brown) | **GND** | Connects to Breadboard GND rail |
| **Green LED** | Anode (+) | **GPIO 25** | $\rightarrow 220\Omega$ resistor $\rightarrow$ LED Anode |
| **Amber LED** | Anode (+) | **GPIO 26** | $\rightarrow 220\Omega$ resistor $\rightarrow$ LED Anode |
| **Red LED** | Anode (+) | **GPIO 27** | $\rightarrow 220\Omega$ resistor $\rightarrow$ LED Anode |
| **Active Buzzer** | Positive (+) | **GPIO 14** | Direct connection |
| **Common Rail** | Ground | **GND** | Connects all LED cathodes (-), buzzer negative (-), and servo ground |

---

## 🗼 METHOD A: Full Deployment (Raspberry Pi + USB Webcam + ESP32)

Use this method to demonstrate the full edge-computing pipeline running on the Raspberry Pi, publishing to a local RPi broker, and sending commands to the ESP32 and Laptop dashboard.

```
USB Webcam ──> Raspberry Pi 4 (Edge Pipeline & Local Broker)
                     |
                     +───(Local WiFi)───> ESP32 Actuator Node
                     |
                     +───(Local WiFi)───> Laptop (React Dashboard Console)
```

### **Step 1: Set Up & Boot the Raspberry Pi**
1. Flash the SD card using **Raspberry Pi Imager** on your laptop with **Raspberry Pi OS (64-bit)** (Bookworm). Click the gear icon to pre-configure:
   * Hostname (e.g. `oracle-pi.local`).
   * Enable SSH.
   * Pre-enter your phone's hotspot SSID and password.
2. Insert the SD card into the RPi, plug in the USB Webcam, connect the power, and wait 2 minutes.
3. On your laptop, open a terminal and SSH into the RPi:
   ```bash
   ssh pi@oracle-pi.local
   # or ssh pi@<RPi_IP> (check your phone hotspot's client list for the Pi's IP)
   ```
4. Install system packages and start the Mosquitto MQTT broker on the Pi:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install python3-venv python3-pip python3-opencv mosquitto mosquitto-clients -y
   ```
5. Edit the Mosquitto config on the RPi to allow remote connections and WebSockets:
   ```bash
   sudo nano /etc/mosquitto/conf.d/local.conf
   ```
   Add these lines:
   ```text
   listener 1883
   allow_anonymous true
   listener 9001
   protocol websockets
   ```
   Restart and enable the service:
   ```bash
   sudo systemctl restart mosquitto
   sudo systemctl enable mosquitto
   ```

### **Step 2: Deploy & Configure Python Pipeline on RPi**
1. On your laptop, copy the pipeline folder to the RPi:
   ```bash
   scp -r backend/rpi-edge/ pi@oracle-pi.local:~/rpi-edge/
   ```
2. On the RPi, set up a virtual environment and install packages:
   ```bash
   cd ~/rpi-edge
   python3 -m venv venv
   source venv/bin/activate
   pip install ultralytics scikit-learn numpy scipy paho-mqtt pyyaml
   ```
3. Open `config.yaml` on the RPi:
   ```bash
   nano config.yaml
   ```
   * Set `camera.source: 0` (selects the plugged-in USB webcam).
   * Set `mqtt.broker: "127.0.0.1"` (uses the broker running locally on the Pi).
   * Set `mqtt.port: 1883`.

### **Step 3: Update & Flash the ESP32 Actuator**
1. Open [main.cpp](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/esp32-actuator/src/main.cpp) in Arduino IDE or PlatformIO on your laptop.
2. Update the configuration to connect to your phone hotspot and the **Raspberry Pi's IP address**:
   ```cpp
   const char* ssid     = "YOUR_PHONE_HOTSPOT_SSID";
   const char* password = "YOUR_PHONE_HOTSPOT_PASSWORD";
   const char* mqtt_server = "<YOUR_RPI_IP_ADDRESS>"; // Set to the RPi's IP address
   const int mqtt_port     = 1883; // Standard TCP Port
   ```
3. Flash the code to the ESP32. Open the Serial Monitor at `115200` to verify it connects to the RPi broker.

### **Step 4: Launch the Laptop Dashboard**
1. In [useMqtt.js](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/frontend/dashboard/src/hooks/useMqtt.js) on your laptop, configure the WebSocket URL to point to the **Raspberry Pi's IP address**:
   ```javascript
   const BROKER_URL = 'ws://<YOUR_RPI_IP_ADDRESS>:9001/mqtt';
   ```
2. Run the dashboard server:
   ```bash
   cd frontend/dashboard
   npm run dev
   ```
   Open `http://localhost:5173` in your browser. Verify it displays "MQTT Connected".

### **Step 5: Run the Pipeline on the RPi**
1. In your SSH session on the RPi, run the script:
   ```bash
   python main.py
   ```
2. **Demonstrate:** Stand in front of the USB webcam. Watch the dashboard update live on your laptop and the physical servo gate rotate on your breadboard circuit!

---

## 💻 METHOD B: Fallback Deployment (Laptop + Built-in Webcam/Video + ESP32)

Use this method if the Raspberry Pi runs into setup issues. Your laptop serves as the Edge computer, and communication goes over the internet using a public broker.

```
               Laptop (Runs Pipeline, webcam/video, & Dashboard)
                                     |
                               (Phone Hotspot)
                                     v
                 Public MQTT Broker (broker.hivemq.com:8000)
                                     ^
                               (Phone Hotspot)
                                     |
                            ESP32 Actuator Node
```

### **Step 1: Update & Flash the ESP32 Actuator**
1. Open [main.cpp](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/esp32-actuator/src/main.cpp) in Arduino IDE or PlatformIO on your laptop.
2. Update the configuration to connect to your phone's hotspot and the **public HiveMQ broker**:
   ```cpp
   const char* ssid     = "YOUR_PHONE_HOTSPOT_SSID";
   const char* password = "YOUR_PHONE_HOTSPOT_PASSWORD";
   const char* mqtt_server = "broker.hivemq.com"; // Connect directly to public broker
   ```
3. Flash the code to the ESP32. Open the Serial Monitor to verify it connects to HiveMQ.

### **Step 2: Launch the Laptop Dashboard**
1. In [useMqtt.js](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/frontend/dashboard/src/hooks/useMqtt.js) on your laptop, ensure the broker URL points to HiveMQ:
   ```javascript
   const BROKER_URL = 'ws://broker.hivemq.com:8000/mqtt';
   ```
2. Run the dashboard server:
   ```bash
   cd frontend/dashboard
   npm run dev
   ```
   Open `http://localhost:5173` in your browser. Verify it displays "MQTT Connected".

### **Step 3: Configure and Run the Python Pipeline on your Laptop**
1. Open **[config.yaml](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/config.yaml)** on your laptop.
2. Set the MQTT section to connect to the public broker on port 8000 (WebSockets):
   ```yaml
   mqtt:
     broker: "broker.hivemq.com"
     port: 8000
   ```
3. Set your camera source:
   * **Webcam:** Set `camera.source: 0` (uses your laptop's built-in webcam).
   * **Video:** Set `camera.source: "../test/test_videos/crowd2.mp4"` (uses the crowd test video).
4. Open a terminal on your laptop, navigate to `backend/rpi-edge`, activate the venv, and run:
   ```powershell
   python main.py
   ```
5. **Demonstrate:** Walk in front of the laptop screen (or play the video) and watch the ESP32 servo gate and LEDs respond live on the table!

---

## 🎤 Section 4: Final Presentation & Demonstration Layouts

Choose the demonstration setup that matches the method you deploy:

### **Layout 1: RPi + USB Webcam (Method A Demo)**
*   **Setup:** Mount the USB webcam on a tripod or stand looking at the demo room. Mount the ESP32 servo gate next to it.
*   **Presentation:** Keep the laptop facing the evaluators showing the React dashboard. Evaluators can watch the crowd walking in the room, watch the RPi process it, and watch the physical gate close next to the camera.

---

### **Layout 2: Laptop Built-in Webcam (Method B Demo)**
*   **Setup:** Place the laptop facing the evaluators. Place the ESP32 circuit on the table right next to the keyboard.
*   **Crowd:** Teammates stand and move in the background of the room behind the presenter.
*   **Presentation:** The presenter stands to the side of the laptop. The camera captures the teammates' movements in the background, updating the dashboard on the laptop and triggering the servo gate on the table.

---

### **Layout 3: Pre-recorded Video (Method B Demo - Space Saving)**
*   **Setup:** Run Method B using the `crowd2.mp4` video. Place the ESP32 circuit next to the laptop on the table.
*   **Presentation:** The dashboard plays the crowd video, displaying bounding boxes and density heatmaps. The physical servo gate rotates, the amber/red LEDs turn on, and the buzzer sounds in perfect sync with the crowd density peaks in the video. This requires zero physical setup space and is 100% reliable!
