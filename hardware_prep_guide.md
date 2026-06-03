# 🏟️ Intelligent Crowd Flow & Density Safety Oracle — Laptop + ESP32 Deployment Guide

This guide describes how to set up, wire, configure, and demonstrate the **Intelligent Crowd Flow & Density Safety Oracle** using a **Laptop** (as the Edge processing node) and an **ESP32** (as the physical actuator gate node).

---

## 🗺️ System Architecture

The setup operates as a distributed edge-computing IoT network. The laptop handles the heavy computer vision calculations and coordinates the physical gate via a public MQTT broker:

```mermaid
graph LR
    subgraph Laptop (Edge Node)
        Webcam[Webcam / Video Input] -->|Raw Frames| PythonPipeline[Python Pipeline<br>YOLOv8 + Optical Flow]
        PythonPipeline -->|Dashboard Data| ReactDashboard[React Dashboard<br>http://localhost:5173]
    end

    subgraph Cloud Broker
        PythonPipeline -->|Publish MQTT Metrics / Commands| HiveMQ[Public MQTT Broker<br>broker.hivemq.com:8000]
    end

    subgraph Physical Gate Node
        HiveMQ -->|Subscribe to Actuation Command| ESP32[ESP32 DevKit v1]
        ESP32 -->|Angle Command| Servo[SG90 Servo Gate]
        ESP32 -->|State LEDs| LEDs[Green/Amber/Red LEDs]
        ESP32 -->|Siren Trigger| Buzzer[Active Buzzer]
    end

    %% Networking connection style %%
    Laptop --- |Phone Hotspot Wi-Fi| HiveMQ
    ESP32 --- |Phone Hotspot Wi-Fi| HiveMQ
    
    style Laptop fill:#1e293b,stroke:#334155,color:#fff
    style Cloud Broker fill:#0f172a,stroke:#334155,color:#fff
    style Physical Gate Node fill:#180f2a,stroke:#4c1d95,color:#fff
```

---

## 🛠️ Section 1: Hardware Components List

Ensure you have gathered the following components for your lab setup:

### **1. Edge Processing Node (Laptop)**
* **Laptop**: Windows/Mac/Linux with built-in webcam (or external USB camera) to run the YOLOv8 and Optical Flow models.

### **2. Actuator & Indicators (The "Gate" Node)**
* **ESP32 DevKit v1** (or any standard NodeMCU ESP32 board).
* **SG90 Micro Servo Motor** (controls physical gate rotation).
* **Active Buzzer** (3.3V or 5V; sounds automatically when supplied with voltage).
* **LED Status Lights (3 pieces)**: 1× Green (Safe), 1× Amber (Warning), 1× Red (Critical).
* **Resistors**: 3× $220\Omega$ resistors (protects the LEDs from burning out).
* **Breadboard & Jumper Wires**: Solderless breadboard, ~10× Male-to-Male (M-M), ~5× Male-to-Female (M-F) jumpers.
* **Micro-USB Cable**: For powering the ESP32 and flashing firmware from your laptop.
* **Gate Indicator**: A small piece of cardboard or stick taped to the servo horn to visually show the gate opening and closing.

### **3. Networking Device**
* **Mobile Phone Hotspot (WPA2)**: Standard institutional/lab Wi-Fi networks block device-to-device communication and raw socket ports. Set up a personal phone hotspot. Both your **Laptop** and your **ESP32** must connect to this same hotspot network.

---

## 🔌 Section 2: ESP32 Actuator Circuit Wiring

Wire your components on the breadboard according to the connection map below:

> [!WARNING]
> **Check Grounding (GND):** Ensure a common ground wire runs from the ESP32 `GND` pin to the negative (-) rail of your breadboard. The grounds (cathodes) of the three LEDs, the negative pin of the buzzer, and the brown wire of the servo must all connect to this same ground rail.

```
                  +--------------------------------+
                  |         ESP32 DevKit           |
                  |                                |
                  |  GND  D13  D14  D25  D26  D27  |
                  +---|----|----|----|----|----|---+
                      |    |    |    |    |    |
                      |    |    |    |    |    +---> [ 220Ω Resistor ] ---> (Red LED Anode)
                      |    |    |    |    +---------> [ 220Ω Resistor ] ---> (Amber LED Anode)
                      |    |    |    +--------------> [ 220Ω Resistor ] ---> (Green LED Anode)
                      |    |    +----------------------------------------> (Buzzer + Pin)
                      |    +---------------------------------------------> (Servo Orange Signal)
                      v
             [ Common GND Rail ] <--- (Servo Brown GND, LED Cathodes, Buzzer - Pin)
```

### **Pin Connection Table**

| Component | Pin / Wire Color | ESP32 Pin | Breadboard / Circuit Connection |
| :--- | :---: | :---: | :--- |
| **SG90 Servo** | Signal (Yellow/Orange) | **GPIO 13** | Connect directly to ESP32 pin. |
| **SG90 Servo** | Power VCC (Red) | **5V / VIN** | Connect directly to ESP32 5V (or VIN) pin. |
| **SG90 Servo** | Ground (Brown) | **GND** | Connects to the negative (-) common ground rail. |
| **Green LED** | Long Leg Anode (+) | **GPIO 25** | Connects to ESP32 via a $220\Omega$ resistor. |
| **Amber LED** | Long Leg Anode (+) | **GPIO 26** | Connects to ESP32 via a $220\Omega$ resistor. |
| **Red LED** | Long Leg Anode (+) | **GPIO 27** | Connects to ESP32 via a $220\Omega$ resistor. |
| **Active Buzzer** | Positive (+) / Long Leg | **GPIO 14** | Connect directly to ESP32 pin. |
| **LEDs / Buzzer** | Cathodes (-) / Short Legs | **GND** | All connect to the negative (-) common ground rail. |

---

## 🚀 Section 3: Step-by-Step Deployment Steps

Follow these steps to deploy and test the entire system in the lab:

### **Step 1: Network Setup**
1. Turn on the **Mobile Hotspot** on your phone (ensure WPA2 security is active).
2. Connect your **Laptop** to the phone's hotspot.
3. Keep the SSID and password handy, as you will write them into the ESP32 code.

---

### **Step 2: Flash the ESP32 Firmware**
1. Open the [esp32-actuator](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/esp32-actuator) project in PlatformIO (VS Code) or open [main.cpp](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/esp32-actuator/src/main.cpp) in the Arduino IDE.
2. Edit lines 9 and 10 to input your phone's hotspot credentials:
   ```cpp
   const char* ssid     = "YOUR_PHONE_HOTSPOT_SSID";
   const char* password = "YOUR_PHONE_HOTSPOT_PASSWORD";
   ```
3. Ensure the MQTT configuration points to the public HiveMQ broker:
   ```cpp
   const char* mqtt_server = "broker.hivemq.com";
   const int mqtt_port     = 1883; // Standard TCP port
   const char* mqtt_topic  = "oracle_rohan_123/node1/actuation"; // Unique topic matching python config
   ```
4. Connect the ESP32 to your laptop using a micro-USB cable.
5. Compile and **Upload** the sketch.
6. Open the Serial Monitor (Baud rate: `115200`). Verify that the ESP32 successfully connects to the Wi-Fi hotspot and prints:
   `[WIFI] Connected successfully!` and `[MQTT] Connecting to broker... Connected!`

---

### **Step 3: Run the Laptop Python Pipeline**
1. Open a terminal on your laptop and navigate to the edge processing folder:
   ```bash
   cd backend/rpi-edge
   ```
2. Activate your virtual environment:
   ```powershell
   .\venv\Scripts\activate
   ```
3. Run the pipeline configuration that matches the demonstration you want to present:

   * **Demo 1: Safe / Open Gate Demo (Landscape webcam/video)**
     ```powershell
     python main.py --config config_demo1_open.yaml
     ```
     *(The gate remains OPEN at $0^{\circ}$. Green LED is active).*

   * **Demo 2: Critical / Closed Gate Demo (Portrait dense video)**
     ```powershell
     python main.py --config config_demo2_closed.yaml
     ```
     *(The gate CLOSES immediately to $180^{\circ}$. Red LED is active and Buzzer sounds).*

   * **Demo 3: Warning / Half-Open Gate Demo (Portrait medium video)**
     ```powershell
     python main.py --config config_demo3_half.yaml
     ```
     *(The gate stays half-open at $90^{\circ}$. Amber LED is active).*

---

### **Step 4: Launch the React Dashboard Console**
1. Open a second terminal window on your laptop.
2. Navigate to the dashboard directory:
   ```bash
   cd frontend/dashboard
   ```
3. Start the local development server:
   ```bash
   npm run dev
   ```
4. Open your browser and navigate to `http://localhost:5173`.
5. Verify that the dashboard status shows **MQTT Connected** (it subscribes to `ws://broker.hivemq.com:8000/mqtt` to pull metrics and live frames).

---

## 🎤 Section 4: Live Presentation Layouts

Use these three layouts to present the project to evaluators:

### **Layout 1: Live Webcam (Interactive Demo)**
* **Setup**: Place the laptop on the table facing the evaluators. Place the ESP32 breadboard circuit directly next to the keyboard. Run **Demo 1** with your laptop webcam (`camera.source: 0`).
* **Visual Presentation**: 
  * The evaluators will see a clean portrait video window with the sidebar HUD on the left showing 1–2 people detected (you and your teammates). The physical gate remains open with the green LED on.
  * **The Interaction**: Gather 3–4 teammates and crowd closely in front of the laptop camera while waving your hands. Evaluators will watch the live density and risk scores rise on the screen, triggering the amber LED and rotating the physical servo gate to $90^{\circ}$ or $180^{\circ}$ in real-time.

---

### **Layout 2: High-Density Crowd Video (Safety System Demo)**
* **Setup**: Run **Demo 2** (`config_demo2_closed.yaml`).
* **Visual Presentation**: 
  * The screen displays the high-density crowd video (`crowd2.mp4`). The YOLO model tracks and counts **292 heads** in the frame.
  * The density jumps to $\approx 8\text{ p/m}^2$ (Level of Service: **CRITICAL**).
  * Evaluators will see the risk score cross the safety threshold, instantly turning on the red LED, triggering the physical buzzer alarm, and rotating the servo gate to the fully closed position ($180^{\circ}$) to prevent further entry.

---

### **Layout 3: Warning/Flow Control Video (Rate Limitation Demo)**
* **Setup**: Run **Demo 3** (`config_demo3_half.yaml`).
* **Visual Presentation**: 
  * The screen displays the medium-density crowd video (`crowd4.mp4`). The model tracks bodies, calculating a steady warning risk score of $\approx 0.40$.
  * Evaluators will see the yellow/amber LED activate and the physical servo gate rotate and hold at $90^{\circ}$ (half-open) to demonstrate automated flow rate restriction.
