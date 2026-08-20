"""
Kinekt360 — Kinect on Mac pipeline (модульная архитектура).

  main.py                    — оркестрация (этот файл)
  config.py                  — статические настройки
  state.py                   — разделяемое состояние
  profiles.py                — конфиги маппингов
  modules/input/camera.py    — Kinect / webcam (FrameSource)
  modules/process/pose.py    — MediaPipe pose + скелет + жесты
  modules/process/mask.py    — маски: depth / selfie / pose
  modules/output/osc.py      — OSC (Resolume + monitor)
  modules/output/ableton.py  — AbletonOSC + guard + маппинг
  modules/output/syphon.py   — 5 Syphon-стримов
  modules/output/webui.py    — HTTP Web UI
  modules/ui/panel.py        — OpenCV-панель управления

Запуск:
    source venv/bin/activate
    python main.py
"""
import time

import cv2
import mediapipe as mp
from pythonosc import udp_client

import config
import state
import profiles
from modules.input import camera as camera_mod
from modules.process import mask as mask_mod
from modules.process import pose as pose_mod
from modules.output import ableton as ableton_mod
from modules.output import osc as osc_mod
from modules.output import syphon as syphon_mod
from modules.output import webui
from modules.ui import panel


# ==== ВВОД (startup) ====
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


def main():
    NUM_POSES = ask_num_poses()
    current_tilt = ask_initial_tilt()
    state.runtime["num_poses"] = NUM_POSES
    state.runtime["tilt"] = current_tilt

    # хук: после сохранения/смены профиля — сразу ре-валидация guard'а
    profiles.on_changed = lambda: ableton_mod.ableton_guard.validate(force=True)

    # ---- OSC клиенты ----
    osc = osc_mod.OscOutput()

    ableton_client = (
        udp_client.SimpleUDPClient(config.ABLETON_OSC_IP, config.ABLETON_OSC_PORT)
        if config.SEND_TO_ABLETON else None
    )
    if ableton_client is not None:
        ableton_client._sock.setblocking(False)

    # ---- маппинги + валидация ----
    profiles.load_mappings()
    ableton_mod.ableton_guard.validate(force=True)
    if ableton_mod.ableton_guard.invalid_mappings:
        print(f"[AbletonGuard] Маппинги с битыми индексами (не будут слаться): "
              f"{sorted(ableton_mod.ableton_guard.invalid_mappings)}")

    # ---- MediaPipe pose ----
    pose_tracker = pose_mod.PoseTracker(NUM_POSES)

    # ---- Web UI (отдельный поток) ----
    import threading
    threading.Thread(target=webui.start_web_server, daemon=True).start()

    # ---- камера ----
    source = camera_mod.create_camera(config.CAMERA_SOURCE, current_tilt)
    camera_mode = state.camera_mode

    # ---- окна превью ----
    panel.create_preview_window()
    if source.has_depth:
        cv2.namedWindow("Depth / IR")
        cv2.moveWindow("Depth / IR", 720, 50)
    panel.setup_mouse()

    print(f"Камера: {camera_mode.upper()}")
    print("TAB = панель управления, Q = выход")
    print(f"AbletonOSC: маппинг на :{config.ABLETON_OSC_PORT} (редактируй в Web UI)")
    if config.SMOOTHING_ALPHA > 0:
        print(f"Сглаживание: alpha={config.SMOOTHING_ALPHA}")

    # ---- Syphon ----
    syphon_out = syphon_mod.SyphonOutput()

    start_time = time.time()
    frame_counter = 0
    fps_counter = 0
    fps_timer = time.time()
    current_fps = 0

    prev_people_present = -1
    prev_gesture_state = {}

    try:
        while True:
            frame = source.read()
            if frame is None:
                print("Камера потеряна")
                break
            frame_bgr = frame.frame_bgr
            display_frame = frame.display_frame
            depth_mm = frame.depth_mm

            # маска глубины на превью
            if depth_mm is not None:
                display_frame = cv2.bitwise_and(
                    display_frame, display_frame,
                    mask=mask_mod.make_silhouette_mask(depth_mm)
                )

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int((time.time() - start_time) * 1000)

            result = pose_tracker.detect(mp_image, timestamp_ms)

            people_present = 0
            frame_counter += 1
            fps_counter += 1

            now = time.time()
            if now - fps_timer >= 1.0:
                current_fps = fps_counter
                fps_counter = 0
                fps_timer = now
                osc.send("/fps", current_fps)

            # Ableton guard: периодическая валидация + пик ошибок
            if ableton_client is not None:
                ableton_mod.ableton_guard.validate()
                if frame_counter % 15 == 0:
                    ableton_mod.ableton_guard.peek_errors()

            should_print = (
                config.PRINT_COORDS_TO_CONSOLE
                and frame_counter % config.CONSOLE_PRINT_EVERY_N_FRAMES == 0
            )

            # joint_state для Web UI
            with state.joint_state_lock:
                state.joint_state.clear()

            if result.pose_landmarks:
                people_present = len(result.pose_landmarks)

                for person_idx, landmarks in enumerate(result.pose_landmarks):
                    color = config.PERSON_COLORS[person_idx % len(config.PERSON_COLORS)]

                    for lm_idx, name in config.LANDMARK_NAMES.items():
                        lm = landmarks[lm_idx]

                        a = config.SMOOTHING_ALPHA
                        x = state.smooth_val(f"p{person_idx}_{name}_x", round(lm.x, 4), a)
                        y = state.smooth_val(f"p{person_idx}_{name}_y", round(lm.y, 4), a)
                        z = state.smooth_val(f"p{person_idx}_{name}_z", round(lm.z, 4), a)
                        visibility = state.smooth_val(
                            f"p{person_idx}_{name}_vis",
                            round(getattr(lm, "visibility", 1.0), 4), a)

                        with state.joint_state_lock:
                            state.joint_state[name] = {"x": x, "y": y, "z": z, "vis": visibility}

                        osc.send(f"/pose/{person_idx}/{name}", [x, y, z, visibility])

                        # Ableton маппинг
                        if person_idx == 0:
                            ableton_mod.apply_mapping(ableton_client, name, x, y, z, visibility)

                        if state.runtime["send_osc_flat"]:
                            base = f"/pose/{person_idx}/{name}"
                            osc.send(f"{base}/x", x)
                            osc.send(f"{base}/y", y)
                            osc.send(f"{base}/z", z)
                            osc.send(f"{base}/vis", visibility)

                        if should_print:
                            print(f"person {person_idx} | {name:>14}: x={x:.3f} y={y:.3f} z={z:.3f}")

                    # жесты (только 0-й человек)
                    pose_tracker.check_gestures(person_idx, landmarks, osc)

                    if config.SHOW_PREVIEW:
                        pose_mod.draw_person_skeleton(
                            display_frame, landmarks, color,
                            joint_names=config.LANDMARK_NAMES,
                            show_coords=state.runtime["show_coords"]
                        )

            if prev_people_present != people_present:
                osc.send("/pose/presence", people_present)
                prev_people_present = people_present

            osc.send("/pose/count", people_present)

            h, w = display_frame.shape[:2]

            # ---- ленивые стрим-кадры (один раз за кадр) ----
            stream_cache = {}

            def get_stream_frame(sid):
                if sid in stream_cache:
                    return stream_cache[sid]
                if sid == "skeleton":
                    out = display_frame
                elif sid == "rgb":
                    out = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                elif sid == "depth":
                    out = cv2.resize(mask_mod.depth_to_display(depth_mm), (w, h)) \
                        if depth_mm is not None else \
                        __import__("numpy").zeros((h, w, 3), dtype=__import__("numpy").uint8)
                elif sid == "ir":
                    if depth_mm is not None:
                        ir = (depth_mm / 16).clip(0, 255).astype("uint8")
                        out = cv2.cvtColor(ir, cv2.COLOR_GRAY2BGR)
                    else:
                        out = __import__("numpy").zeros((h, w, 3), dtype=__import__("numpy").uint8)
                elif sid == "mask":
                    m = mask_mod.best_mask(h, w, depth_mm, mp_image, timestamp_ms, result)
                    out = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
                else:
                    out = display_frame
                stream_cache[sid] = out
                return out

            # ---- локальное превью: копия + UI (не уходит наружу) ----
            if config.SHOW_PREVIEW:
                preview_sid = state.runtime.get("preview_tab_stream", "skeleton")
                preview_frame = get_stream_frame(preview_sid).copy()
                panel.draw_control_panel(preview_frame, state.runtime, h, w)
                cv2.putText(preview_frame, f"FPS: {current_fps}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.putText(preview_frame, f"People: {people_present}", (10, 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.imshow("Kinekt360 — [TAB] Panel  [Q] Quit", preview_frame)

            if depth_mm is not None:
                cv2.imshow("Depth / IR", mask_mod.depth_to_display(depth_mm))

            # ---- Syphon: всегда чистые данные ----
            for sid in syphon_out.servers:
                if state.runtime.get(f"stream_{sid}", False):
                    syphon_out.publish(sid, get_stream_frame(sid))

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("\t") or key == 9:
                state.runtime["panel_open"] = not state.runtime["panel_open"]
            elif key == 81 or key == 2424832:  # left arrow
                state.runtime["preview_tab"] = max(0, state.runtime["preview_tab"] - 1)
            elif key == 83 or key == 2555904:  # right arrow
                state.runtime["preview_tab"] = min(2, state.runtime["preview_tab"] + 1)
            elif camera_mode == "kinect":
                tilt = state.runtime["tilt"]
                if tilt != current_tilt:
                    current_tilt = max(-30, min(30, tilt))
                    source.set_tilt(current_tilt)
    finally:
        pose_tracker.close()
        cv2.destroyAllWindows()
        syphon_out.stop_all()
        source.close()


if __name__ == "__main__":
    main()
