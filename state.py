"""Разделяемое состояние между модулями (потокобезопасно где нужно)."""
import threading
from typing import Optional

import numpy as np

# ==== RUNTIME CONTROLS (меняются через GUI) ====
runtime = {
    "num_poses": 2, "tilt": 0,
    "send_osc": True, "send_osc_flat": True, "send_gestures": True,
    "show_coords": False,
    "camera_mode": "auto",
    "panel_open": False,
    "mouse_x": 0, "mouse_y": 0, "mouse_down": False,

    # streams (Syphon output toggles)
    "stream_skeleton": True,    # KinectSkeleton — RGB + skeleton
    "stream_rgb": True,         # KinectRGB — clean RGB
    "stream_depth": True,       # KinectDepth — depth colormap
    "stream_ir": False,         # KinectIR — IR grayscale
    "stream_mask": True,        # KinectMask — silhouette mask

    # preview tab
    "preview_tab": 0,
}

# ==== ПОСЛЕДНИЕ КАДРЫ (пишутся из callback-потока Kinect, читаются из главного) ====
frame_lock = threading.Lock()
latest_rgb: Optional[np.ndarray] = None
latest_depth: Optional[np.ndarray] = None

# ==== КАМЕРА ====
camera_mode = "none"          # kinect | webcam

# ==== СГЛАЖИВАНИЕ ====
smooth_state = {}
last_sent = {}                # для threshold проверки

# ==== WEB UI ====
joint_state = {}
joint_state_lock = threading.Lock()
live_mappings = []
mappings_lock = threading.Lock()
ableton_scanning = False

# ==== ПРОФИЛИ ====
current_profile = "default"


def smooth_val(key, raw, alpha):
    if alpha <= 0:
        return raw
    prev = smooth_state.get(key)
    if prev is None:
        smooth_state[key] = raw
        return raw
    smoothed = prev * alpha + raw * (1 - alpha)
    smooth_state[key] = smoothed
    return round(smoothed, 4)
