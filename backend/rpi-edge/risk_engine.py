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
        self.smoothing_alpha    = cfg.get("smoothing_alpha", 0.2)
        self.hysteresis_margin  = cfg.get("hysteresis_margin", 0.05)
        self.actuator_cooldown_s = cfg.get("actuator_cooldown_s", 5.0)

        # Sliding window of (timestamp_ms, smoothed_risk) tuples
        self._window: deque = deque(maxlen=self.window_size)
        
        # State variables for smoothing, hysteresis and debouncing
        self.smoothed_risk = None
        self.current_level = "SAFE"
        self.current_command = "GATE_OPEN"
        self.last_actuation_time = 0.0

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

        # ---- Exponential Moving Average (EMA) Smoothing --------------------
        if self.smoothed_risk is None:
            self.smoothed_risk = risk_score
        else:
            self.smoothed_risk = self.smoothing_alpha * risk_score + (1.0 - self.smoothing_alpha) * self.smoothed_risk
        
        self.smoothed_risk = clamp(self.smoothed_risk)

        # ---- Sliding window + trend (linear regression slope) --------------
        now = timestamp_ms()
        self._window.append((now, self.smoothed_risk))
        trend, time_to_critical = self._compute_trend(self.smoothed_risk)

        # ---- Alert level + gate command ------------------------------------
        alert_level, gate_command, alert_message = self._classify(self.smoothed_risk, trend, time_to_critical, now)

        return {
            "risk_score":            round(risk_score, 4),
            "smoothed_risk":         round(self.smoothed_risk, 4),
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

        # Prevent singular matrix error (SVD division by zero) if all timestamps are identical
        if times[-1] == times[0]:
            return 0.0, None

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

    def _classify(self, risk_score: float, slope: float, ttc, now: int):
        """
        Maps risk score to alert level, gate command, and human-readable message,
        using hysteresis and time-based debouncing to prevent rapid switching.
        """
        # 1. Determine the raw target level based on thresholds and hysteresis
        target_level = self.current_level
        
        if self.current_level == "CRITICAL":
            # Must drop well below critical threshold to downgrade
            if risk_score < (self.critical_threshold - self.hysteresis_margin):
                if risk_score >= self.warning_threshold:
                    target_level = "WARNING"
                else:
                    target_level = "SAFE"
        elif self.current_level == "WARNING":
            # Can upgrade easily, but must drop well below warning to downgrade
            if risk_score >= self.critical_threshold:
                target_level = "CRITICAL"
            elif risk_score < (self.warning_threshold - self.hysteresis_margin):
                target_level = "SAFE"
        else: # SAFE
            if risk_score >= self.critical_threshold:
                target_level = "CRITICAL"
            elif risk_score >= self.warning_threshold:
                target_level = "WARNING"

        # 2. Time-Based Debouncing (Cooldown) with Safety Override
        # If the level is trying to change, check if we are allowed to
        if target_level != self.current_level:
            time_since_last = (now - self.last_actuation_time) / 1000.0  # ms to s
            
            # Determine if this is an escalation (increase in risk)
            levels = {"SAFE": 0, "WARNING": 1, "CRITICAL": 2}
            is_escalation = levels[target_level] > levels[self.current_level]
            
            # Allow change if it's an escalation (safety override) OR cooldown has passed
            if is_escalation or (time_since_last >= self.actuator_cooldown_s):
                self.current_level = target_level
                self.last_actuation_time = now

        # 3. Generate outputs based on the finalized self.current_level
        if self.current_level == "CRITICAL":
            self.current_command = "GATE_CLOSE"
            msg = f"CRITICAL crowd density. Gate closed." + (f" Time-to-critical: {ttc:.1f}s" if ttc is not None else " Immediately.")
        elif self.current_level == "WARNING":
            self.current_command = "GATE_HALF"
            msg = f"WARNING: Elevated crowd risk. Gate half-open." + (f" Predicted critical in {ttc:.1f}s." if ttc is not None else "")
        else:
            self.current_command = "GATE_OPEN"
            msg = "Crowd density within safe limits. Gate open."

        return self.current_level, self.current_command, msg


# ------------------------------------------------------------------
# Quick standalone test
# ------------------------------------------------------------------
if __name__ == "__main__":
    import time
    engine = RiskEngine("config.yaml")

    print("--- Simulating bouncing density around threshold ---")
    # Threshold is 0.45. Let's make density cause risk to bounce around 0.45
    # with a very short interval between updates.
    for density in [3.0, 3.1, 2.9, 3.2, 2.8, 3.3]:
        result = engine.update(
            density=density,
            flow_magnitude=1.0,
            divergence=0.0,
            chaos=0.5,
        )
        print(
            f"density={density:.1f}  RawR={result['risk_score']:.3f}  SmoothR={result['smoothed_risk']:.3f}  "
            f"level={result['alert_level']:8s}  cmd={result['gate_command']:10s}  "
        )
        time.sleep(0.5) # Fast updates

    print("\n--- Simulating cooldown expiry ---")
    time.sleep(5) # Wait for cooldown
    for density in [1.0, 1.0]: # Drop density safely
        result = engine.update(
            density=density,
            flow_magnitude=1.0,
            divergence=0.0,
            chaos=0.5,
        )
        print(
            f"density={density:.1f}  RawR={result['risk_score']:.3f}  SmoothR={result['smoothed_risk']:.3f}  "
            f"level={result['alert_level']:8s}  cmd={result['gate_command']:10s}  "
        )
        time.sleep(0.5)
