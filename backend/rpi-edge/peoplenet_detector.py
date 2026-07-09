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

    def _init_session(self):
        # ── Session options: full graph optimisation + thread budget ──────────
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Keep thread counts sensible — unlimited threads cause OS scheduling
        # contention that paradoxically slows inference on a GPU pipeline.
        opts.intra_op_num_threads = 4
        opts.inter_op_num_threads = 1
        opts.enable_mem_pattern   = True
        opts.enable_cpu_mem_arena = True

        providers = []
        if self.device == 'cuda':
            if 'CUDAExecutionProvider' in ort.get_available_providers():
                # arena_extend_strategy=0 → pre-allocate GPU arena; avoids
                # per-call cudaMalloc which is a common hidden latency source.
                cuda_opts = {
                    "arena_extend_strategy":    "kNextPowerOfTwo",
                    "cudnn_conv_algo_search":    "EXHAUSTIVE",
                    "do_copy_in_default_stream": True,
                }
                providers.append(('CUDAExecutionProvider', cuda_opts))
                print("[PeopleNet] Using CUDA execution provider (ORT_ENABLE_ALL)")
            else:
                print("[PeopleNet] CUDA not available, falling back to CPU")
        providers.append('CPUExecutionProvider')

        self.session = ort.InferenceSession(
            str(self.model_path), sess_options=opts, providers=providers
        )

        # Verify if CUDA was actually loaded or if ONNX Runtime fell back to CPU
        active_providers = self.session.get_providers()
        if "CUDAExecutionProvider" in active_providers or "TensorrtExecutionProvider" in active_providers:
            self.device = "cuda"
        else:
            self.device = "cpu"
            if providers[0] in ("CUDAExecutionProvider",) or \
               (isinstance(providers[0], tuple) and providers[0][0] == "CUDAExecutionProvider"):
                print("[PeopleNet] CUDA Execution Provider failed to load. Falling back to CPU.")

        self.input_name   = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        print(f"[PeopleNet] Input  name : {self.input_name}")
        print(f"[PeopleNet] Output names: {self.output_names}")

        # ── Pre-allocate a reusable input tensor buffer (avoids per-frame
        #    heap allocation in preprocess). Shape: (1, 3, MODEL_H, MODEL_W)
        self._input_buffer = np.zeros(
            (1, 3, MODEL_H, MODEL_W), dtype=np.float32
        )

        # ── Warmup: first few CUDA inferences are slow because cuDNN
        #    benchmarks convolution algorithms and ONNX RT allocates GPU
        #    memory pools. Run 3 dummy passes so real frames are fast.
        print("[PeopleNet] Warming up GPU (3 passes)…")
        for _ in range(3):
            self.session.run(
                self.output_names,
                {self.input_name: self._input_buffer}
            )
        print("[PeopleNet] Warmup complete.")

    # ── Pre-processing ───────────────────────────────────────────────────────
    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, int, int]:
        """
        BGR frame  →  float32 NCHW tensor ready for ONNX Runtime.

        Uses cv2.dnn.blobFromImage which performs BGR→RGB, resize, pixel
        scaling ([0,1]) and HWC→NCHW layout in a single optimised C++ call.
        """
        orig_h, orig_w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            image,
            scalefactor = 1.0 / 255.0,
            size        = (MODEL_W, MODEL_H),
            mean        = (0.0, 0.0, 0.0),
            swapRB      = True,   # BGR → RGB
            crop        = False,
        )
        return blob, orig_h, orig_w

    # ── Inference ────────────────────────────────────────────────────────────
    def infer(self, tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run ONNX Runtime inference.

        Uses session.run() directly (IOBinding requires CUDA-capable ORT build
        with numpy_helper; plain run() with a pre-allocated input buffer is
        already zero-copy on the input side because ORT reads from the buffer
        pointer without an extra copy when the array is C-contiguous float32).

        Returns
        -------
        (output_cov, output_bbox)  both as numpy arrays
        """
        raw = self.session.run(self.output_names, {self.input_name: tensor})

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
