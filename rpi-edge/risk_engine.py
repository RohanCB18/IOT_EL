import numpy as np
import yaml
from collections import deque
from utils import timestamp_ms, clamp


# ---------------------------------------------------------------------------
# Empirical normalisation bounds (tuned for 320×240 indoor camera)
# Adjust these after calibration if values consistently exceed bounds.
# ---------------------------------------------------------------------------
_BOUNDS = {
    "density":       (0.0, 6.0),   # persons / m²  — Fruin max ≈ 6
    "flow_magnitude": (0.0, 15.0), # pixels / frame — fast crowd sprint ≈ 15
    "divergence":    (-2.0, 2.0),  # ∇·v  — empirically bounded
    "chaos":         (0.0, np.pi), # σθ   — max possible std of angles
}


def _normalise(value: float, lo: float, hi: float) -> float:
    """Min-max normalise to [0, 1], clamped."""
    if hi == lo:
        return 0.0
    return clamp((value - lo) / (hi - lo))


class RiskEngine:
    """
    Composite crowd-risk scorer.

    Formula (from README):
        R = 0.40·ρ̂  +  0.20·|v̂|  +  0.25·(1 − ∇̂·v)  +  0.15·σ̂θ

    where ρ̂, |v̂|, ∇̂·v, σ̂θ are each normalised to [0, 1].

    The compression term uses (1 − normalised_divergence) so that a
    negative divergence (crowd compressing) raises risk.
    """

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)["risk"]

        self.weights            = cfg["weights"]          # [w_density, w_speed, w_compression, w_chaos]
        self.warning_threshold  = cfg["warning_threshold"]
        self.critical_threshold = cfg["critical_threshold"]
        self.window_size        = cfg["window_size"]

        # Sliding window of (timestamp_ms, risk_score) tuples
        self._window: deque = deque(maxlen=self.window_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, density: float, flow_magnitude: float,
               divergence: float, chaos: float) -> dict:
        """
        Ingest one frame's metrics, compute risk score, trend, and gate command.

        Returns
        -------
        result : dict  — see keys below
        """
        # ---- Normalise each input to [0, 1] --------------------------------
        rho_hat  = _normalise(density,        *_BOUNDS["density"])
        v_hat    = _normalise(flow_magnitude, *_BOUNDS["flow_magnitude"])
        div_hat  = _normalise(divergence,     *_BOUNDS["divergence"])
        chaos_hat = _normalise(chaos,         *_BOUNDS["chaos"])

        # Compression component: high when divergence is negative (crowd compressing)
        compression_hat = clamp(1.0 - div_hat)

        # ---- Weighted composite score --------------------------------------
        w = self.weights
        risk_score = (
            w[0] * rho_hat
            + w[1] * v_hat
            + w[2] * compression_hat
            + w[3] * chaos_hat
        )
        risk_score = clamp(risk_score)

        # ---- Sliding window + trend (linear regression slope) --------------
        now = timestamp_ms()
        self._window.append((now, risk_score))
        trend, time_to_critical = self._compute_trend(risk_score)

        # ---- Alert level + gate command ------------------------------------
        alert_level, gate_command, alert_message = self._classify(risk_score, trend, time_to_critical)

        return {
            "risk_score":            round(risk_score, 4),
            "rho_hat":               round(rho_hat, 4),
            "v_hat":                 round(v_hat, 4),
            "compression_hat":       round(compression_hat, 4),
            "chaos_hat":             round(chaos_hat, 4),
            "trend_slope":           round(trend, 6),
            "time_to_critical_s":    round(time_to_critical, 1) if time_to_critical is not None else None,
            "alert_level":           alert_level,
            "gate_command":          gate_command,
            "alert_message":         alert_message,
            "timestamp":             now,
        }

    def reset(self):
        """Clears the sliding window (e.g. when video source changes)."""
        self._window.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_trend(self, current_score: float):
        """
        Fits a linear regression to the risk scores in the sliding window.

        Returns
        -------
        slope              : float — positive = rising risk
        time_to_critical   : float | None — seconds until R crosses 0.75,
                             None if slope ≤ 0 or already critical
        """
        if len(self._window) < 2:
            return 0.0, None

        times  = np.array([t for t, _ in self._window], dtype=np.float64)
        scores = np.array([s for _, s in self._window], dtype=np.float64)

        # Normalise times to seconds relative to window start
        t0     = times[0]
        times  = (times - t0) / 1000.0   # ms → s

        coeffs = np.polyfit(times, scores, 1)
        slope  = float(coeffs[0])        # risk units per second

        if slope > 0 and current_score < self.critical_threshold:
            time_to_critical = (self.critical_threshold - current_score) / slope
        else:
            time_to_critical = None

        return slope, time_to_critical

    def _classify(self, risk_score: float, slope: float, ttc):
        """
        Maps risk score to alert level, gate command, and human-readable message.

        Alert levels  : SAFE | WARNING | CRITICAL
        Gate commands : GATE_OPEN | GATE_HALF | GATE_CLOSE
        """
        if risk_score >= self.critical_threshold:
            level   = "CRITICAL"
            command = "GATE_CLOSE"
            if ttc is not None:
                msg = f"CRITICAL crowd density. Gate closed. Time-to-critical: {ttc:.1f}s"
            else:
                msg = "CRITICAL crowd density. Gate closed immediately."
        elif risk_score >= self.warning_threshold:
            level   = "WARNING"
            command = "GATE_HALF"
            if ttc is not None:
                msg = f"WARNING: Rising crowd risk. Gate half-open. Predicted critical in {ttc:.1f}s."
            else:
                msg = "WARNING: Elevated crowd risk. Gate set to half-open."
        else:
            level   = "SAFE"
            command = "GATE_OPEN"
            msg     = "Crowd density within safe limits. Gate open."

        return level, command, msg


# ------------------------------------------------------------------
# Quick standalone test
# ------------------------------------------------------------------
if __name__ == "__main__":
    engine = RiskEngine("config.yaml")

    print("--- Simulating increasing density ---")
    for density in [0.5, 1.0, 2.0, 3.5, 4.5, 5.5, 6.0]:
        result = engine.update(
            density=density,
            flow_magnitude=2.0,
            divergence=-0.5,
            chaos=1.2,
        )
        print(
            f"density={density:.1f}  R={result['risk_score']:.3f}  "
            f"level={result['alert_level']:8s}  cmd={result['gate_command']:10s}  "
            f"slope={result['trend_slope']:+.4f}  ttc={result['time_to_critical_s']}"
        )
