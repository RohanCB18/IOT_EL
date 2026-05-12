import numpy as np
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
    """

    # Farneback parameters (tuned for 320×240 at 3–10 FPS)
    FB_PARAMS = dict(
        pyr_scale  = 0.5,   # each pyramid level shrinks by half
        levels     = 3,     # number of pyramid levels
        winsize    = 15,    # averaging window — larger = smoother but less detail
        iterations = 3,     # iterations per pyramid level
        poly_n     = 5,     # neighbourhood size for polynomial expansion
        poly_sigma = 1.2,   # Gaussian std for smoothing before polynomial fit
        flags      = 0,
    )

    def __init__(self):
        self.prev_gray = None   # stores the previous frame (greyscale)

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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # First frame — no flow yet
        if self.prev_gray is None:
            self.prev_gray = gray
            blank = np.zeros_like(frame)
            return self._zero_metrics(), blank, (None, None)

        # ---- Farneback dense optical flow --------------------------------
        # Returns a 2-channel array: flow[y, x, 0]=fx, flow[y, x, 1]=fy
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, gray, None, **self.FB_PARAMS
        )
        self.prev_gray = gray

        fx = flow[..., 0]   # horizontal component
        fy = flow[..., 1]   # vertical  component

        # ---- Metric 1: Mean flow magnitude (speed) -----------------------
        magnitude = np.sqrt(fx ** 2 + fy ** 2)
        flow_magnitude = float(np.mean(magnitude))

        # ---- Metric 2: Divergence  ∇·v = ∂fx/∂x + ∂fy/∂y ---------------
        # np.gradient returns the discrete derivative along each axis
        dfx_dx = np.gradient(fx, axis=1)   # ∂fx/∂x
        dfy_dy = np.gradient(fy, axis=0)   # ∂fy/∂y
        div_field = dfx_dx + dfy_dy
        divergence = float(np.mean(div_field))

        # ---- Metric 3: Chaos — angular std dev ---------------------------
        # arctan2 gives the angle of each flow vector (−π … +π)
        angles = np.arctan2(fy, fx)
        chaos  = float(np.std(angles))

        metrics = {
            "flow_magnitude": flow_magnitude,
            "divergence":     divergence,
            "chaos":          chaos,
        }

        # ---- Visualisation -----------------------------------------------
        flow_bgr = self._flow_to_bgr(magnitude, angles)

        return metrics, flow_bgr, (fx, fy)

    def reset(self):
        """Call this if the video source changes (e.g. camera reconnect)."""
        self.prev_gray = None

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

        y = 90
        for key, val in metrics.items():
            cv2.putText(vis, f"{key}: {val:.3f}", (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 50), 1)
            y += 22

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
