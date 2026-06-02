# 🏟️ Oracle — Crowd Safety Pipeline Metrics Guide

This document provides a comprehensive mathematical and algorithmic explanation of all metrics calculated in real-time by the **Oracle Crowd Safety Edge Pipeline**. 

The pipeline processes live video feeds through a sequence of steps:
$$\text{Object/Head Detection} \longrightarrow \text{Spatial \& Flow Analysis} \longrightarrow \text{Composite Risk Scoring} \longrightarrow \text{Actuation \& Alerts}$$

---

## 🗺️ Metric Architecture Overview

The computed metrics are categorized into three core domains:

```mermaid
graph TD
    subgraph Spatial Metrics
        A[People Count] --> B[Density]
        B --> C[Level of Service - LOS]
        A --> D[DBSCAN Clustering]
    end

    subgraph Motion Flow Dynamics
        E[Flow Speed] --> F[Divergence/Compression]
        E --> G[Crowd Chaos]
    end

    subgraph Safety & Decision Metrics
        B & E & F & G --> H[Composite Risk Score]
        H --> I[Trend Slope]
        H --> J[Time-To-Critical - TTC]
        H & I & J --> K[Alert Level & Gate Actuation]
    end

    style Spatial Metrics fill:#1e293b,stroke:#334155,color:#fff
    style Motion Flow Dynamics fill:#0f172a,stroke:#334155,color:#fff
    style Safety & Decision Metrics fill:#180f2a,stroke:#4c1d95,color:#fff
```

---

## 1. Spatial Metrics

These metrics quantify the physical distribution of the crowd inside the monitored zone.

### A. People Count
* **What it is**: The total number of human heads detected in the frame.
* **Calculation**: 
  Using `yolov8n-head.pt` (a custom model optimized for detecting heads in highly occluded dense crowds), we pass the pre-processed frame into the model:
  ```python
  results = model(frame, imgsz=imgsz, conf=conf_threshold, classes=[0])
  ```
  The count is the size of the detected bounding box array: $N = \text{len(centroids)}$.
* **Reference**: [detector.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/detector.py)

### B. Density ($\rho$)
* **What it is**: The number of persons per square meter ($\text{p/m}^2$) in the field of view.
* **Calculation**:
  We calibrate the pixel dimensions to real-world dimensions using a calibration constant $P_{\text{cal}}$ (pixels per meter).
  $$\text{Real-world Area } (A_m) = \frac{\text{Width}_{\text{pixels}} \times \text{Height}_{\text{pixels}}}{P_{\text{cal}}^2}$$
  $$\text{Density } (\rho) = \frac{N}{A_m} \quad (\text{persons/m}^2)$$
* **Configuration**: Default $P_{\text{cal}} = 120\text{ px/m}$.
* **Reference**: [density.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/density.py)

### C. Level of Service (LOS)
* **What it is**: An qualitative safety index (from Safe to Critical) derived from transportation engineering standards (Fruin's Pedestrian Level of Service).
* **Thresholds**:
  | Density Range ($\rho$) | LOS Category | Display Color | Safety Description |
  | :--- | :--- | :--- | :--- |
  | $\rho < 2.0\text{ p/m}^2$ | **SAFE** | Mint Green | Free movement, no physical contact. |
  | $2.0 \le \rho < 3.5\text{ p/m}^2$ | **CAUTION** | Yellow/Amber | Minor flow restriction, lane forming. |
  | $3.5 \le \rho < 5.0\text{ p/m}^2$ | **WARNING** | Orange | Severe restriction, physical contact. |
  | $\rho \ge 5.0\text{ p/m}^2$ | **CRITICAL** | Red | Dangerous congestion, risk of crush/shockwave. |
* **Reference**: [density.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/density.py)

### D. DBSCAN Clusters (Spatial Clumps)
* **What it is**: Identifies spatial sub-groups or "clumps" of dense crowds within the frame, filtering out dispersed individuals as noise.
* **Calculation**:
  Uses the **DBSCAN** (Density-Based Spatial Clustering of Applications with Noise) algorithm on the set of detected 2D centroids:
  $$\text{DBSCAN}(\text{centroids}, \epsilon, \text{min\_samples})$$
  * **$\epsilon$ (epsilon)**: The neighborhood search radius in pixels (default: $50\text{ px}$). Centroids closer than $\epsilon$ are considered neighbors.
  * **min_samples**: The minimum number of neighbors required to form a cluster (default: $3$).
* **Result**:
  * Centroids belonging to dense clusters are labeled `C0`, `C1`, `C2`, etc.
  * Spatially isolated individuals are labeled as `-1` (noise) and their text labels are hidden to reduce display clutter.
* **Reference**: [density.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/density.py)

---

## 2. Motion & Flow Dynamics

These metrics capture the velocity and pattern of crowd movement by computing dense **Farneback Optical Flow** on consecutive grayscale frames.

```
Frame (t - 1)  ┐
               ├─► Farneback Dense Flow ─► Vector Field (vx, vy) for every pixel
Frame (t)      ┘
```

### A. Flow Speed ($|\vec{v}|$)
* **What it is**: The average velocity of crowd movement, measured in pixels per frame ($\text{px/f}$).
* **Calculation**:
  For each pixel $(x, y)$, Farneback optical flow outputs horizontal velocity $v_x(x,y)$ and vertical velocity $v_y(x,y)$.
  $$\text{Magnitude at pixel } m(x, y) = \sqrt{v_x(x, y)^2 + v_y(x, y)^2}$$
  $$\text{Flow Speed } (|\vec{v}|) = \frac{1}{W \times H} \sum_{x=1}^{W} \sum_{y=1}^{H} m(x, y)$$
* **Reference**: [optical_flow.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/optical_flow.py)

### B. Divergence ($\nabla \cdot \vec{v}$)
* **What it is**: Represents whether the crowd is dispersing (expansion) or packing together (compression).
* **Mathematical Calculation**:
  We compute the spatial gradients of the horizontal and vertical velocity fields:
  $$\nabla \cdot \vec{v} = \frac{\partial v_x}{\partial x} + \frac{\partial v_y}{\partial y}$$
  The spatial derivatives $\frac{\partial v_x}{\partial x}$ and $\frac{\partial v_y}{\partial y}$ are computed using central finite differences (`np.gradient`).
* **Interpretation**:
  * **Positive Divergence ($\nabla \cdot \vec{v} > 0$)**: Outward movement/dispersion (Safe).
  * **Negative Divergence ($\nabla \cdot \vec{v} < 0$)**: Inward compression/packing (Dangerous). High negative values indicate localized bottlenecks.
* **Reference**: [optical_flow.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/optical_flow.py)

### C. Crowd Chaos ($\sigma_{\theta}$)
* **What it is**: Measures angular dispersion. High chaos means people are moving in many random, conflicting directions (turbulent flow/panic). Low chaos means orderly, unidirectional flow.
* **Calculation**:
  First, calculate the direction angle $\theta$ of the velocity vector at each moving pixel:
  $$\theta(x, y) = \text{atan2}(v_y(x, y), v_x(x, y)) \quad \in [-\pi, \pi]$$
  $$\text{Crowd Chaos } (\sigma_{\theta}) = \text{std}(\theta)$$
  Where $\text{std}$ is the standard deviation of all computed angles. Max possible value is $\pi$ rad.
* **Reference**: [optical_flow.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/optical_flow.py)

---

## 3. Safety & Decision Metrics

These metrics aggregate spatial and motion dynamics to drive automated gate actuators and broadcast safety alerts.

### A. Composite Risk Score ($R$)
* **What it is**: A unified risk score between $0.0$ (no risk) and $1.0$ (immediate threat).
* **Formula**:
  $$R = w_0 \cdot \hat{\rho} + w_1 \cdot |\hat{v}| + w_2 \cdot (1 - \hat{\nabla \cdot v}) + w_3 \cdot \hat{\sigma}_{\theta}$$
  Where:
  * **$\hat{\text{Metric}}$** represents the min-max normalized and clamped value of the metric to the range $[0, 1]$ based on empirical calibration bounds:
    * $\text{Density } \hat{\rho} \in [0.0, 6.0]$
    * $\text{Flow Speed } |\hat{v}| \in [0.0, 15.0]$
    * $\text{Divergence } \hat{\nabla \cdot v} \in [-2.0, 2.0]$
    * $\text{Chaos } \hat{\sigma}_{\theta} \in [0.0, \pi]$
  * **Weights ($w$)**: The default configured weights are:
    $$w = [0.40, 0.20, 0.25, 0.15]$$
    * **$40\%$ Weight**: Density ($\hat{\rho}$)
    * **$20\%$ Weight**: Flow Speed ($|\hat{v}|$)
    * **$25\%$ Weight**: Compression ($1 - \hat{\nabla \cdot v}$)
    * **$15\%$ Weight**: Chaos ($\hat{\sigma}_{\theta}$)
* **Reference**: [risk_engine.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/risk_engine.py)

### B. Trend Slope
* **What it is**: The rate of change of the risk score per second ($R/s$).
* **Calculation**:
  Calculated by fitting a linear regression line $R(t) = m \cdot t + c$ over a sliding window of the latest $N$ frames (default $N=10$):
  $$\text{Slope } (m) = \frac{N \sum (t \cdot R) - \sum t \sum R}{N \sum t^2 - (\sum t)^2}$$
  * A **positive slope** indicates risk is rising.
  * A **negative slope** indicates risk is subsiding.
* **Reference**: [risk_engine.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/risk_engine.py)

### C. Time-To-Critical (TTC)
* **What it is**: Estimated time (in seconds) until the composite risk score crosses the critical threshold ($0.75$ or $0.55$).
* **Calculation**:
  If the trend slope $m$ is positive (risk is rising) and the current risk is below the critical threshold:
  $$\text{TTC } = \frac{R_{\text{critical}} - R_{\text{current}}}{m} \quad (\text{seconds})$$
  * If risk is falling ($m \le 0$) or already critical, TTC is set to `N/A`.
* **Reference**: [risk_engine.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/risk_engine.py)

### D. Alert Level & Gate Actuator Command
* **What it is**: Decisions triggered by the composite risk score $R$ that dictate the physical position of the servo gate actuator and trigger buzzer alarms.
* **Logic**:
  ```python
  if risk_score >= critical_threshold:
      alert_level = "CRITICAL"
      gate_command = "GATE_CLOSE"  # Actuator rotates to 180°, turns on Buzzer & Red LED
  elif risk_score >= warning_threshold:
      alert_level = "WARNING"
      gate_command = "GATE_HALF"   # Actuator rotates to 90°, turns on Orange LED
  else:
      alert_level = "SAFE"
      gate_command = "GATE_OPEN"   # Actuator rotates to 0°, turns on Green LED
  ```
* **Threshold configurations**:
  * **Demo 1 (Open Gate)**: `warning: 0.55`, `critical: 0.75`
  * **Demo 2 (Closed Gate)**: `warning: 0.25`, `critical: 0.55`
* **Reference**: [risk_engine.py](file:///c:/Users/rohan/OneDrive/Desktop/cursorOP/IOT_EL/backend/rpi-edge/risk_engine.py)
