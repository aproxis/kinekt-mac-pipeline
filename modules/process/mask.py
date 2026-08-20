"""Маски: depth → selfie-сегментация → pose-полигон."""
import numpy as np
import cv2

from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import config

# ==== SELFIE SEGMENTATION (webcam fallback маска) ====
segmenter = None
segmenter_init_tried = False


def init_segmenter():
    """Ленивая инициализация — только когда реально нужна (webcam без depth)."""
    global segmenter, segmenter_init_tried
    if segmenter_init_tried:
        return segmenter
    segmenter_init_tried = True
    try:
        seg_opts = vision.ImageSegmenterOptions(
            base_options=mp_python.BaseOptions(model_asset_path=config.SELFIE_MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True,
        )
        segmenter = vision.ImageSegmenter.create_from_options(seg_opts)
        print("Selfie segmentation: загружена (webcam fallback маска)")
    except Exception as e:
        print(f"Selfie segmentation: не удалось загрузить ({e}) — "
              f"используется pose-полигон")
    return segmenter


def make_selfie_mask(h, w, mp_image, timestamp_ms):
    """Пиксельная сегментация человека из RGB. None если модель недоступна."""
    seg = init_segmenter()
    if seg is None:
        return None
    try:
        result = seg.segment_for_video(mp_image, timestamp_ms)
        if not result.confidence_masks:
            return None
        conf = result.confidence_masks[0].numpy_view()   # (H, W) float 0..1
        binary = (conf > config.SELFIE_THRESHOLD).astype(np.uint8) * 255
        if binary.shape != (h, w):
            binary = cv2.resize(binary, (w, h), interpolation=cv2.INTER_NEAREST)
        kernel = np.ones((5, 5), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        return binary
    except Exception:
        return None


def depth_to_display(depth_mm):
    valid = depth_mm.copy()
    valid[valid == 0] = config.DEPTH_MAX_MM
    clipped = np.clip(valid, config.DEPTH_MIN_MM, config.DEPTH_MAX_MM)
    normalized = ((clipped - config.DEPTH_MIN_MM) / (config.DEPTH_MAX_MM - config.DEPTH_MIN_MM) * 255)
    normalized = (255 - normalized).astype(np.uint8)
    return cv2.applyColorMap(normalized, cv2.COLORMAP_JET)


def make_silhouette_mask(depth_mm):
    mask = np.zeros(depth_mm.shape, dtype=np.uint8)
    in_range = (depth_mm > config.DEPTH_MIN_MM) & (depth_mm < config.DEPTH_MAX_MM)
    mask[in_range] = 255
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def make_pose_mask(h, w, pose_results):
    mask = np.zeros((h, w), dtype=np.uint8)
    if not pose_results or not pose_results.pose_landmarks:
        return mask
    for landmarks in pose_results.pose_landmarks:
        pts = {}
        for idx, lm in enumerate(landmarks):
            pts[idx] = (int((1.0 - lm.x) * w), int(lm.y * h))
        contour = [pts[i] for i in config.BODY_OUTLINE_ORDER if i in pts]
        if len(contour) < 3:
            continue
        body = np.array(contour, dtype=np.int32)
        cv2.fillPoly(mask, [body], 255)
        # скелет поверх: тонкие линии, чтобы руки не слипались в один ком
        for a, b in config.POSE_CONNECTIONS:
            if a in pts and b in pts:
                cv2.line(mask, pts[a], pts[b], 255, 2)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def best_mask(h, w, depth_mm, mp_image, timestamp_ms, pose_result):
    """Приоритет: depth → selfie → pose-полигон. Возвращает uint8 маску."""
    if depth_mm is not None:
        return make_silhouette_mask(depth_mm)

    m = make_selfie_mask(h, w, mp_image, timestamp_ms)
    if m is None or not m.any():
        if pose_result and pose_result.pose_landmarks:
            m = make_pose_mask(h, w, pose_result)
    if m is None:
        m = np.zeros((h, w), dtype=np.uint8)
    return m
