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
"""

import numpy as np

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

    detections = []

    for c in analysis_classes:
        cov = output_cov[0, c]           # (GRID_H, GRID_W)
        mask = cov >= min_confidence

        if not np.any(mask):
            continue

        # Raw bbox offsets for this class
        o1 = output_bbox[0, c * 4 + 0]  # x1 channel
        o2 = output_bbox[0, c * 4 + 1]  # y1 channel
        o3 = output_bbox[0, c * 4 + 2]  # x2 channel
        o4 = output_bbox[0, c * 4 + 3]  # y2 channel

        # Apply NVIDIA's box-norm formula  (vectorised, model-space pixels)
        x1 = (o1 - GC_W) * -BOX_NORM
        y1 = (o2 - GC_H) * -BOX_NORM
        x2 = (o3 + GC_W) *  BOX_NORM
        y2 = (o4 + GC_H) *  BOX_NORM

        # Scale to original image space
        x1 *= scale_x;  x2 *= scale_x
        y1 *= scale_y;  y2 *= scale_y

        # Extract valid boxes
        vx1 = x1[mask];  vy1 = y1[mask]
        vx2 = x2[mask];  vy2 = y2[mask]
        vc  = cov[mask]

        for i in range(len(vx1)):
            if vx2[i] > vx1[i] and vy2[i] > vy1[i]:
                detections.append({
                    'x1':        float(vx1[i]),
                    'y1':        float(vy1[i]),
                    'x2':        float(vx2[i]),
                    'y2':        float(vy2[i]),
                    'confidence': float(vc[i]),
                    'class_id':  c,
                })

    return detections


def nms(detections: list, iou_threshold: float = 0.5) -> list:
    """
    Per-class Non-Maximum Suppression.

    Parameters
    ----------
    detections    : list of detection dicts (with 'x1','y1','x2','y2','confidence','class_id')
    iou_threshold : overlap threshold; boxes above this are suppressed

    Returns
    -------
    Filtered list sorted by confidence descending.
    """
    if not detections:
        return []

    boxes     = np.array([[d['x1'], d['y1'], d['x2'], d['y2']] for d in detections], dtype=np.float32)
    scores    = np.array([d['confidence']  for d in detections], dtype=np.float32)
    class_ids = np.array([d['class_id']   for d in detections], dtype=np.int32)

    keep = []
    for c in np.unique(class_ids):
        idx = np.where(class_ids == c)[0]
        cb  = boxes[idx]
        cs  = scores[idx]

        order = np.argsort(-cs)
        kept  = []

        while len(order):
            i = order[0]
            kept.append(idx[i])

            if len(order) == 1:
                break

            # IOU with remaining boxes
            xx1 = np.maximum(cb[i, 0], cb[order[1:], 0])
            yy1 = np.maximum(cb[i, 1], cb[order[1:], 1])
            xx2 = np.minimum(cb[i, 2], cb[order[1:], 2])
            yy2 = np.minimum(cb[i, 3], cb[order[1:], 3])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h

            area_i  = (cb[i,  2] - cb[i,  0]) * (cb[i,  3] - cb[i,  1])
            area_r  = (cb[order[1:], 2] - cb[order[1:], 0]) * \
                      (cb[order[1:], 3] - cb[order[1:], 1])
            iou = inter / (area_i + area_r - inter + 1e-6)

            order = order[np.where(iou <= iou_threshold)[0] + 1]

        keep.extend(kept)

    keep = sorted(keep, key=lambda i: detections[i]['confidence'], reverse=True)
    return [detections[i] for i in keep]
