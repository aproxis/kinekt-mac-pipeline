"""
Multi-person skeleton tracking (Kinect RGB + depth + live tilt) -> OSC (Resolume Arena)

Единый device-хендл Kinect для видео/depth/тилта (без sync API).
Smoothing координат + детекция жестов + FPS + Web UI.

Требует:
    pip install mediapipe opencv-python python-osc
    pose_landmarker.task рядом со скриптом

Запуск:
    source venv/bin/activate
    python pose_to_osc_6.py

Управление в окне превью: I = тилт вверх, K = тилт вниз, Q = выход.
Web UI: http://localhost:8080
"""

import socket
import json
import os
import time
import cv2
import numpy as np
import freenect
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from pythonosc import udp_client
from pythonosc import osc_message
from pythonosc.osc_message_builder import OscMessageBuilder
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    import syphon
    from syphon.utils.numpy import copy_image_to_mtl_texture
    from syphon.utils.raw import create_mtl_texture
    SYPHON_AVAILABLE = True
except ImportError:
    SYPHON_AVAILABLE = False

# ==== НАСТРОЙКИ ====
OSC_IP = "192.168.1.5"
OSC_PORT = 7000
MONITOR_OSC_IP = "127.0.0.1"
MONITOR_OSC_PORT = 9001
SEND_TO_MONITOR = True
SEND_SYPHON = True
SYPHON_NAME = "KinectSkeleton"
MODEL_PATH = "pose_landmarker.task"
SHOW_PREVIEW = True
SHOW_DEPTH_PREVIEW = True
USE_DEPTH_MASK = True
SHOW_COORDS_ON_FRAME = True
PRINT_COORDS_TO_CONSOLE = False
CONSOLE_PRINT_EVERY_N_FRAMES = 30

OSC_SEND_FLAT = True

CAMERA_SOURCE = "auto"
SMOOTHING_ALPHA = 0.8   # глобальное сглаживание (0-1). Per-mapping в JSON переопределяет

ABLETON_OSC_IP = "127.0.0.1"
ABLETON_OSC_PORT = 11000
SEND_TO_ABLETON = True

MAPPINGS_PATH = "mappings.json"   # legacy fallback
PROFILES_DIR = "profiles"
CURRENT_PROFILE = "default"
WEB_HOST = "0.0.0.0"
WEB_PORT = 8080

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

# ==== ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ ====
latest_rgb = None
latest_depth = None
camera_mode = "none"

smooth_state = {}

# ==== STATE FOR WEB UI ====
joint_state = {}
joint_state_lock = threading.Lock()
live_mappings = []
mappings_lock = threading.Lock()
ableton_scanning = False

last_sent = {}  # для threshold проверки

# ==== СГЛАЖИВАНИЕ ====
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
            cv2.putText(frame, label, (x + 6, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)


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


# ==== PROFILES ====
current_profile = CURRENT_PROFILE


def ensure_profiles_dir():
    os.makedirs(PROFILES_DIR, exist_ok=True)


def profile_path(name):
    return os.path.join(PROFILES_DIR, f"{name}.json")


def list_profiles():
    ensure_profiles_dir()
    names = []
    for f in sorted(os.listdir(PROFILES_DIR)):
        if f.endswith(".json"):
            names.append(f[:-5])
    return names


def load_mappings():
    global live_mappings, current_profile
    ensure_profiles_dir()
    # try current profile first
    path = profile_path(current_profile)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        with mappings_lock:
            live_mappings = data
        print(f"Profile '{current_profile}': {len(data)} mappings")
        return data
    # fallback: migrate from legacy mappings.json
    if os.path.exists(MAPPINGS_PATH):
        with open(MAPPINGS_PATH) as f:
            data = json.load(f)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        with mappings_lock:
            live_mappings = data
        print(f"Migrated mappings.json -> profiles/{current_profile}.json")
        return data
    # create default
    default = [
        {"id": 1, "joint": "right_wrist", "axis": "y", "track": 4, "device": 0, "param": 144, "smoothing": 0.8, "threshold": 0.005},
        {"id": 2, "joint": "left_wrist", "axis": "y", "track": 4, "device": 0, "param": 148, "smoothing": 0.8, "threshold": 0.005},
    ]
    with open(path, "w") as f:
        json.dump(default, f, indent=2)
    with mappings_lock:
        live_mappings = default
    print(f"Created default profile: {len(default)} mappings")
    return default


def save_mappings(data):
    with mappings_lock:
        live_mappings = data
    path = profile_path(current_profile)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved profile '{current_profile}': {len(data)} mappings")


def load_profile(name):
    global live_mappings, current_profile
    path = profile_path(name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    with mappings_lock:
        live_mappings = data
    current_profile = name
    print(f"Switched to profile '{name}': {len(data)} mappings")
    return data


def save_as_profile(name, data):
    path = profile_path(name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved as profile '{name}': {len(data)} mappings")


def delete_profile(name):
    if name == CURRENT_PROFILE:
        return False
    path = profile_path(name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# ==== ABLETON SCANNER ====
def ableton_query(address, *args, timeout=4):
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", 11001))
    listener.settimeout(0.01)
    for _ in range(500):
        try:
            listener.recvfrom(65535)
        except socket.timeout:
            break

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        builder = OscMessageBuilder(address)
        for a in args:
            if isinstance(a, int):
                builder.add_arg(a, "i")
            elif isinstance(a, float):
                builder.add_arg(a, "f")
            else:
                builder.add_arg(str(a), "s")
        sender.sendto(builder.build().dgram, (ABLETON_OSC_IP, ABLETON_OSC_PORT))
        deadline = time.time() + timeout
        while time.time() < deadline:
            listener.settimeout(max(0.01, deadline - time.time()))
            try:
                data, _ = listener.recvfrom(65535)
                parsed = osc_message.OscMessage(data)
                if parsed.address != "/live/error" and parsed.address != "/live/startup":
                    return parsed
            except socket.timeout:
                return None
        return None
    finally:
        sender.close()
        listener.close()


def scan_ableton():
    global ableton_scanning
    ableton_scanning = True
    time.sleep(0.1)
    try:
        r = ableton_query("/live/song/get/num_tracks")
        num_tracks = int(r.params[-1]) if r else 0
        r = ableton_query("/live/song/get/track_data", 0, num_tracks, "track.name")
        track_names = list(r.params) if r else []

        tracks = []
        for t in range(num_tracks):
            name = str(track_names[t]) if t < len(track_names) else f"Track {t}"
            tr = {"index": t, "name": name, "devices": []}

            r = ableton_query("/live/track/get/num_devices", t)
            num_devices = int(r.params[-1]) if r else 0

            for d in range(num_devices):
                r = ableton_query("/live/track/get/devices/name", t, d)
                dname = str(r.params[-1]) if r else f"Device {d}"
                dev = {"index": d, "name": dname, "parameters": []}

                r = ableton_query("/live/device/get/parameters/name", t, d)
                names = list(r.params[2:]) if r and len(r.params) > 2 else []
                r = ableton_query("/live/device/get/parameters/min", t, d)
                mins = list(r.params[2:]) if r and len(r.params) > 2 else []
                r = ableton_query("/live/device/get/parameters/max", t, d)
                maxs = list(r.params[2:]) if r and len(r.params) > 2 else []

                for i, pname in enumerate(names):
                    dev["parameters"].append({
                        "index": i, "name": str(pname),
                        "min": float(mins[i]) if i < len(mins) else 0.0,
                        "max": float(maxs[i]) if i < len(maxs) else 1.0,
                    })

                tr["devices"].append(dev)
            tracks.append(tr)

        return {"tracks": tracks, "total": num_tracks}
    except Exception as e:
        return {"error": str(e)}
    finally:
        ableton_scanning = False


# ==== WEB SERVER ====
def web_server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/joints":
                with joint_state_lock:
                    data = dict(joint_state)
                self.send_json(data)

            elif path == "/api/mappings":
                with mappings_lock:
                    self.send_json(live_mappings)

            elif path == "/api/profiles":
                self.send_json(list_profiles())

            elif path == "/api/profiles/current":
                with mappings_lock:
                    self.send_json({"name": current_profile, "mappings": live_mappings})

            elif path == "/api/ableton/scan":
                self.send_json(scan_ableton())

            elif path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                try:
                    with open("web/index.html") as f:
                        self.wfile.write(f.read().encode())
                except FileNotFoundError:
                    self.wfile.write(b"<h1>web/index.html not found</h1>")

            else:
                self.send_json({"error": "not found"}, 404)

        def do_PUT(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except Exception:
                self.send_json({"error": "bad json"}, 400)
                return

            if self.path == "/api/mappings":
                save_mappings(data)
                self.send_json({"ok": True})

            elif self.path == "/api/profiles/load":
                name = data.get("name")
                if not name:
                    self.send_json({"error": "name required"}, 400)
                elif load_profile(name) is None:
                    self.send_json({"error": f"profile '{name}' not found"}, 404)
                else:
                    self.send_json({"ok": True, "name": name})

            elif self.path == "/api/profiles/save":
                name = data.get("name")
                mappings = data.get("mappings")
                if not name or mappings is None:
                    self.send_json({"error": "name and mappings required"}, 400)
                save_as_profile(name, mappings)
                self.send_json({"ok": True, "name": name})

            else:
                self.send_json({"error": "not found"}, 404)

        def do_DELETE(self):
            import urllib.parse as up
            parsed = up.urlparse(self.path)
            if parsed.path == "/api/profiles":
                query = parse_qs(parsed.query)
                name = query.get("name", [None])[0]
                if not name:
                    self.send_json({"error": "name required"}, 400)
                elif delete_profile(name):
                    self.send_json({"ok": True})
                else:
                    self.send_json({"error": f"cannot delete '{name}'"}, 400)
            else:
                self.send_json({"error": "not found"}, 404)

        def send_json(self, data, code=200):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

    server = HTTPServer((WEB_HOST, WEB_PORT), Handler)
    print(f"Web UI: http://localhost:{WEB_PORT}")
    server.serve_forever()


web_thread = threading.Thread(target=web_server, daemon=True)
web_thread.start()


# ==== ИНИЦИАЛИЗАЦИЯ ====
NUM_POSES = ask_num_poses()
current_tilt = ask_initial_tilt()

client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
monitor_client = udp_client.SimpleUDPClient(MONITOR_OSC_IP, MONITOR_OSC_PORT) if SEND_TO_MONITOR else None
ableton_client = udp_client.SimpleUDPClient(ABLETON_OSC_IP, ABLETON_OSC_PORT) if SEND_TO_ABLETON else None

client._sock.setblocking(False)
if monitor_client is not None:
    monitor_client._sock.setblocking(False)
if ableton_client is not None:
    ableton_client._sock.setblocking(False)


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


load_mappings()

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

# ==== ОТКРЫВАЕМ КАМЕРУ ====
ctx = None
dev = None
webcam = None
has_depth = True


def init_kinect():
    global ctx, dev, has_depth
    try:
        ctx = freenect.init()
        if not ctx:
            return False
        dev = freenect.open_device(ctx, 0)
        if not dev:
            freenect.shutdown(ctx)
            ctx = None
            return False
        freenect.set_video_mode(dev, freenect.RESOLUTION_MEDIUM, freenect.VIDEO_RGB)
        freenect.set_depth_mode(dev, freenect.RESOLUTION_MEDIUM, freenect.DEPTH_MM)
        freenect.set_video_callback(dev, video_callback)
        freenect.set_depth_callback(dev, depth_callback)
        freenect.set_tilt_degs(dev, current_tilt)
        print(f"Tilt выставлен: {current_tilt}°")
        freenect.start_video(dev)
        freenect.start_depth(dev)
        return True
    except Exception as e:
        print(f"Kinect init error: {e}")
        if ctx:
            freenect.shutdown(ctx)
            ctx = None
        return False


def init_webcam():
    global webcam, has_depth
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    webcam = cap
    has_depth = False
    return True


if CAMERA_SOURCE == "kinect" or CAMERA_SOURCE == "auto":
    if init_kinect():
        camera_mode = "kinect"
    elif CAMERA_SOURCE == "kinect":
        raise RuntimeError("Kinect не найден, а CAMERA_SOURCE=kinect")

if camera_mode != "kinect":
    if init_webcam():
        camera_mode = "webcam"
        print("Режим: webcam (MacBook камера) — без depth/тилта")
    else:
        raise RuntimeError("Не удалось открыть ни Kinect, ни вебку")

if SHOW_PREVIEW:
    cv2.namedWindow("Pose -> OSC (нажми Q для выхода)")
    cv2.moveWindow("Pose -> OSC (нажми Q для выхода)", 50, 50)
has_depth = has_depth and (SHOW_DEPTH_PREVIEW or USE_DEPTH_MASK)
if has_depth and SHOW_DEPTH_PREVIEW:
    cv2.namedWindow("Depth / IR")
    cv2.moveWindow("Depth / IR", 720, 50)

print(f"Камера: {camera_mode.upper()}")
print("Управление: I = наклон вверх, K = наклон вниз, Q = выход")
if camera_mode == "webcam":
    print("(тилт доступен только с Kinect)")
if OSC_SEND_FLAT:
    print("OSC плоские адреса: /pose/{person}/{joint}/{x|y|z|vis}")
print(f"AbletonOSC: маппинг на :{ABLETON_OSC_PORT} (редактируй в Web UI)")
if SMOOTHING_ALPHA > 0:
    print(f"Сглаживание: alpha={SMOOTHING_ALPHA}")

syphon_server = None
syphon_texture = None
if SEND_SYPHON:
    if not SYPHON_AVAILABLE:
        print("syphon-python не установлен -- Syphon-вывод отключён")
    else:
        syphon_server = syphon.SyphonMetalServer(SYPHON_NAME)
        print(f"Syphon-сервер: '{SYPHON_NAME}'")

start_time = time.time()
frame_counter = 0
fps_counter = 0
fps_timer = time.time()
current_fps = 0

prev_people_present = -1
prev_gesture_state = {}

try:
    while True:
        if camera_mode == "kinect":
            freenect.process_events(ctx)
            if latest_rgb is None or latest_depth is None:
                continue
            frame_bgr = latest_rgb
            depth_mm_raw = cv2.flip(latest_depth, 1)
            display_frame = cv2.flip(frame_bgr, 1)
            if USE_DEPTH_MASK:
                mask = make_silhouette_mask(depth_mm_raw)
                display_frame = cv2.bitwise_and(display_frame, display_frame, mask=mask)
            depth_mm = depth_mm_raw
        else:
            ret, frame_bgr = webcam.read()
            if not ret:
                print("Вебка потеряна")
                break
            display_frame = cv2.flip(frame_bgr, 1)
            depth_mm = None

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int((time.time() - start_time) * 1000)

        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        people_present = 0
        frame_counter += 1
        fps_counter += 1

        now = time.time()
        if now - fps_timer >= 1.0:
            current_fps = fps_counter
            fps_counter = 0
            fps_timer = now
            send_osc("/fps", current_fps)

        should_print = (
            PRINT_COORDS_TO_CONSOLE and frame_counter % CONSOLE_PRINT_EVERY_N_FRAMES == 0
        )

        # обновляем joint_state для Web UI
        with joint_state_lock:
            joint_state.clear()

        if result.pose_landmarks:
            people_present = len(result.pose_landmarks)

            for person_idx, landmarks in enumerate(result.pose_landmarks):
                color = PERSON_COLORS[person_idx % len(PERSON_COLORS)]

                for lm_idx, name in LANDMARK_NAMES.items():
                    lm = landmarks[lm_idx]

                    a = SMOOTHING_ALPHA
                    x = smooth_val(f"p{person_idx}_{name}_x", round(lm.x, 4), a)
                    y = smooth_val(f"p{person_idx}_{name}_y", round(lm.y, 4), a)
                    z = smooth_val(f"p{person_idx}_{name}_z", round(lm.z, 4), a)
                    visibility = smooth_val(f"p{person_idx}_{name}_vis", round(getattr(lm, "visibility", 1.0), 4), a)

                    # store для Web UI
                    with joint_state_lock:
                        joint_state[name] = {"x": x, "y": y, "z": z, "vis": visibility}

                    send_osc(f"/pose/{person_idx}/{name}", [x, y, z, visibility])

                    # Ableton маппинг из JSON
                    if ableton_client is not None and person_idx == 0 and not ableton_scanning:
                        with mappings_lock:
                            for m in live_mappings:
                                if m["joint"] == name:
                                    val = {"x": x, "y": y, "z": z, "vis": visibility}.get(m["axis"])
                                    if val is not None:
                                        smoothing = m.get("smoothing", SMOOTHING_ALPHA)
                                        threshold = m.get("threshold", 0)
                                        skey = f"ableton_{m['id']}"
                                        sval = smooth_val(skey, val, smoothing)
                                        # scale/min/max
                                        scale = m.get("scale", 1.0)
                                        pmin = m.get("min", 0.0)
                                        pmax = m.get("max", 1.0)
                                        if scale != 1.0:
                                            sval = max(0.0, min(1.0, sval * scale))
                                        sval = pmin + max(0.0, min(1.0, sval)) * (pmax - pmin)
                                        last = last_sent.get(skey)
                                        if threshold and last is not None and abs(sval - last) < threshold:
                                            pass
                                        else:
                                            last_sent[skey] = sval
                                            ableton_client.send_message(
                                                "/live/device/set/parameter/value",
                                                [m["track"], m["device"], m["param"], sval]
                                            )

                    if OSC_SEND_FLAT:
                        base = f"/pose/{person_idx}/{name}"
                        send_osc(f"{base}/x", x)
                        send_osc(f"{base}/y", y)
                        send_osc(f"{base}/z", z)
                        send_osc(f"{base}/vis", visibility)

                    if should_print:
                        print(f"person {person_idx} | {name:>14}: x={x:.3f} y={y:.3f} z={z:.3f}")

                if person_idx == 0:
                    wrist = landmarks[16]
                    shoulder = landmarks[12]
                    hip = landmarks[24]

                    right_hand_up = 1.0 if wrist.y < shoulder.y else 0.0
                    right_hand_down = 1.0 if wrist.y > hip.y else 0.0

                    gkey = "p0_right_hand_up"
                    if prev_gesture_state.get(gkey) != right_hand_up:
                        send_osc("/gesture/0/right_hand_up", right_hand_up)
                        prev_gesture_state[gkey] = right_hand_up

                    gkey = "p0_right_hand_down"
                    if prev_gesture_state.get(gkey) != right_hand_down:
                        send_osc("/gesture/0/right_hand_down", right_hand_down)
                        prev_gesture_state[gkey] = right_hand_down

                if SHOW_PREVIEW:
                    draw_person_skeleton(
                        display_frame, landmarks, color,
                        joint_names=LANDMARK_NAMES, show_coords=SHOW_COORDS_ON_FRAME
                    )

        if prev_people_present != people_present:
            send_osc("/pose/presence", people_present)
            prev_people_present = people_present

        if SHOW_PREVIEW:
            cv2.putText(display_frame, f"FPS: {current_fps}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(display_frame, f"People: {people_present}", (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

        send_osc("/pose/count", people_present)

        if SHOW_PREVIEW:
            cv2.imshow("Pose -> OSC (нажми Q для выхода)", display_frame)
        if has_depth and SHOW_DEPTH_PREVIEW and depth_mm is not None:
            cv2.imshow("Depth / IR", depth_to_display(depth_mm))

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
        elif key == ord("i") and camera_mode == "kinect":
            current_tilt = max(-30, min(30, current_tilt + 5))
            freenect.set_tilt_degs(dev, current_tilt)
            print(f"Tilt выставлен: {current_tilt}°")
        elif key == ord("k") and camera_mode == "kinect":
            current_tilt = max(-30, min(30, current_tilt - 5))
            freenect.set_tilt_degs(dev, current_tilt)
            print(f"Tilt выставлен: {current_tilt}°")
finally:
    landmarker.close()
    cv2.destroyAllWindows()
    if syphon_server is not None:
        syphon_server.stop()
    if camera_mode == "kinect":
        if dev:
            freenect.stop_video(dev)
            freenect.stop_depth(dev)
            freenect.close_device(dev)
        if ctx:
            freenect.shutdown(ctx)
    elif webcam is not None:
        webcam.release()
