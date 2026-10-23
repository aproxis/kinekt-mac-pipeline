"""Headless-фидер: FaceTime-камера -> MediaPipe -> OSC (/pose/...).

Используется как фоллбэк без Kinect. Не меняет main.py и существующий мост:
пишет те же адреса через modules.output.osc.OscOutput (Resolume, monitor :9001,
PlayCanvas bridge :9002).

Запуск:
    ./venv/bin/python tools/webcam_pose_feed.py --people 4
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import mediapipe as mp

import config
import state
from modules.input import camera as camera_mod
from modules.output import osc as osc_mod
from modules.process import pose as pose_mod


def main() -> None:
    parser = argparse.ArgumentParser(description="FaceTime camera -> OSC pose feed")
    parser.add_argument("--people", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--camera", type=int, default=0, help="cv2 camera index")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    state.runtime["num_poses"] = args.people
    source = camera_mod.WebcamSource(args.camera)
    tracker = pose_mod.PoseTracker(args.people)
    osc = osc_mod.OscOutput()

    print(f"[webcam-feed] camera={args.camera} people={args.people} "
          f"-> OSC monitor :{config.MONITOR_OSC_PORT} + bridge :{config.PC_BRIDGE_OSC_PORT}")

    started = time.time()
    frames = 0
    fps_timer = time.time()
    fps = 0
    prev_count = -1

    try:
        while True:
            frame = source.read()
            if frame is None:
                print("[webcam-feed] camera lost")
                break

            rgb = cv2.cvtColor(frame.frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int((time.time() - started) * 1000)
            result = tracker.detect(mp_image, timestamp_ms)

            count = len(result.pose_landmarks) if result.pose_landmarks else 0

            for person_idx, landmarks in enumerate(result.pose_landmarks or []):
                for lm_idx, name in config.LANDMARK_NAMES.items():
                    lm = landmarks[lm_idx]
                    vis = float(getattr(lm, "visibility", 1.0))
                    osc.send(
                        f"/pose/{person_idx}/{name}",
                        [round(lm.x, 4), round(lm.y, 4), round(lm.z, 4), round(vis, 4)],
                    )

            if count != prev_count:
                osc.send("/pose/presence", count)
                prev_count = count
            osc.send("/pose/count", count)

            frames += 1
            now = time.time()
            if now - fps_timer >= 1.0:
                fps = frames
                frames = 0
                fps_timer = now
                osc.send("/fps", fps)
                if not args.quiet:
                    print(f"[webcam-feed] fps={fps} people={count}", flush=True)
    except KeyboardInterrupt:
        print("[webcam-feed] stopped")
    finally:
        tracker.close()
        source.close()


if __name__ == "__main__":
    main()
