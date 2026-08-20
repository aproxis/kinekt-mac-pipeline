"""OpenCV-панель управления поверх превью. Только рисование и клики — никакой логики."""
import cv2

import config
import state


def draw_control_panel(frame, rt, h, w):
    if not rt["panel_open"]:
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, h - 40), (140, h - 5), (30, 30, 30), -1)
        cv2.putText(overlay, "[TAB] Panel  [←→] Tabs", (18, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        return

    tab = rt.get("preview_tab", 0)
    tabs = ["STREAMS", "SYSTEM", "OUTPUT"]
    pw, ph = 300, 360
    px, py = 10, 10

    overlay = frame.copy()
    cv2.rectangle(overlay, (px, py), (px + pw, py + ph), (20, 20, 30), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    cv2.rectangle(frame, (px, py), (px + pw, py + ph), (60, 60, 80), 1)

    # tabs row
    xo = px + 6
    for i, t in enumerate(tabs):
        act = i == tab
        bg = (50, 60, 80) if act else (30, 30, 40)
        tw = 80
        cv2.rectangle(frame, (xo + i * (tw + 4), py + 4), (xo + i * (tw + 4) + tw, py + 22), bg, -1)
        cv2.putText(frame, t, (xo + i * (tw + 4) + 6, py + 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 220, 240) if act else (120, 120, 140), 1, cv2.LINE_AA)
        rt[f"_rect_tab_{i}"] = (xo + i * (tw + 4), py + 4, tw, 18)

    y0 = py + 30
    if tab == 0:
        y = y0
        y = _btn(frame, "Syphon Outputs", None, px + 8, y, 120, 18)
        y = _sep(frame, px + 8, y, pw - 16)
        for sid, sinfo in config.SYPHON_STREAMS.items():
            key = f"stream_{sid}"
            y = _toggle(frame, sinfo["label"], rt, key, px + 12, y, pw - 24, 20)
            y += 2
        y = _sep(frame, px + 8, y, pw - 16)
        y = _btn(frame, "Preview tab:", None, px + 8, y, 90, 18)
        y += 2
        for idx, (sid, sinfo) in enumerate(config.SYPHON_STREAMS.items()):
            key = f"preview_{sid}"
            sel = sid == rt.get("preview_tab_stream", "skeleton")
            bg = (50, 80, 60) if sel else (35, 35, 45)
            xp = px + 12 + idx * (48 + 4)
            cv2.rectangle(frame, (xp, y), (xp + 48, y + 20), bg, -1)
            cv2.rectangle(frame, (xp, y), (xp + 48, y + 20), (70, 70, 70), 1)
            cv2.putText(frame, sinfo["label"][:4], (xp + 3, y + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA)
            rt[f"_rect_preview_{sid}"] = (xp, y, 48, 20)
        y += 26
    elif tab == 1:
        y = y0
        y = _btn(frame, "Camera", None, px + 8, y, 60, 18)
        cam_row_y = y - 22
        rt["cam_kinect"] = (state.camera_mode == "kinect")
        rt["cam_webcam"] = (state.camera_mode == "webcam")
        _toggle(frame, "Kinect", rt, "cam_kinect", px + 70, cam_row_y, 60, 18)
        _toggle(frame, "Webcam", rt, "cam_webcam", px + 135, cam_row_y, 60, 18)
        y = _sep(frame, px + 8, y, pw - 16)
        y = _btn(frame, "Track:", None, px + 8, y, 55, 18)
        y = _slider(frame, rt, "num_poses", px + 65, y - 18, 100, 18, 1, 4, 1)
        y = _sep(frame, px + 8, y, pw - 16)
        y = _btn(frame, "Tilt:", None, px + 8, y, 40, 18)
        y = _slider(frame, rt, "tilt", px + 50, y - 18, 150, 18, -30, 30, 5)
        y = _sep(frame, px + 8, y, pw - 16)
        y = _btn(frame, "Display:", None, px + 8, y, 65, 18)
        y = _toggle(frame, "Coords", rt, "show_coords", px + 75, y - 18, 60, 18)
    elif tab == 2:
        y = y0
        y = _btn(frame, "OSC Output", None, px + 8, y, 90, 18)
        y = _sep(frame, px + 8, y, pw - 16)
        y = _toggle(frame, "Joints", rt, "send_osc", px + 12, y, pw - 24, 20)
        y = _toggle(frame, "Flat", rt, "send_osc_flat", px + 12, y + 2, pw - 24, 20)
        y = _toggle(frame, "Gestures", rt, "send_gestures", px + 12, y + 4, pw - 24, 20)


def _btn(frame, label, _u, x, y, w, h):
    cv2.putText(frame, label, (x + 2, y + 13),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (140, 140, 160), 1, cv2.LINE_AA)
    return y + h + 4


def _toggle(frame, label, rt, key, x, y, w, h):
    val = rt.get(key, False)
    bg = (40, 80, 50) if val else (45, 40, 40)
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (80, 80, 80), 1)
    c = (180, 255, 180) if val else (180, 150, 150)
    cv2.putText(frame, label, (x + 3, y + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, c, 1, cv2.LINE_AA)
    rt[f"_rect_{key}"] = (x, y, w, h)
    return y + h + 2


def _slider(frame, rt, key, x, y, w, h, vmin, vmax, step):
    val = rt.get(key, vmin)
    pct = (val - vmin) / (vmax - vmin)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (35, 35, 45), -1)
    fw = int(w * pct)
    cv2.rectangle(frame, (x, y), (x + fw, y + h), (50, 80, 120), -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (80, 80, 80), 1)
    cv2.putText(frame, str(val), (x + 3, y + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 220), 1, cv2.LINE_AA)
    rt[f"_rect_{key}"] = (x, y, w, h)
    return y + h + 2


def _sep(frame, x, y, w):
    cv2.line(frame, (x, y), (x + w, y), (50, 50, 55), 1)
    return y + 3


def handle_click(rt, key, x, y):
    for k, v in list(rt.items()):
        if not k.startswith("_rect_"):
            continue
        rx, ry, rw, rh = v
        vname = k.replace("_rect_", "")
        if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
            continue

        if vname.startswith("tab_"):
            rt["preview_tab"] = int(vname.split("_")[1])
            return True
        if vname.startswith("preview_"):
            rt["preview_tab_stream"] = vname.replace("preview_", "")
            return True
        if vname.startswith("stream_"):
            rt[vname] = not rt.get(vname, False)
            return True
        if vname in ("cam_kinect", "cam_webcam"):
            print("Переключение камеры на лету не поддерживается — перезапусти скрипт с другим источником.")
            return True
        if vname in ("send_osc", "send_osc_flat", "send_gestures", "show_coords"):
            rt[vname] = not rt.get(vname, False)
            return True
        if vname == "num_poses":
            rt["num_poses"] = rt.get("num_poses", 2) % 4 + 1
            print(f"Track: {rt['num_poses']} — применится только при перезапуске скрипта "
                  f"(PoseLandmarker создаётся один раз при старте)")
            return True
        if vname == "tilt":
            rt["tilt"] = (rt.get("tilt", 0) + 5) % 65 - 30
            return True
    return False


def create_preview_window():
    if config.SHOW_PREVIEW:
        cv2.namedWindow("Kinekt360 — [TAB] Panel  [Q] Quit")
        cv2.moveWindow("Kinekt360 — [TAB] Panel  [Q] Quit", 50, 50)


def setup_mouse():
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.runtime["mouse_down"] = True
            handle_click(state.runtime, "click", x, y)
        elif event == cv2.EVENT_MOUSEMOVE and state.runtime.get("mouse_down"):
            for k, v in list(state.runtime.items()):
                if not k.startswith("_rect_"):
                    continue
                var_name = k.replace("_rect_", "")
                if var_name in ("tilt",):
                    rx, ry, rw, rh = v
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        pct = max(0, min(1, (x - rx) / rw))
                        state.runtime[var_name] = round(-30 + pct * 60)
        elif event == cv2.EVENT_LBUTTONUP:
            state.runtime["mouse_down"] = False

    if config.SHOW_PREVIEW:
        cv2.setMouseCallback("Kinekt360 — [TAB] Panel  [Q] Quit", mouse_callback)
