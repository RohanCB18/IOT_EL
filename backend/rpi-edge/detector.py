"""
detector.py — Unified PersonDetector with pluggable backend
============================================================

Strategy pattern: select the detection backend via config.yaml:

    detection:
      backend: "peoplenet"   # ← default (NVIDIA PeopleNet ONNX, faster + more accurate)
      backend: "yolo"        # ← fallback (YOLOv8, requires ultralytics)

Public API (unchanged — main.py requires zero modifications):
    detector = PersonDetector(config_path)
    centroids, boxes = detector.detect(frame)
    vis_frame        = detector.draw_detections(frame, centroids, boxes)

CUDA is used automatically for both backends when available.
"""

import cv2
import yaml
import torch
import numpy as np
from pathlib import Path
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Helper: auto-detect best available device string
# ---------------------------------------------------------------------------

def _best_device() -> str:
    """Returns 'cuda' if a CUDA GPU is available, else 'cpu'."""
    return "cuda" if torch.cuda.is_available() else "cpu"


# ---------------------------------------------------------------------------
# PeopleNet Backend
# ---------------------------------------------------------------------------

class _PeopleNetBackend:
    """
    Thin adapter that wraps PeopleNetDetector and exposes
    the same (centroids, boxes) interface as the YOLO backend.
    """

    def __init__(self, cfg: dict):
        from peoplenet_detector import PeopleNetDetector

        model_path = cfg.get("peoplenet_model_path", "models/resnet34_peoplenet.onnx")
        confidence = cfg.get("peoplenet_confidence", 0.40)
        nms_thresh = cfg.get("peoplenet_nms", 0.50)
        device     = _best_device()

        print(f"[INFO] Loading PeopleNet from: {model_path}")
        self._detector = PeopleNetDetector(
            model_path           = model_path,
            device               = device,
            confidence_threshold = confidence,
            nms_threshold        = nms_thresh,
        )
        self.device      = device
        self.name        = "PeopleNet"
        self._last_dets  = []   # cache for draw_detections

    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> Tuple[List[Tuple], List[Tuple]]:
        """
        Run PeopleNet person-only detection.

        Returns
        -------
        centroids : list of (cx, cy) floats
        boxes     : list of (x1, y1, x2, y2) ints  (pixel coords)
        """
        dets = self._detector.detect_persons(frame)
        self._last_dets = dets           # keep for styled visualisation

        centroids = []
        boxes     = []
        for d in dets:
            x1, y1, x2, y2 = int(d["x1"]), int(d["y1"]), int(d["x2"]), int(d["y2"])
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            centroids.append((cx, cy))
            boxes.append((x1, y1, x2, y2))

        return centroids, boxes

    # Auto-hide labels when the crowd is dense — each label = 3 extra OpenCV
    # calls (getTextSize + background rect + putText). At 148 detections that
    # alone costs ~90 ms. Switch to boxes-only above this threshold.
    _LABEL_THRESHOLD = 25

    def draw_detections(self, frame: np.ndarray,
                        centroids: List[Tuple],
                        boxes: List[Tuple]) -> np.ndarray:
        """
        Use PeopleNetDetector's styled visualiser when last_dets are available.
        Labels are automatically hidden when detection count > _LABEL_THRESHOLD
        to prevent the visualisation loop from becoming the pipeline bottleneck.
        """
        if not self._last_dets:
            return _simple_draw(frame, centroids, boxes)

        dense = len(self._last_dets) > self._LABEL_THRESHOLD
        vis   = self._detector.visualize(
            frame, self._last_dets,
            show_labels     = not dense,
            show_confidence = not dense,
            thickness       = 1,
        )

        # Draw centroids only in sparse mode (skipping saves ~2ms in dense mode)
        if not dense:
            for (cx, cy) in centroids:
                cv2.circle(vis, (int(cx), int(cy)), 3, (0, 0, 255), -1)

        return vis


# ---------------------------------------------------------------------------
# YOLO Backend
# ---------------------------------------------------------------------------

class _YOLOBackend:
    """
    Wraps ultralytics YOLO and exposes the same detect() interface.
    Forces CUDA + FP16 when available.
    """

    def __init__(self, cfg: dict):
        from ultralytics import YOLO

        model_path      = cfg.get("model_path", "yolov8s.pt")
        self.conf       = cfg.get("confidence", 0.25)
        self.imgsz      = cfg.get("imgsz", 640)
        self.device     = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.name       = "YOLOv8"

        print(f"[INFO] Loading YOLOv8 model from: {model_path}")
        self._model = YOLO(model_path)
        print(f"[INFO] YOLOv8 loaded. Device: {self.device}  FP16: {self.device != 'cpu'}")

    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> Tuple[List[Tuple], List[Tuple]]:
        """
        Run YOLOv8 person detection (class 0 in COCO).

        Returns
        -------
        centroids : list of (cx, cy) floats
        boxes     : list of (x1, y1, x2, y2) ints
        """
        results = self._model(
            frame,
            imgsz   = self.imgsz,
            conf    = self.conf,
            classes = [0],           # person class only
            device  = self.device,
            half    = (self.device != "cpu"),   # FP16 on GPU
            verbose = False,
        )

        centroids = []
        boxes     = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                centroids.append((cx, cy))
                boxes.append((int(x1), int(y1), int(x2), int(y2)))

        return centroids, boxes

    def draw_detections(self, frame: np.ndarray,
                        centroids: List[Tuple],
                        boxes: List[Tuple]) -> np.ndarray:
        return _simple_draw(frame, centroids, boxes)


# ---------------------------------------------------------------------------
# Shared drawing helper
# ---------------------------------------------------------------------------

def _simple_draw(frame: np.ndarray,
                 centroids: List[Tuple],
                 boxes: List[Tuple]) -> np.ndarray:
    """Plain green-box + red-dot visualisation (used by YOLO backend)."""
    vis = frame.copy()
    for (x1, y1, x2, y2), (cx, cy) in zip(boxes, centroids):
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 1)
        cv2.circle(vis, (int(cx), int(cy)), 3, (0, 0, 255), -1)
    return vis


# ---------------------------------------------------------------------------
# Public facade — the only class main.py ever imports
# ---------------------------------------------------------------------------

class PersonDetector:
    """
    Unified person-detection facade.

    Reads `detection.backend` from config.yaml:
      "peoplenet"  → NVIDIA PeopleNet ONNX (default, recommended)
      "yolo"       → YOLOv8 via ultralytics (fallback)

    Public interface is identical regardless of backend:
        centroids, boxes = detector.detect(frame)
        vis              = detector.draw_detections(frame, centroids, boxes)
    """

    def __init__(self, config_path: str = "config.yaml", profile: str = None):
        with open(config_path, "r") as f:
            full_cfg = yaml.safe_load(f)
            
        if "profiles" in full_cfg:
            p = profile if profile and profile in full_cfg["profiles"] else "0"
            cfg = full_cfg["profiles"][p]["detection"]
        else:
            cfg = full_cfg["detection"]

        backend_key = cfg.get("backend", "peoplenet").lower().strip()

        if backend_key == "peoplenet":
            self._backend = _PeopleNetBackend(cfg)
        elif backend_key == "yolo":
            self._backend = _YOLOBackend(cfg)
        else:
            raise ValueError(
                f"[Detector] Unknown backend '{backend_key}'. "
                "Choose 'peoplenet' or 'yolo' in config.yaml → detection.backend"
            )

        print(
            f"[Detector] Backend : {self._backend.name}  |  "
            f"Device : {self._backend.device.upper()}"
        )

    # ------------------------------------------------------------------
    # Public API (identical contract to the old detector.py)
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> Tuple[List[Tuple], List[Tuple]]:
        """
        Run person detection on a BGR frame.

        Returns
        -------
        centroids : list[(cx, cy)]  — float pixel coords of each person's centre
        boxes     : list[(x1,y1,x2,y2)] — int bounding boxes in pixel space
        """
        return self._backend.detect(frame)

    def draw_detections(self, frame: np.ndarray,
                        centroids: List[Tuple],
                        boxes: List[Tuple]) -> np.ndarray:
        """
        Visualise detections on a copy of *frame* and return it.
        Style differs per backend (PeopleNet uses its own styled visualiser).
        """
        return self._backend.draw_detections(frame, centroids, boxes)

    # ------------------------------------------------------------------
    # Convenience properties (used for the startup log in main.py)
    # ------------------------------------------------------------------

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def device(self) -> str:
        return self._backend.device


# ---------------------------------------------------------------------------
# Quick self-test when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    detector    = PersonDetector(config_path)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam.")
        sys.exit(1)

    print("[INFO] Starting self-test stream... Press 'q' to exit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        centroids, boxes = detector.detect(frame)
        vis = detector.draw_detections(frame, centroids, boxes)

        cv2.putText(
            vis, f"Backend: {detector.backend_name}  Count: {len(centroids)}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2,
        )
        cv2.imshow("PersonDetector Self-Test", vis)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
