"""Статическая конфигурация и пути. Импортируется всеми модулями — без side-effects."""
from pathlib import Path
import mediapipe as mp

PROJECT_ROOT = Path(__file__).resolve().parent

# ==== СЕТЬ / OSC ====
OSC_IP = "192.168.1.5"
OSC_PORT = 7000
MONITOR_OSC_IP = "127.0.0.1"
MONITOR_OSC_PORT = 9001
SEND_TO_MONITOR = True

# ==== SYPHON ====
SEND_SYPHON = True
SYPHON_NAME = "KinectSkeleton"
SEND_MASK_SYPHON = True
MASK_SYPHON_NAME = "KinectMask"

SYPHON_STREAMS = {
    "skeleton": {"name": "KinectSkeleton", "label": "Skeleton"},
    "rgb": {"name": "KinectRGB", "label": "RGB"},
    "depth": {"name": "KinectDepth", "label": "Depth"},
    "ir": {"name": "KinectIR", "label": "IR"},
    "mask": {"name": "KinectMask", "label": "Mask"},
}

# ==== МОДЕЛИ ====
MODEL_PATH = str(PROJECT_ROOT / "pose_landmarker.task")
SELFIE_MODEL_PATH = str(PROJECT_ROOT / "selfie_segmentation.tflite")
SELFIE_THRESHOLD = 0.5

# ==== ПРЕВЬЮ / ПЕЧАТЬ ====
SHOW_PREVIEW = True
PRINT_COORDS_TO_CONSOLE = False
CONSOLE_PRINT_EVERY_N_FRAMES = 30

OSC_SEND_FLAT = True

# ==== КАМЕРА ====
CAMERA_SOURCE = "auto"          # kinect | webcam | auto
SMOOTHING_ALPHA = 0.8

# ==== ABLETON ====
ABLETON_OSC_IP = "127.0.0.1"
ABLETON_OSC_PORT = 11000
SEND_TO_ABLETON = True

# ==== ПРОФИЛИ / WEB ====
MAPPINGS_PATH = str(PROJECT_ROOT / "mappings.json")   # legacy fallback
PROFILES_DIR = str(PROJECT_ROOT / "profiles")
CURRENT_PROFILE = "default"
WEB_HOST = "0.0.0.0"
WEB_PORT = 8090
WEB_INDEX = str(PROJECT_ROOT / "web" / "index.html")

# ==== DEPTH ====
DEPTH_MIN_MM = 500
DEPTH_MAX_MM = 2500

# ==== MediaPipe POSES ====
LANDMARK_NAMES = {
    0: "nose",
    11: "left_shoulder", 12: "right_shoulder",
    13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist",
    23: "left_hip", 24: "right_hip",
    25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle",
}

PERSON_COLORS = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255)]
POSE_CONNECTIONS = mp.solutions.pose.POSE_CONNECTIONS

# Правильный порядок обхода тела для человекообразного контура
# (не z-order MediaPipe — тот даёт спайки между конечностями)
BODY_OUTLINE_ORDER = [
    0,   # nose
    11,  # left_shoulder
    13,  # left_elbow
    15,  # left_wrist
    16,  # right_wrist
    14,  # right_elbow
    12,  # right_shoulder
    24,  # right_hip
    26,  # right_knee
    28,  # right_ankle
    27,  # left_ankle
    25,  # left_knee
    23,  # left_hip
]
