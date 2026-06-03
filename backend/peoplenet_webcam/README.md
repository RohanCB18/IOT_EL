# PeopleNet Webcam Detection

Real-time person / head / face / bag detection using
**NVIDIA PeopleNet** (ResNet-34 backbone) via ONNX Runtime.

---

## Folder contents

| File | Purpose |
|---|---|
| `webcam_peoplenet.py` | **Main script** — opens webcam and runs live detection |
| `peoplenet_detector.py` | `PeopleNetDetector` class — model loading, pre/post-processing |
| `postprocess_utils.py` | DetectNet_v2 grid decoding + NMS (pure NumPy) |
| `setup_model.py` | One-time helper to link/copy the ONNX model here |
| `requirements.txt` | Python dependencies |

---

## Quick start

### 1. Install dependencies

```bash
# Inside the backend venv or a new one
pip install -r requirements.txt
```

### 2. Link the model

```bash
# From inside peoplenet_webcam/
python setup_model.py
```

This creates a symlink (or copy) of `resnet34_peoplenet.onnx` from
`../backend/model_weights/` so the script can find it automatically.

Alternatively, copy it manually:
```bash
copy ..\backend\model_weights\resnet34_peoplenet.onnx .
```

### 3. Run

```bash
# Default: webcam 0, CPU, all classes
python webcam_peoplenet.py

# CUDA GPU
python webcam_peoplenet.py --device cuda

# Persons + faces only
python webcam_peoplenet.py --classes person face

# Higher confidence (fewer false positives)
python webcam_peoplenet.py --threshold 0.55

# Save annotated video
python webcam_peoplenet.py --save-video output.mp4

# Camera index 1
python webcam_peoplenet.py --camera 1
```

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| `q` | Quit |
| `p` | Pause / Resume |
| `s` | Save current frame as `capture_YYYYMMDD_HHMMSS.png` |
| `+` | Raise confidence threshold by 0.05 |
| `-` | Lower confidence threshold by 0.05 |

---

## Detection classes & colours

| Class | Colour | Description |
|---|---|---|
| `person` | 🟢 Green | Full body |
| `face` | 🔴 Red | Head / face |
| `bag` | 🔵 Blue | Bag / backpack |

---

## How PeopleNet works (end-to-end)

```
Webcam frame (BGR, any resolution)
          │
          ▼
    ┌─────────────────────────────────────┐
    │          Pre-processing             │
    │  • BGR → RGB                        │
    │  • Resize to 960 × 544             │
    │  • Pixel values ÷ 255  → [0,1]     │
    │  • HWC → CHW  (+batch dim)          │
    └──────────────┬──────────────────────┘
                   │  float32 (1,3,544,960)
                   ▼
    ┌─────────────────────────────────────┐
    │    ResNet-34 PeopleNet (ONNX)       │
    │                                     │
    │  output_cov  : (1, 3, 34, 60)      │  ← confidence per grid cell
    │  output_bbox : (1,12, 34, 60)      │  ← raw bbox offsets per cell
    └──────────────┬──────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────┐
    │  DetectNet_v2 Post-processing       │
    │  • Filter cells below threshold     │
    │  • Decode bbox via box-norm formula │
    │      x1 = (raw_x1 - gc_w) × -35   │
    │      y1 = (raw_y1 - gc_h) × -35   │
    │      x2 = (raw_x2 + gc_w) ×  35   │
    │      y2 = (raw_y2 + gc_h) ×  35   │
    │  • Scale back to original frame     │
    │  • Per-class NMS (IoU threshold)    │
    └──────────────┬──────────────────────┘
                   │  list of dicts
                   ▼
    ┌─────────────────────────────────────┐
    │  Visualisation                      │
    │  • Coloured bounding boxes          │
    │  • Class label + confidence score   │
    │  • HUD overlay (FPS / stats)        │
    └─────────────────────────────────────┘
```

### Grid explanation

The model output grid is **34 × 60** cells (stride = 16 pixels on the
544 × 960 model input).  Each cell independently predicts whether an
object's centre falls inside it, and the offsets to decode the box.

The normalisation constant **BOX_NORM = 35.0** and the formula above
come from NVIDIA's official reference implementation on the
[developer forum](https://forums.developer.nvidia.com/t/run-peoplenet-with-tensorrt/128000/22).

---

## GPU setup (optional)

1. Uninstall CPU-only runtime: `pip uninstall onnxruntime`
2. Install GPU runtime: `pip install onnxruntime-gpu`
3. Ensure CUDA 12.x and cuDNN 9.x are installed.
4. Run: `python webcam_peoplenet.py --device cuda`
