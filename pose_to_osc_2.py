"""
Multi-person skeleton tracking (Kinect RGB + depth) -> OSC (для Resolume Arena)

Требует:
    pip install mediapipe opencv-python python-osc
    скачанный pose_landmarker.task рядом со скриптом (см. инструкцию)

Запуск:
    source venv/bin/activate
    python pose_to_osc.py

Resolume: Preferences -> OSC -> Enable OSC Input, порт 7000.
"""

import time
import cv2
import numpy as np
import freenect
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from pythonosc import udp_client

# ==== НАСТРОЙКИ ====
OSC_IP = "127.0.0.1"
OSC_PORT = 7000
MODEL_PATH = "pose_landmarker.task"
SHOW_PREVIEW = True
SHOW_COORDS_ON_FRAME = True   # подписывать x,y,z рядом с каждой точкой на видео
PRINT_COORDS_TO_CONSOLE = False  # дублировать координаты в терминал (спамит)
CONSOLE_PRINT_EVERY_N_FRAMES = 15  # если консоль включена -- не каждый кадр
SHOW_DEPTH_PREVIEW = True
USE_DEPTH_MASK = True

DEPTH_MIN_MM = 500
DEPTH_MAX_MM = 2500

# Какие суставы шлём по OSC (имя -> индекс landmark в MediaPipe Pose, 0-32)
LANDMARK_NAMES = {
    0: "nose",
    11: "left_shoulder", 12: "right_shoulder",
    13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist",
    23: "left_hip", 24: "right_hip",
    25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle",
}

# Цвета для отрисовки разных людей (BGR)
PERSON_COLORS = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (0, 255, 255)]

# Связи между суставами для рисования скелета (те же индексы, что в MediaPipe)
POSE_CONNECTIONS = mp.solutions.pose.POSE_CONNECTIONS


def get_kinect_rgb_frame():
    frame, _ = freenect.sync_get_video()
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


def get_kinect_depth_frame():
    depth, _ = freenect.sync_get_depth(format=freenect.DEPTH_MM)
    return depth


def set_kinect_tilt(angle_degs):
    """
    Наклон Kinect на motor. Открывает отдельный device-хендл (не sync API),
    поэтому если в этот момент активно читается видео/depth через sync,
    возможен конфликт -- в таком случае просто выведется предупреждение,
    поток камеры при этом не упадёт.
    """
    angle_degs = max(-30, min(30, angle_degs))
    try:
        ctx = freenect.init()
        if not ctx:
            print("Не удалось получить контекст Kinect для тилта")
            return angle_degs
        dev = freenect.open_device(ctx, 0)
        if not dev:
            print("Не удалось открыть устройство для тилта (возможно занято потоком камеры)")
            freenect.shutdown(ctx)
            return angle_degs
        freenect.set_tilt_degs(dev, angle_degs)
        time.sleep(0.05)
        freenect.close_device(dev)
        freenect.shutdown(ctx)
        print(f"Tilt выставлен: {angle_degs}°")
    except Exception as e:
        print("Ошибка управления тилтом:", e)
    return angle_degs


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


# ==== ИНИЦИАЛИЗАЦИЯ ====
def ask_num_poses():
    while True:
        raw = input("Сколько человек в кадре трекать? (1-4): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= 4:
            return int(raw)
        print("Введи число от 1 до 4.")


NUM_POSES = ask_num_poses()

raw_tilt = input("Начальный угол наклона Kinect в градусах (-30..30, Enter = 0): ").strip()
try:
    current_tilt = int(raw_tilt) if raw_tilt else 0
except ValueError:
    current_tilt = 0
current_tilt = set_kinect_tilt(current_tilt)
time.sleep(1.5)  # даём Kinect время освободить USB-хендл после тилта

client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

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

if SHOW_PREVIEW:
    cv2.namedWindow("Pose -> OSC (нажми Q для выхода)")
    cv2.moveWindow("Pose -> OSC (нажми Q для выхода)", 50, 50)
if SHOW_DEPTH_PREVIEW:
    cv2.namedWindow("Kinect Depth / IR")
    cv2.moveWindow("Kinect Depth / IR", 720, 50)

start_time = time.time()
frame_counter = 0
frame_read_errors = 0
MAX_FRAME_READ_RETRIES = 20

print("Управление: I = наклон вверх, K = наклон вниз, Q = выход")

try:
    while True:
        try:
            frame = get_kinect_rgb_frame()
            depth_mm = get_kinect_depth_frame()
        except Exception as e:
            frame_read_errors += 1
            if frame_read_errors <= MAX_FRAME_READ_RETRIES:
                print(f"Не удалось прочитать кадр ({frame_read_errors}/{MAX_FRAME_READ_RETRIES}), пробую снова: {e}")
                time.sleep(0.3)
                continue
            print("Kinect не отвечает после нескольких попыток, останавливаюсь:", e)
            break
        frame_read_errors = 0

        frame = cv2.flip(frame, 1)
        depth_mm = cv2.flip(depth_mm, 1)

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

                # Шлём каждый нужный сустав отдельным OSC-сообщением
                # Адрес вида /pose/<person_idx>/<joint_name>
                for lm_idx, name in LANDMARK_NAMES.items():
                    lm = landmarks[lm_idx]
                    x, y, z = round(lm.x, 4), round(lm.y, 4), round(lm.z, 4)
                    visibility = round(getattr(lm, "visibility", 1.0), 4)
                    client.send_message(
                        f"/pose/{person_idx}/{name}", [x, y, z, visibility]
                    )
                    if should_print:
                        print(f"person {person_idx} | {name:>14}: x={x:.3f} y={y:.3f} z={z:.3f}")

                if SHOW_PREVIEW:
                    draw_person_skeleton(
                        display_frame, landmarks, color,
                        joint_names=LANDMARK_NAMES, show_coords=SHOW_COORDS_ON_FRAME
                    )

                # ПРИМЕР явного маппинга под конкретные параметры Resolume.
                # Адреса ниже нужно заменить на свои реальные (Show OSC в Resolume).
                if person_idx == 0:
                    right_wrist_y = landmarks[16].y  # 0=вверху кадра, 1=внизу
                    opacity = round(1.0 - right_wrist_y, 3)  # рука выше -> ярче
                    client.send_message(
                        "/composition/layers/1/clips/1/video/opacity", opacity
                    )

        client.send_message("/pose/count", people_present)

        if SHOW_PREVIEW:
            cv2.imshow("Pose -> OSC (нажми Q для выхода)", display_frame)
        if SHOW_DEPTH_PREVIEW:
            cv2.imshow("Kinect Depth / IR", depth_to_display(depth_mm))

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("i"):
            current_tilt = set_kinect_tilt(current_tilt + 5)
            time.sleep(1.0)
        elif key == ord("k"):
            current_tilt = set_kinect_tilt(current_tilt - 5)
            time.sleep(1.0)
finally:
    landmarker.close()
    cv2.destroyAllWindows()
    freenect.sync_stop()
