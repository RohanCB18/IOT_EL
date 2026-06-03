import numpy as np
# pyrefly: ignore [missing-import]
import cv2


class OpticalFlowAnalyser:
    """
    Computes dense Farneback optical flow between consecutive greyscale frames
    and extracts three crowd-motion metrics:

      1. flow_magnitude  (|v̄|)  — mean speed of all pixels (how fast crowd moves)
      2. divergence      (∇·v)  — compression/expansion signal
                                  negative → crowd compressing (dangerous)
                                  positive → crowd spreading out (safe)
      3. chaos           (σθ)   — angular standard deviation of flow vectors
                                  high → people moving in many different directions (panic-like)
                                  low  → orderly, uniform movement

    Performance notes
    -----------------
    • `downsample_res`: Farneback cost scales as O(W×H). Running at 320×240 instead
      of 640×480 gives 4× speedup with negligible metric accuracy loss.
    • `frame_skip`: Only compute flow every N frames; return cached metrics otherwise.
      N=2 halves the optical-flow budget at the cost of 1-frame metric lag.
    """

    # Farneback parameters — tuned for downsampled 320×240 resolution
    FB_PARAMS = dict(
        pyr_scale  = 0.5,   # each pyramid level shrinks by half
        levels     = 2,     # reduced from 3 — sufficient at 320×240
        winsize    = 13,    # slightly smaller window at lower res
        iterations = 2,     # reduced from 3 — still stable at 320×240
        poly_n     = 5,     # neighbourhood size for polynomial expansion
        poly_sigma = 1.1,   # Gaussian std for polynomial fit
        flags      = 0,
    )

    def __init__(self, downsample_res: tuple = (320, 240), frame_skip: int = 2):
        """
        Parameters
        ----------
        downsample_res : (width, height) to run optical flow at.
                         Default (320, 240) = 4× fewer pixels than 640×480.
        frame_skip     : compute flow only every N frames; return cached result
                         on skipped frames. 1 = every frame, 2 = every other, etc.
        """
        self.prev_gray      = None
        self.downsample_res = downsample_res
        self.frame_skip     = max(1, frame_skip)
        self._frame_count   = 0
        self._cached_metrics = self._zero_metrics()
        self._cached_flow_bgr = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, frame):
        """
        Call once per frame (in order).

        Parameters
        ----------
        frame : np.ndarray (H×W×3 BGR) — current camera frame

        Returns
        -------
        metrics : dict with keys:
                    'flow_magnitude'  float  — mean pixel speed (pixels/frame)
                    'divergence'      float  — mean ∇·v across the frame
                    'chaos'           float  — angular std dev (radians, 0–π)
        flow_bgr : np.ndarray (H×W×3) — HSV-encoded flow visualisation
        flow_xy  : tuple (fx, fy) np.ndarrays — raw flow components, or (None, None)
                   on the first frame (no previous frame to compare against)
        """
        self._frame_count += 1

        # ---- Downsample to reduce Farneback cost by 4x ------------------
        small = cv2.resize(frame, self.downsample_res, interpolation=cv2.INTER_AREA)
        gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # ---- Frame-skip: return cached result on non-compute frames ------
        if self._frame_count % self.frame_skip != 0:
            blank = self._cached_flow_bgr if self._cached_flow_bgr is not None \
                    else np.zeros((*frame.shape[:2], 3), dtype=np.uint8)
            return self._cached_metrics, blank, (None, None)

        # First frame — no flow yet
        if self.prev_gray is None:
            self.prev_gray = gray
            blank = np.zeros((*frame.shape[:2], 3), dtype=np.uint8)
            self._cached_flow_bgr = blank
            return self._zero_metrics(), blank, (None, None)

        # ---- Farneback dense optical flow (on downsampled frame) ---------
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, gray, None, **self.FB_PARAMS
        )
        self.prev_gray = gray

        fx = flow[..., 0]   # horizontal component
        fy = flow[..., 1]   # vertical  component

        # ---- Metric 1: Mean flow magnitude (speed) -----------------------
        magnitude = np.sqrt(fx ** 2 + fy ** 2)
        flow_magnitude = float(np.mean(magnitude))

        # ---- Metric 2: Divergence  ∇·v ≈ ∂fx/∂x + ∂fy/∂y ---------------
        # Fast finite-difference approximation — avoids the full np.gradient
        # which allocates two large temporary arrays at full resolution.
        dfx_dx = fx[:, 1:] - fx[:, :-1]    # shape (H, W-1)
        dfy_dy = fy[1:, :] - fy[:-1, :]    # shape (H-1, W)
        divergence = float(np.mean(dfx_dx)) + float(np.mean(dfy_dy))

        # ---- Metric 3: Chaos — angular std dev ---------------------------
        angles = np.arctan2(fy, fx)
        chaos  = float(np.std(angles))

        metrics = {
            "flow_magnitude": flow_magnitude,
            "divergence":     divergence,
            "chaos":          chaos,
        }

        # ---- Visualisation (upscale back to original frame size) ---------
        flow_bgr = self._flow_to_bgr(magnitude, angles)
        flow_bgr = cv2.resize(flow_bgr, (frame.shape[1], frame.shape[0]),
                              interpolation=cv2.INTER_LINEAR)

        # Cache for frame-skip frames
        self._cached_metrics  = metrics
        self._cached_flow_bgr = flow_bgr

        return metrics, flow_bgr, (fx, fy)

    def reset(self):
        """Call this if the video source changes (e.g. camera reconnect)."""
        self.prev_gray       = None
        self._frame_count    = 0
        self._cached_metrics = self._zero_metrics()
        self._cached_flow_bgr = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _flow_to_bgr(self, magnitude, angles):
        """
        Encodes flow as an HSV image:
          Hue        → direction (angle)
          Saturation → full (255)
          Value      → speed (magnitude), normalised
        Then converts to BGR for display.
        """
        hsv = np.zeros((*magnitude.shape, 3), dtype=np.uint8)

        # Hue: angle mapped from (−π, π) → (0, 180) for OpenCV HSV
        hsv[..., 0] = ((angles + np.pi) / (2 * np.pi) * 180).astype(np.uint8)
        hsv[..., 1] = 255   # full saturation
        # Value: normalise magnitude to 0–255
        norm_mag = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX)
        hsv[..., 2] = norm_mag.astype(np.uint8)

        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    @staticmethod
    def _zero_metrics():
        return {"flow_magnitude": 0.0, "divergence": 0.0, "chaos": 0.0}

    def overlay(self, frame, flow_bgr, metrics, alpha=0.35):
        """
        Blends the HSV flow visualisation onto the frame and prints metrics.
        Returns the annotated frame.
        """
        vis = cv2.addWeighted(frame, 1 - alpha, flow_bgr, alpha, 0)

        return vis


# ------------------------------------------------------------------
# Quick standalone test
# ------------------------------------------------------------------
if __name__ == "__main__":
    from detector import PersonDetector

    analyser = OpticalFlowAnalyser()
    detector = PersonDetector("config.yaml")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam.")
        exit(1)

    print("[INFO] Optical flow running — move around — press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Phase 1
        centroids, boxes = detector.detect(frame)

        # Phase 2B — optical flow
        metrics, flow_bgr, _ = analyser.compute(frame)

        vis = detector.draw_detections(frame, centroids, boxes)
        vis = analyser.overlay(vis, flow_bgr, metrics)

        print(
            f"[FLOW] speed={metrics['flow_magnitude']:.3f}  "
            f"div={metrics['divergence']:.4f}  "
            f"chaos={metrics['chaos']:.3f}"
        )

        cv2.imshow("Optical Flow", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
