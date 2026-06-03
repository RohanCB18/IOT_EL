"""
peoplenet_detector.py
=====================
NVIDIA PeopleNet (ResNet-34 ONNX) wrapper.

Model detects three classes in order:
  0  person
  1  bag
  2  face

Input tensor : float32, NCHW (1, 3, 544, 960), values in [0, 1]
Output tensors (sorted by channel count during init):
  output_cov  : (1,  3, 34, 60)  — confidence/coverage maps
  output_bbox : (1, 12, 34, 60)  — raw bounding-box offsets

Post-processing:
  • Vectorised DetectNet_v2 box decoding  (postprocess_utils.py)
  • Per-class NMS
"""

import numpy as np
import cv2
from pathlib import Path
from typing import List, Optional, Tuple

# Preload CUDA DLLs before importing onnxruntime (fixes Windows pip-CUDA issues)
try:
    import onnxruntime as _ort_preload
    _ort_preload.preload_dlls(cuda=True, cudnn=True)
except Exception:
    pass

import onnxruntime as ort
from postprocess_utils import (
    postprocess_detectnet_vectorized,
    nms,
    MODEL_W,
    MODEL_H,
)


class PeopleNetDetector:
    """
    NVIDIA PeopleNet detector using ONNX Runtime.

    Usage
    -----
    detector = PeopleNetDetector(model_path="resnet34_peoplenet.onnx")
    detections = detector.detect(frame)          # all classes
    persons    = detector.detect(frame, classes=['person'])
    vis        = detector.visualize(frame, detections)
    """

    # ── Class definitions (must match NVIDIA model output order) ────────────
    CLASSES = ['person', 'bag', 'face']

    # ── Colours for visualisation (BGR) ─────────────────────────────────────
    COLORS = {
        'person': (0,  255,   0),   # green
        'bag':    (255,  0,   0),   # blue
        'face':   (0,   0, 255),    # red
    }

    def __init__(
        self,
        model_path:           str,
        device:               str   = 'cpu',
        confidence_threshold: float = 0.4,
        nms_threshold:        float = 0.5,
    ):
        """
        Parameters
        ----------
        model_path           : absolute or relative path to the .onnx file
        device               : 'cuda' or 'cpu'
        confidence_threshold : minimum confidence to keep a detection
        nms_threshold        : IoU threshold for NMS suppression
        """
        self.model_path           = Path(model_path)
        self.device               = device
        self.confidence_threshold = confidence_threshold
        self.nms_threshold        = nms_threshold

        if not self.model_path.exists():
            raise FileNotFoundError(f"[PeopleNet] Model not found: {self.model_path}")

        self._init_session()

        print(f"[PeopleNet] Loaded  : {self.model_path.name}")
        print(f"[PeopleNet] Device  : {self.device}")
        print(f"[PeopleNet] Input   : 3 × {MODEL_H} × {MODEL_W}  (CHW)")
        print(f"[PeopleNet] Classes : {self.CLASSES}")

    # ── ONNX session ─────────────────────────────────────────────────────────
    def _init_session(self):
        providers = []
        if self.device == 'cuda':
            if 'CUDAExecutionProvider' in ort.get_available_providers():
                providers.append('CUDAExecutionProvider')
                print("[PeopleNet] Using CUDA execution provider")
            else:
                print("[PeopleNet] CUDA not available, falling back to CPU")
        providers.append('CPUExecutionProvider')

        self.session    = ort.InferenceSession(str(self.model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        print(f"[PeopleNet] Input  name : {self.input_name}")
        print(f"[PeopleNet] Output names: {self.output_names}")

    # ── Pre-processing ───────────────────────────────────────────────────────
    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, int, int]:
        """
        BGR frame  →  float32 NCHW tensor ready for ONNX Runtime.

        Steps
        -----
        1. BGR → RGB
        2. Resize to (MODEL_W, MODEL_H) = (960, 544)
        3. Scale pixel values to [0, 1]
        4. HWC → CHW, add batch dimension
        """
        orig_h, orig_w = image.shape[:2]
        rgb     = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (MODEL_W, MODEL_H), interpolation=cv2.INTER_LINEAR)
        scaled  = resized.astype(np.float32) / 255.0
        chw     = np.transpose(scaled, (2, 0, 1))
        tensor  = np.expand_dims(chw, axis=0)       # (1, 3, H, W)
        return tensor, orig_h, orig_w

    # ── Inference ────────────────────────────────────────────────────────────
    def infer(self, tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run ONNX Runtime inference.

        Returns
        -------
        (output_cov, output_bbox)  both as numpy arrays
        """
        raw = self.session.run(None, {self.input_name: tensor})

        output_cov  = None
        output_bbox = None

        n_classes = len(self.CLASSES)   # 3
        for out in raw:
            if out.shape[1] == n_classes:
                output_cov  = out
            elif out.shape[1] == n_classes * 4:
                output_bbox = out

        if output_cov is None or output_bbox is None:
            shapes = [o.shape for o in raw]
            raise ValueError(f"[PeopleNet] Unexpected output shapes: {shapes}. "
                             f"Expected channels {n_classes} and {n_classes*4}.")

        return output_cov, output_bbox

    # ── Detect ───────────────────────────────────────────────────────────────
    def detect(
        self,
        image:                np.ndarray,
        confidence_threshold: Optional[float]     = None,
        classes:              Optional[List[str]] = None,
    ) -> List[dict]:
        """
        Detect objects in a single BGR frame.

        Parameters
        ----------
        image                : BGR numpy array (H, W, 3)
        confidence_threshold : overrides instance default if provided
        classes              : restrict to subset, e.g. ['person', 'face']
                               (None → all three classes)

        Returns
        -------
        List of dicts:
          {'x1', 'y1', 'x2', 'y2', 'confidence', 'class_id', 'class_name'}
        All coordinates are in *original* image pixel space.
        """
        thr = confidence_threshold if confidence_threshold is not None \
              else self.confidence_threshold

        if classes:
            analysis_classes = [self.CLASSES.index(c) for c in classes
                                 if c in self.CLASSES]
        else:
            analysis_classes = None

        tensor, orig_h, orig_w = self.preprocess(image)
        cov, bbox              = self.infer(tensor)

        detections = postprocess_detectnet_vectorized(
            output_bbox      = bbox,
            output_cov       = cov,
            num_classes      = len(self.CLASSES),
            min_confidence   = thr,
            analysis_classes = analysis_classes,
            orig_width       = orig_w,
            orig_height      = orig_h,
        )

        detections = nms(detections, self.nms_threshold)

        for d in detections:
            d['class_name'] = self.CLASSES[d['class_id']]

        return detections

    def detect_persons(
        self,
        image:                np.ndarray,
        confidence_threshold: Optional[float] = None,
    ) -> List[dict]:
        """Convenience: detect only persons."""
        return self.detect(image, confidence_threshold, classes=['person'])

    # ── Visualisation ────────────────────────────────────────────────────────
    def visualize(
        self,
        image:           np.ndarray,
        detections:      List[dict],
        show_labels:     bool = True,
        show_confidence: bool = True,
        thickness:       int  = 2,
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels on a copy of *image*.

        Color coding:
          green → person
          blue  → bag
          red   → face
        """
        result = image.copy()
        font        = cv2.FONT_HERSHEY_SIMPLEX
        font_scale  = 0.55
        font_thick  = 1

        for det in detections:
            cn    = det.get('class_name', self.CLASSES[det['class_id']])
            color = self.COLORS.get(cn, (255, 255, 255))

            x1 = max(0, int(det['x1']))
            y1 = max(0, int(det['y1']))
            x2 = min(result.shape[1], int(det['x2']))
            y2 = min(result.shape[0], int(det['y2']))

            cv2.rectangle(result, (x1, y1), (x2, y2), color, thickness)

            if show_labels or show_confidence:
                parts = []
                if show_labels:
                    parts.append(cn)
                if show_confidence:
                    parts.append(f"{det['confidence']:.2f}")
                label = " ".join(parts)

                (tw, th), _ = cv2.getTextSize(label, font, font_scale, font_thick)
                cv2.rectangle(result, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
                cv2.putText(result, label, (x1 + 2, y1 - 3),
                            font, font_scale, (255, 255, 255), font_thick, cv2.LINE_AA)

        return result
