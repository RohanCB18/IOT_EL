import numpy as np
import cv2
import yaml
from sklearn.cluster import DBSCAN



class DensityMapper:
    """
    Takes person centroids from the detector and produces:
      1. DBSCAN cluster labels (which person belongs to which cluster)
      2. A Gaussian heatmap overlaid on the frame
      3. A density value in persons/m²
    """

    # Fruin Level-of-Service thresholds (persons/m²)
    # These are internationally recognised crowd safety standards
    LOS_SAFE     = 2.0   # < 2.0  → Safe (green)
    LOS_CAUTION  = 3.5   # 2.0–3.5 → Caution (yellow)
    LOS_WARNING  = 5.0   # 3.5–5.0 → Warning (orange)
    # ≥ 5.0 → Critical (red)

    def __init__(self, config_path="config.yaml", profile: str = None):
        with open(config_path, "r") as f:
            full_cfg = yaml.safe_load(f)
            
        if "profiles" in full_cfg:
            p = profile if profile and profile in full_cfg["profiles"] else "0"
            cfg = full_cfg["profiles"][p]["density"]
        else:
            cfg = full_cfg["density"]

        self.eps             = cfg["eps"]             # DBSCAN neighbourhood radius (pixels)
        self.min_samples     = cfg["min_samples"]     # minimum points to form a cluster
        self.pixels_per_meter = cfg["pixels_per_meter"]  # calibration: how many pixels = 1 metre
        self.sigma           = cfg["sigma"]            # Gaussian blur radius for heatmap

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, centroids, frame_shape):
        """
        Main entry point.

        Parameters
        ----------
        centroids   : list of (cx, cy) floats — one per detected person
        frame_shape : (height, width, channels) of the original frame

        Returns
        -------
        density     : float  — persons per m²
        labels      : np.array — DBSCAN cluster label for each centroid (-1 = noise/outlier)
        heatmap_bgr : np.ndarray (H×W×3) — coloured heatmap ready to overlay on the frame
        level       : str — "SAFE" | "CAUTION" | "WARNING" | "CRITICAL"
        """
        h, w = frame_shape[:2]

        if len(centroids) == 0:
            blank = np.zeros((h, w, 3), dtype=np.uint8)
            return 0.0, np.array([]), blank, "SAFE"

        pts = np.array(centroids, dtype=np.float32)

        # ---- 1. DBSCAN clustering ----------------------------------------
        # eps: if two centroids are within `eps` pixels they are neighbours
        # min_samples: a cluster needs at least this many points
        labels = DBSCAN(eps=self.eps, min_samples=self.min_samples).fit_predict(pts)

        # ---- 2. Density calculation ----------------------------------------
        # Convert pixel area to real-world area using the calibration factor
        area_m2 = (w * h) / (self.pixels_per_meter ** 2)
        density  = len(centroids) / area_m2   # persons per m²

        # ---- 3. Fruin Level-of-Service classification ----------------------
        level = self._classify(density)

        # ---- 4. Gaussian heatmap -------------------------------------------
        heatmap_bgr = self._build_heatmap(pts, h, w)

        return density, labels, heatmap_bgr, level

    def overlay(self, frame, heatmap_bgr, labels, centroids, density, level, alpha=0.45):
        """
        Blends the heatmap onto the frame and annotates cluster IDs,
        density value, and Level-of-Service.

        Draws in-place on *frame* for speed (the caller passes a vis copy).
        """
        # Blend heatmap in-place
        vis = cv2.addWeighted(frame, 1 - alpha, heatmap_bgr, alpha, 0)

        # Draw cluster labels next to each centroid (only for clustered people, skipping noise to avoid clutter)
        for i, (cx, cy) in enumerate(centroids):
            lbl = labels[i] if len(labels) > i else -1
            if lbl >= 0:
                colour = (0, 255, 255)  # Cyan for active cluster identifiers
                tag    = f"C{lbl}"
                cv2.putText(vis, tag, (int(cx) + 5, int(cy) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, colour, 1, cv2.LINE_AA)

        return vis

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_heatmap(self, pts, h, w):
        """
        Splats each centroid onto a quarter-resolution canvas, applies
        cv2.GaussianBlur (SIMD-optimised C++, ~2–5× faster than scipy),
        then upscales and applies COLORMAP_JET.

        Downsampling before the blur gives ~16× fewer pixels to process
        with negligible visual difference on a heatmap.
        """
        # Quarter resolution for the blur pass
        sh, sw = h // 4, w // 4
        canvas = np.zeros((sh, sw), dtype=np.float32)

        # Scale centroids to quarter-res and splat
        sx = sw / w
        sy = sh / h
        for cx, cy in pts:
            ix = int(np.clip(cx * sx, 0, sw - 1))
            iy = int(np.clip(cy * sy, 0, sh - 1))
            canvas[iy, ix] += 1.0

        # cv2.GaussianBlur: ksize=(0,0) auto-computes from sigma.
        # sigma is scaled to quarter-res.
        small_sigma = max(1.0, self.sigma / 4.0)
        # ksize must be odd; derive from sigma
        ksize = int(6 * small_sigma) | 1   # ensure odd
        blurred = cv2.GaussianBlur(canvas, (ksize, ksize), small_sigma)

        # Normalise to 0–255 for colourmap
        bmax = blurred.max()
        if bmax > 0:
            blurred = (blurred * (255.0 / bmax)).astype(np.uint8)
        else:
            blurred = blurred.astype(np.uint8)

        # Upscale back to original frame size
        blurred = cv2.resize(blurred, (w, h), interpolation=cv2.INTER_LINEAR)

        # Apply JET colour map: blue=sparse, red=dense
        heatmap_bgr = cv2.applyColorMap(blurred, cv2.COLORMAP_JET)
        return heatmap_bgr

    def _classify(self, density):
        if density < self.LOS_SAFE:
            return "SAFE"
        elif density < self.LOS_CAUTION:
            return "CAUTION"
        elif density < self.LOS_WARNING:
            return "WARNING"
        else:
            return "CRITICAL"

    def _level_colour(self, level):
        """Returns BGR colour for the LoS level."""
        return {
            "SAFE":     (0, 220, 0),
            "CAUTION":  (0, 220, 220),
            "WARNING":  (0, 140, 255),
            "CRITICAL": (0, 0, 255),
        }.get(level, (255, 255, 255))


# ------------------------------------------------------------------
# Quick standalone test
# ------------------------------------------------------------------
if __name__ == "__main__":
    from detector import PersonDetector

    detector = PersonDetector("config.yaml")
    mapper   = DensityMapper("config.yaml")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam.")
        exit(1)

    print("[INFO] Density mapper running — press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        centroids, boxes = detector.detect(frame)
        density, labels, heatmap_bgr, level = mapper.compute(centroids, frame.shape)

        # Draw bounding boxes from Phase 1
        vis = detector.draw_detections(frame, centroids, boxes)
        # Overlay heatmap + density info from Phase 2
        vis = mapper.overlay(vis, heatmap_bgr, labels, centroids, density, level)

        cv2.putText(vis, f"People: {len(centroids)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        print(f"[DENSITY] {density:.2f} p/m²  |  Level: {level}  |  Count: {len(centroids)}")

        cv2.imshow("Density Mapper", vis)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
