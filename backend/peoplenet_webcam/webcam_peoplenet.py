"""
webcam_peoplenet.py
===================
Real-time webcam detection with NVIDIA PeopleNet (ResNet-34 ONNX).

Detects and draws bounding boxes around:
  • Person  (green)
  • Bag     (blue)
  • Face / Head  (red)

Usage
-----
  # Basic (uses webcam 0, CPU inference, model next to this script)
  python webcam_peoplenet.py

  # Custom model path + CUDA
  python webcam_peoplenet.py --model path/to/resnet34_peoplenet.onnx --device cuda

  # Persons + faces only, stricter threshold
  python webcam_peoplenet.py --classes person face --threshold 0.45

  # Save output to video file
  python webcam_peoplenet.py --save-video output.mp4

  # Use camera index 1
  python webcam_peoplenet.py --camera 1

Keyboard shortcuts during playback
-----------------------------------
  q  – quit
  p  – pause / resume
  s  – save current frame as PNG
  +  – raise confidence threshold by 0.05
  -  – lower confidence threshold by 0.05
"""

import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np

# ── Local imports ─────────────────────────────────────────────────────────────
# Both files must be in the same directory as this script.
from peoplenet_detector import PeopleNetDetector


# ─────────────────────────────────────────────────────────────────────────────
#  HUD / overlay helpers
# ─────────────────────────────────────────────────────────────────────────────

FONT         = cv2.FONT_HERSHEY_SIMPLEX
COLOR_HUD    = (0, 255, 180)    # cyan-green
COLOR_WARN   = (0, 80, 255)     # orange-red
COLOR_WHITE  = (255, 255, 255)


def draw_hud(
    frame:          np.ndarray,
    fps:            float,
    inference_ms:   float,
    det_counts:     dict,
    threshold:      float,
    paused:         bool,
    device:         str,
) -> None:
    """Overlay a semi-transparent HUD panel in the top-left corner."""
    h, w = frame.shape[:2]

    # ── Semi-transparent dark rectangle ──────────────────────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (340, 175), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    lines = [
        f"FPS: {fps:5.1f}   Infer: {inference_ms:5.1f} ms",
        f"Device : {device.upper()}",
        f"Threshold: {threshold:.2f}   {'[PAUSED]' if paused else ''}",
        "─" * 36,
        f"Persons : {det_counts.get('person', 0):3d}",
        f"Faces   : {det_counts.get('face',   0):3d}",
        f"Bags    : {det_counts.get('bag',     0):3d}",
        "─" * 36,
        "q=quit  p=pause  s=save  +/-=threshold",
    ]

    for i, line in enumerate(lines):
        color = COLOR_WARN if paused and i == 2 else COLOR_HUD
        cv2.putText(frame, line, (8, 22 + i * 20),
                    FONT, 0.46, color, 1, cv2.LINE_AA)


def draw_crosshair(frame: np.ndarray) -> None:
    """Draw a faint centre crosshair."""
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    cv2.line(frame, (cx - 15, cy), (cx + 15, cy), (80, 80, 80), 1, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - 15), (cx, cy + 15), (80, 80, 80), 1, cv2.LINE_AA)


def count_by_class(detections: list) -> dict:
    counts: dict = {}
    for d in detections:
        cn = d.get('class_name', 'unknown')
        counts[cn] = counts.get(cn, 0) + 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────────────────────────

def run_webcam(
    model_path:   str,
    camera_index: int   = 0,
    device:       str   = 'cpu',
    threshold:    float = 0.40,
    nms_thresh:   float = 0.50,
    classes:      list  = None,      # None → detect all
    save_video:   str   = None,
    width:        int   = 1280,
    height:       int   = 720,
) -> None:
    """
    Main webcam loop.

    Parameters
    ----------
    model_path   : path to resnet34_peoplenet.onnx
    camera_index : OpenCV camera index (0, 1, …)
    device       : 'cuda' or 'cpu'
    threshold    : initial confidence threshold
    nms_thresh   : NMS IoU threshold
    classes      : list of class names to detect, or None for all
    save_video   : if given, write annotated frames to this mp4 path
    width/height : requested capture resolution
    """
    print("\n" + "=" * 60)
    print("  NVIDIA PeopleNet  —  Webcam Detection")
    print("=" * 60)

    # ── Initialise detector ───────────────────────────────────────────────────
    detector = PeopleNetDetector(
        model_path           = model_path,
        device               = device,
        confidence_threshold = threshold,
        nms_threshold        = nms_thresh,
    )

    # ── Open webcam ───────────────────────────────────────────────────────────
    print(f"\n[Webcam] Opening camera {camera_index} …")
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)   # CAP_DSHOW is faster on Windows
    if not cap.isOpened():
        # Fallback without backend hint
        cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[Webcam] ERROR: Cannot open camera {camera_index}")
        print("         → Make sure no other app is using the camera.")
        print("         → Try --camera 1 or --camera 2")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS,          30)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[Webcam] Capture resolution : {actual_w} × {actual_h}")
    print("[Webcam] Controls : q=quit | p=pause | s=save-frame | +/-=threshold\n")

    # ── Optional video writer ─────────────────────────────────────────────────
    writer = None
    if save_video:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(save_video, fourcc, 30, (actual_w, actual_h))
        print(f"[Webcam] Saving to: {save_video}")

    # ── Runtime state ─────────────────────────────────────────────────────────
    paused         = False
    frame_count    = 0
    fps_display    = 0.0
    inference_ms   = 0.0
    last_fps_time  = time.time()
    frame_times:   list = []
    last_frame     = None    # used when paused
    last_dets:     list = []

    try:
        while True:
            # ── Key handling ──────────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print("\n[Webcam] Quit by user.")
                break

            elif key == ord('p'):
                paused = not paused
                state  = "PAUSED" if paused else "RESUMED"
                print(f"[Webcam] {state}")

            elif key == ord('s') and last_frame is not None:
                ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn  = f"capture_{ts}.png"
                cv2.imwrite(fn, last_frame)
                print(f"[Webcam] Saved frame → {fn}")

            elif key == ord('+') or key == ord('='):
                threshold = min(0.95, round(threshold + 0.05, 2))
                detector.confidence_threshold = threshold
                print(f"[Webcam] Threshold → {threshold:.2f}")

            elif key == ord('-'):
                threshold = max(0.05, round(threshold - 0.05, 2))
                detector.confidence_threshold = threshold
                print(f"[Webcam] Threshold → {threshold:.2f}")

            # ── Paused mode — re-display last frame ───────────────────────────
            if paused:
                if last_frame is not None:
                    vis = last_frame.copy()
                    draw_hud(vis, fps_display, inference_ms,
                             count_by_class(last_dets), threshold, True, device)
                    cv2.putText(vis, "▌▌  PAUSED",
                                (actual_w // 2 - 90, actual_h // 2),
                                FONT, 1.2, COLOR_WARN, 2, cv2.LINE_AA)
                    cv2.imshow("PeopleNet  |  q=quit  p=pause  s=save", vis)
                continue

            # ── Read frame ────────────────────────────────────────────────────
            ret, frame = cap.read()
            if not ret:
                print("[Webcam] Frame read failed.")
                break

            # ── Inference ─────────────────────────────────────────────────────
            t0 = time.perf_counter()
            detections = detector.detect(
                frame,
                confidence_threshold = threshold,
                classes              = classes,
            )
            inference_ms = (time.perf_counter() - t0) * 1000
            frame_times.append(inference_ms)

            # ── Visualise ─────────────────────────────────────────────────────
            vis = detector.visualize(frame, detections, show_labels=True, show_confidence=True)
            draw_crosshair(vis)

            # ── FPS counter (updated every 0.5 s) ─────────────────────────────
            now = time.perf_counter()
            if now - last_fps_time >= 0.5 and frame_times:
                recent = frame_times[-20:]
                fps_display = 1000.0 / (sum(recent) / len(recent))
                last_fps_time = now

            draw_hud(vis, fps_display, inference_ms,
                     count_by_class(detections), threshold, False, device)

            # ── Save & display ────────────────────────────────────────────────
            last_frame = vis
            last_dets  = detections

            if writer:
                writer.write(vis)

            cv2.imshow("PeopleNet  |  q=quit  p=pause  s=save", vis)

            frame_count += 1

            # Progress log every 150 frames
            if frame_count % 150 == 0:
                avg = sum(frame_times[-150:]) / len(frame_times[-150:])
                print(f"[Webcam] Frame {frame_count:6d} | "
                      f"avg infer {avg:.1f} ms | "
                      f"FPS {1000/avg:.1f} | "
                      f"detections {len(detections)}")

    except KeyboardInterrupt:
        print("\n[Webcam] Interrupted.")

    finally:
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()

        # ── Summary ───────────────────────────────────────────────────────────
        if frame_times:
            avg = sum(frame_times) / len(frame_times)
            print(f"\n{'='*60}")
            print(f"  Session summary")
            print(f"{'='*60}")
            print(f"  Frames processed  : {frame_count}")
            print(f"  Avg inference     : {avg:.1f} ms")
            print(f"  Avg FPS           : {1000/avg:.1f}")
            if save_video:
                print(f"  Video saved to    : {save_video}")
            print(f"{'='*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

def _default_model_path() -> str:
    """
    Walk up from this script's directory to find the model.
    Checks:
      1.  ./resnet34_peoplenet.onnx         (next to this script)
      2.  ./models/resnet34_peoplenet.onnx
      3.  ../backend/model_weights/resnet34_peoplenet.onnx  (project layout)
    """
    here = Path(__file__).resolve().parent
    candidates = [
        here / "resnet34_peoplenet.onnx",
        here / "models" / "resnet34_peoplenet.onnx",
        here.parent / "backend" / "model_weights" / "resnet34_peoplenet.onnx",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # Return default even if not found — the script will raise a clear error
    return str(here / "resnet34_peoplenet.onnx")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Real-time PeopleNet detection from webcam",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model", "-m",
        default=_default_model_path(),
        help="Path to resnet34_peoplenet.onnx (auto-detected if omitted)",
    )
    parser.add_argument(
        "--camera", "-c",
        type=int, default=0,
        help="Webcam index (default: 0)",
    )
    parser.add_argument(
        "--device", "-d",
        choices=["cpu", "cuda"], default="cpu",
        help="Inference device (default: cpu)",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float, default=0.40,
        help="Initial confidence threshold 0–1 (default: 0.40)",
    )
    parser.add_argument(
        "--nms", type=float, default=0.50,
        help="NMS IoU threshold (default: 0.50)",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        choices=["person", "bag", "face"],
        default=None,
        help="Classes to detect (default: all three)",
    )
    parser.add_argument(
        "--save-video", "-s",
        default=None, metavar="PATH",
        help="Save annotated video to this .mp4 path",
    )
    parser.add_argument(
        "--width",  type=int, default=1280,
        help="Requested capture width  (default: 1280)",
    )
    parser.add_argument(
        "--height", type=int, default=720,
        help="Requested capture height (default:  720)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print(f"[Config] Model     : {args.model}")
    print(f"[Config] Camera    : {args.camera}")
    print(f"[Config] Device    : {args.device}")
    print(f"[Config] Threshold : {args.threshold}")
    print(f"[Config] Classes   : {args.classes or 'all (person, bag, face)'}")

    run_webcam(
        model_path   = args.model,
        camera_index = args.camera,
        device       = args.device,
        threshold    = args.threshold,
        nms_thresh   = args.nms,
        classes      = args.classes,
        save_video   = args.save_video,
        width        = args.width,
        height       = args.height,
    )
