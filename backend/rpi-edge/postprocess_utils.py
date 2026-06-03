"""
postprocess_utils.py
====================
DetectNet_v2 post-processing for NVIDIA PeopleNet (ResNet-34 ONNX).

The raw model outputs two tensors per frame:
  - output_cov  : (1, 3, 34, 60)  — confidence/coverage per grid cell per class
  - output_bbox : (1, 12, 34, 60) — raw bounding-box offsets per grid cell per class

Grid parameters come from the model's fixed input resolution (960 x 544)
and stride (16).  The box normalisation formula is from the official
NVIDIA developer forum:
https://forums.developer.nvidia.com/t/run-peoplenet-with-tensorrt/128000/22

Classes detected (in order): person, bag, face

Performance notes
-----------------
• nms() uses cv2.dnn.NMSBoxes — a vectorised C++ implementation — instead of
  the previous Python while-loop which was O(N²) and slow on dense crowds.
• postprocess_detectnet_vectorized() now builds the detection list with a
  fully vectorised numpy path, avoiding the per-element Python dict loop.
"""

import numpy as np
import cv2

# ─── Model / grid constants ─────────────────────────────────────────────────
MODEL_W  = 960
MODEL_H  = 544
STRIDE   = 16
BOX_NORM = 35.0

GRID_W = MODEL_W // STRIDE   # 60
GRID_H = MODEL_H // STRIDE   # 34

# Precompute grid-cell centre coordinates (normalised by BOX_NORM)
GRID_CENTERS_W = np.array([(i * STRIDE + 0.5) / BOX_NORM for i in range(GRID_W)], dtype=np.float32)
GRID_CENTERS_H = np.array([(i * STRIDE + 0.5) / BOX_NORM for i in range(GRID_H)], dtype=np.float32)

# Broadcast-ready 2-D grids  (GRID_H, GRID_W)
GC_W, GC_H = np.meshgrid(GRID_CENTERS_W, GRID_CENTERS_H)   # both (34, 60)
# ────────────────────────────────────────────────────────────────────────────


def postprocess_detectnet_vectorized(
    output_bbox:       np.ndarray,
    output_cov:        np.ndarray,
    num_classes:       int   = 3,
    min_confidence:    float = 0.4,
    analysis_classes:  list  = None,
    orig_width:        int   = None,
    orig_height:       int   = None,
) -> list:
    """
    Vectorised DetectNet_v2 post-processing.

    Parameters
    ----------
    output_bbox      : ndarray (1, num_classes*4, GRID_H, GRID_W)
    output_cov       : ndarray (1, num_classes,   GRID_H, GRID_W)
    num_classes      : number of output classes (3 for PeopleNet)
    min_confidence   : cells below this threshold are discarded
    analysis_classes : list of class indices to decode (None → all)
    orig_width/height: frame dimensions for rescaling boxes back to pixel space

    Returns
    -------
    list of dict  {'x1', 'y1', 'x2', 'y2', 'confidence', 'class_id'}
    """
    if analysis_classes is None:
        analysis_classes = list(range(num_classes))

    scale_x = (orig_width  / MODEL_W) if orig_width  else 1.0
    scale_y = (orig_height / MODEL_H) if orig_height else 1.0

    all_x1  = []
    all_y1  = []
    all_x2  = []
    all_y2  = []
    all_cov = []
    all_cls = []

    for c in analysis_classes:
        cov  = output_cov[0, c]           # (GRID_H, GRID_W)
        mask = cov >= min_confidence

        if not np.any(mask):
            continue

        # Raw bbox offsets for this class
        o1 = output_bbox[0, c * 4 + 0]   # x1 channel
        o2 = output_bbox[0, c * 4 + 1]   # y1 channel
        o3 = output_bbox[0, c * 4 + 2]   # x2 channel
        o4 = output_bbox[0, c * 4 + 3]   # y2 channel

        # Apply NVIDIA's box-norm formula (vectorised, model-space pixels)
        x1 = (o1 - GC_W) * (-BOX_NORM) * scale_x
        y1 = (o2 - GC_H) * (-BOX_NORM) * scale_y
        x2 = (o3 + GC_W) *   BOX_NORM  * scale_x
        y2 = (o4 + GC_H) *   BOX_NORM  * scale_y

        # Keep only valid boxes (x2 > x1 and y2 > y1) — vectorised
        valid = mask & (x2 > x1) & (y2 > y1)
        if not np.any(valid):
            continue

        all_x1.append(x1[valid])
        all_y1.append(y1[valid])
        all_x2.append(x2[valid])
        all_y2.append(y2[valid])
        all_cov.append(cov[valid])
        all_cls.append(np.full(int(np.sum(valid)), c, dtype=np.int32))

    if not all_x1:
        return []

    # Concatenate all classes into flat arrays
    vx1 = np.concatenate(all_x1).astype(np.float32)
    vy1 = np.concatenate(all_y1).astype(np.float32)
    vx2 = np.concatenate(all_x2).astype(np.float32)
    vy2 = np.concatenate(all_y2).astype(np.float32)
    vc  = np.concatenate(all_cov).astype(np.float32)
    vcls = np.concatenate(all_cls)

    # Build output list — still Python dicts but in one vectorised pass
    detections = [
        {
            'x1':        float(vx1[i]),
            'y1':        float(vy1[i]),
            'x2':        float(vx2[i]),
            'y2':        float(vy2[i]),
            'confidence': float(vc[i]),
            'class_id':  int(vcls[i]),
        }
        for i in range(len(vx1))
    ]

    return detections


def nms(detections: list, iou_threshold: float = 0.5) -> list:
    """
    Per-class Non-Maximum Suppression using cv2.dnn.NMSBoxes.

    Replaces the previous Python while-loop implementation with OpenCV's
    vectorised C++ NMS — significantly faster for dense crowds (100+ detections).

    Parameters
    ----------
    detections    : list of detection dicts (with 'x1','y1','x2','y2','confidence','class_id')
    iou_threshold : IoU overlap threshold; boxes above this are suppressed

    Returns
    -------
    Filtered list sorted by confidence descending.
    """
    if not detections:
        return []

    # cv2.dnn.NMSBoxes expects [x, y, w, h] format
    boxes_xywh = [
        [d['x1'], d['y1'], d['x2'] - d['x1'], d['y2'] - d['y1']]
        for d in detections
    ]
    scores    = [d['confidence'] for d in detections]
    class_ids = [d['class_id']  for d in detections]

    keep_indices = []
    for c in set(class_ids):
        # Gather indices for this class
        cls_mask    = [i for i, cid in enumerate(class_ids) if cid == c]
        cls_boxes   = [boxes_xywh[i] for i in cls_mask]
        cls_scores  = [scores[i]     for i in cls_mask]

        # OpenCV NMS — C++ vectorised implementation
        indices = cv2.dnn.NMSBoxes(
            cls_boxes, cls_scores,
            score_threshold = 0.0,        # pre-filtered by confidence already
            nms_threshold   = iou_threshold,
        )

        if len(indices) > 0:
            # cv2.dnn.NMSBoxes returns nested array on older OpenCV; flatten safely
            for idx in np.array(indices).flatten():
                keep_indices.append(cls_mask[int(idx)])

    # Sort by confidence descending
    keep_indices.sort(key=lambda i: detections[i]['confidence'], reverse=True)
    return [detections[i] for i in keep_indices]
