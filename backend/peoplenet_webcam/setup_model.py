"""
setup_model.py
==============
One-time helper: creates a symbolic link (or hard-copy) of
resnet34_peoplenet.onnx into this folder so the webcam script
can find it automatically.

Run once from inside the peoplenet_webcam folder:
    python setup_model.py
"""

import os
import shutil
import sys
from pathlib import Path


# ── Expected location of the model in the MAINEL project ─────────────────────
HERE        = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SOURCE_MODEL = PROJECT_ROOT / "backend" / "model_weights" / "resnet34_peoplenet.onnx"
DEST_MODEL   = HERE / "resnet34_peoplenet.onnx"


def main():
    if DEST_MODEL.exists():
        print(f"[setup] Model already present: {DEST_MODEL}")
        return

    if not SOURCE_MODEL.exists():
        print(f"[setup] ERROR: Source model not found at:\n  {SOURCE_MODEL}")
        print("\n[setup] Please manually copy/move resnet34_peoplenet.onnx")
        print(f"        into: {HERE}")
        sys.exit(1)

    # ── Try symbolic link first (saves disk space) ────────────────────────────
    try:
        os.symlink(SOURCE_MODEL, DEST_MODEL)
        print(f"[setup] Created symlink:\n  {DEST_MODEL}  ->  {SOURCE_MODEL}")
    except (OSError, NotImplementedError):
        # Symlinks may require elevated privileges on Windows — fall back to copy
        print(f"[setup] Symlink failed (probably needs admin). Copying instead …")
        shutil.copy2(SOURCE_MODEL, DEST_MODEL)
        print(f"[setup] Copied {SOURCE_MODEL.stat().st_size / 1e6:.1f} MB "
              f"→ {DEST_MODEL}")

    print("\n[setup] Done! You can now run:")
    print("        python webcam_peoplenet.py")


if __name__ == "__main__":
    main()
