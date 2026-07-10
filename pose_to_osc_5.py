"""
Multi-person skeleton tracking (Kinect RGB + depth + live tilt) -> OSC (Resolume Arena)

Единый device-хендл Kinect для видео/depth/тилта (без sync API) --
так тилт можно крутить прямо во время стрима, без конфликтов USB.

Требует:
    pip install mediapipe opencv-python python-osc
    pose_landmarker.task рядом со скриптом

Запуск:
    source venv/bin/activate
    python pose_to_osc_5.py

Управление в окне превью: I = тилт вверх, K = тилт вниз, Q = выход.
Resolume: Preferences -> OSC -> Enable OSC Input, порт 7000.
           Edit OSC Mapping на любом параметре -> ввести /pose/0/nose/y и т.д.
"""

import socket
import time
import cv2
import numpy as np
import freenect
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from pythonosc import udp_client

try:
    import syphon
    from syphon.utils.numpy import copy_image_to_mtl_texture
    from syphon.utils.raw import create_mtl_texture
    SYPHON_AVAILABLE = True
except ImportError:
    SYPHON_AVAILABLE = False

# ==== НАСТРОЙКИ ====
OSC_IP = "192.168.1.5"
OSC_PORT = 7000              # Resolume OSC In
MONITOR_OSC_IP = "127.0.0.1"
MONITOR_OSC_PORT = 9001      # сюда параллельно шлём дубль для Protokol/мониторинга
SEND_TO_MONITOR = True
SEND_SYPHON = True
SYPHON_NAME = "KinectSkeleton"
MODEL_PATH = "pose_landmarker.task"
SHOW_PREVIEW = True
SHOW_DEPTH_PREVIEW = True
USE_DEPTH_MASK = True
SHOW_COORDS_ON_FRAME = True
PRINT_COORDS_TO_CONSOLE = False
CONSOLE_PRINT_EVERY_N_FRAMES = 15

OSC_SEND_FLAT = True         # /pose/0/nose/x, /pose/0/nose/y, ... для Resolume маппинга

DEPTH_MIN_MM = 500
DEPTH_MAX_MM = 2500

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

# ==== ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ ПОСЛЕДНИХ КАДРОВ (заполняется callback'ами) ====
latest_rgb = None
latest_depth = None


def video_callback(dev, data, timestamp):
    global latest_rgb
    latest_rgb = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)


def depth_callback(dev, data, timestamp):
    global latest_depth
    latest_depth = data.copy()


def depth_to_display(depth_mm):
    valid = depth_mm.copy()
    valid[valid == 0] = DEPTH_MAX_MM
    clipped = np.clip(valid, DEPTH_MIN_MM, DEPTH_MAX_MM)
    normalized = ((clipped - DEPTH_MIN_MM) / (DEPTH_MAX_MM - DEPTH_MIN_MM) * 255)
    normalized = (255 - normalized).astype(np.uint8)
    return cv2.applyColorMap(normalized, cv2.COLORMAP_JET)


def make_silhouette_mask(depth_mm):
    mask = np.zeros(depth_mm.shape, dtype=np.uint8)
    in_range = (depth_mm > DEPTH_MIN_MM) & (depth_mm < DEPTH_MAX_MM)
    mask[in_range] = 255
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def draw_person_skeleton(frame, landmarks, color, joint_names=None, show_coords=False):
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in POSE_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], color, 2)
    for p in pts:
        cv2.circle(frame, p, 4, color, -1)

    if show_coords and joint_names:
        for lm_idx, name in joint_names.items():
            lm = landmarks[lm_idx]
            x, y = pts[lm_idx]
            label = f"{name} ({lm.x:.2f},{lm.y:.2f},{lm.z:.2f})"
            cv2.putText(
                frame, label, (x + 6, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA
            )


def ask_num_poses():
    while True:
        raw = input("Сколько человек в кадре трекать? (1-4): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= 4:
            return int(raw)
        print("Введи число от 1 до 4.")


def ask_initial_tilt():
    raw = input("Начальный угол наклона Kinect в градусах (-30..30, Enter = 0): ").strip()
    try:
        return max(-30, min(30, int(raw))) if raw else 0
    except ValueError:
        return 0


# ==== ИНИЦИАЛИЗАЦИЯ ====
NUM_POSES = ask_num_poses()
current_tilt = ask_initial_tilt()

client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
monitor_client = udp_client.SimpleUDPClient(MONITOR_OSC_IP, MONITOR_OSC_PORT) if SEND_TO_MONITOR else None

# non-blocking сокеты — не крешиться если Resolume не слушает
client._sock.setblocking(False)
if monitor_client is not None:
    monitor_client._sock.setblocking(False)


def send_osc(address, value):
    try:
        client.send_message(address, value)
    except (BlockingIOError, OSError):
        pass
    if monitor_client is not None:
        try:
            monitor_client.send_message(address, value)
        except (BlockingIOError, OSError):
            pass


base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_poses=NUM_POSES,
    min_pose_detection_confidence=0.5,
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)
landmarker = vision.PoseLandmarker.create_from_options(options)

# ==== ОТКРЫВАЕМ KINECT ОДИН РАЗ, ДЕРЖИМ ХЕНДЛ ДО КОНЦА ====
ctx = freenect.init()
if not ctx:
    raise RuntimeError("Не удалось получить контекст freenect")

dev = freenect.open_device(ctx, 0)
if not dev:
    raise RuntimeError("Не удалось открыть устройство Kinect")

freenect.set_video_mode(dev, freenect.RESOLUTION_MEDIUM, freenect.VIDEO_RGB)
freenect.set_depth_mode(dev, freenect.RESOLUTION_MEDIUM, freenect.DEPTH_MM)
freenect.set_video_callback(dev, video_callback)
freenect.set_depth_callback(dev, depth_callback)

freenect.set_tilt_degs(dev, current_tilt)
print(f"Tilt выставлен: {current_tilt}°")

freenect.start_video(dev)
freenect.start_depth(dev)

if SHOW_PREVIEW:
    cv2.namedWindow("Pose -> OSC (нажми Q для выхода)")
    cv2.moveWindow("Pose -> OSC (нажми Q для выхода)", 50, 50)
if SHOW_DEPTH_PREVIEW:
    cv2.namedWindow("Kinect Depth / IR")
    cv2.moveWindow("Kinect Depth / IR", 720, 50)

print("Управление: I = наклон вверх, K = наклон вниз, Q = выход")
if OSC_SEND_FLAT:
    print("OSC плоские адреса включены: /pose/{person}/{joint}/{x|y|z|vis}")

syphon_server = None
syphon_texture = None
if SEND_SYPHON:
    if not SYPHON_AVAILABLE:
        print("syphon-python не установлен -- Syphon-вывод отключён. "
              "pip install syphon-python pyobjc")
    else:
        syphon_server = syphon.SyphonMetalServer(SYPHON_NAME)
        print(f"Syphon-сервер запущен: '{SYPHON_NAME}' -- ищи его в Resolume как Source")

start_time = time.time()
frame_counter = 0

try:
    while True:
        freenect.process_events(ctx)

        if latest_rgb is None or latest_depth is None:
            continue

        frame = cv2.flip(latest_rgb, 1)
        depth_mm = cv2.flip(latest_depth, 1)

        if USE_DEPTH_MASK:
            mask = make_silhouette_mask(depth_mm)
            display_frame = cv2.bitwise_and(frame, frame, mask=mask)
        else:
            display_frame = frame.copy()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int((time.time() - start_time) * 1000)

        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        people_present = 0
        frame_counter += 1
        should_print = (
            PRINT_COORDS_TO_CONSOLE and frame_counter % CONSOLE_PRINT_EVERY_N_FRAMES == 0
        )

        if result.pose_landmarks:
            people_present = len(result.pose_landmarks)

            for person_idx, landmarks in enumerate(result.pose_landmarks):
                color = PERSON_COLORS[person_idx % len(PERSON_COLORS)]

                for lm_idx, name in LANDMARK_NAMES.items():
                    lm = landmarks[lm_idx]
                    x, y, z = round(lm.x, 4), round(lm.y, 4), round(lm.z, 4)
                    visibility = round(getattr(lm, "visibility", 1.0), 4)

                    # массивы для Protokol (компактно)
                    send_osc(
                        f"/pose/{person_idx}/{name}", [x, y, z, visibility]
                    )

                    # плоские адреса для Resolume маппинга
                    if OSC_SEND_FLAT:
                        base = f"/pose/{person_idx}/{name}"
                        send_osc(f"{base}/x", x)
                        send_osc(f"{base}/y", y)
                        send_osc(f"{base}/z", z)
                        send_osc(f"{base}/vis", visibility)

                    if should_print:
                        print(f"person {person_idx} | {name:>14}: x={x:.3f} y={y:.3f} z={z:.3f}")

                if SHOW_PREVIEW:
                    draw_person_skeleton(
                        display_frame, landmarks, color,
                        joint_names=LANDMARK_NAMES, show_coords=SHOW_COORDS_ON_FRAME
                    )

                # Пример явного маппинга под конкретный параметр Resolume.
                if person_idx == 0:
                    right_wrist_y = landmarks[16].y
                    opacity = round(1.0 - right_wrist_y, 3)
                    send_osc(
                        "/composition/layers/1/clips/1/video/opacity", opacity
                    )

        send_osc("/pose/count", people_present)

        if SHOW_PREVIEW:
            cv2.imshow("Pose -> OSC (нажми Q для выхода)", display_frame)
        if SHOW_DEPTH_PREVIEW:
            cv2.imshow("Kinect Depth / IR", depth_to_display(depth_mm))

        if syphon_server is not None:
            h, w = display_frame.shape[:2]
            if syphon_texture is None:
                syphon_texture = create_mtl_texture(syphon_server.device, w, h)
            rgba = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGBA)
            copy_image_to_mtl_texture(rgba, syphon_texture)
            syphon_server.publish_frame_texture(syphon_texture)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("i"):
            current_tilt = max(-30, min(30, current_tilt + 5))
            freenect.set_tilt_degs(dev, current_tilt)
            print(f"Tilt выставлен: {current_tilt}°")
        elif key == ord("k"):
            current_tilt = max(-30, min(30, current_tilt - 5))
            freenect.set_tilt_degs(dev, current_tilt)
            print(f"Tilt выставлен: {current_tilt}°")
finally:
    landmarker.close()
    cv2.destroyAllWindows()
    if syphon_server is not None:
        syphon_server.stop()
    freenect.stop_video(dev)
    freenect.stop_depth(dev)
    freenect.close_device(dev)
    freenect.shutdown(ctx)
