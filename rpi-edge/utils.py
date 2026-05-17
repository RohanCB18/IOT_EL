import base64
import time
import cv2
import numpy as np


def encode_frame_base64(frame: np.ndarray, quality: int = 60) -> str:
    """
    JPEG-encodes a BGR frame and returns a base64 string suitable for MQTT.
    Lower quality reduces payload size for faster transmission.
    """
    ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ret:
        return ""
    return base64.b64encode(buf).decode("utf-8")


def timestamp_ms() -> int:
    """Returns current UTC time as an integer millisecond epoch timestamp."""
    return int(time.time() * 1000)


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamps a float to [lo, hi]."""
    return max(lo, min(hi, value))
