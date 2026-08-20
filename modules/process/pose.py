"""MediaPipe Pose: детекция, скелет, жесты."""
import cv2

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import config
import state


class PoseTracker:
    def __init__(self, num_poses: int):
        base_options = mp_python.BaseOptions(model_asset_path=config.MODEL_PATH)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=num_poses,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        self.prev_gesture_state = {}

    def detect(self, mp_image, timestamp_ms):
        return self.landmarker.detect_for_video(mp_image, timestamp_ms)

    def check_gestures(self, person_idx, landmarks, osc):
        """Жесты руки (только 0-й человек). Возвращает обновлённый словарь."""
        if person_idx != 0 or not state.runtime["send_gestures"]:
            return
        wrist = landmarks[16]
        shoulder = landmarks[12]
        hip = landmarks[24]

        right_hand_up = 1.0 if wrist.y < shoulder.y else 0.0
        right_hand_down = 1.0 if wrist.y > hip.y else 0.0

        gkey = "p0_right_hand_up"
        if self.prev_gesture_state.get(gkey) != right_hand_up:
            osc.send("/gesture/0/right_hand_up", right_hand_up)
            self.prev_gesture_state[gkey] = right_hand_up

        gkey = "p0_right_hand_down"
        if self.prev_gesture_state.get(gkey) != right_hand_down:
            osc.send("/gesture/0/right_hand_down", right_hand_down)
            self.prev_gesture_state[gkey] = right_hand_down

    def close(self):
        self.landmarker.close()


def draw_person_skeleton(frame, landmarks, color, joint_names=None, show_coords=False):
    h, w = frame.shape[:2]
    pts = [(int((1.0 - lm.x) * w), int(lm.y * h)) for lm in landmarks]
    for a, b in config.POSE_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], color, 2)
    for p in pts:
        cv2.circle(frame, p, 4, color, -1)
    if show_coords and joint_names:
        for lm_idx, name in joint_names.items():
            lm = landmarks[lm_idx]
            x, y = pts[lm_idx]
            label = f"{name} ({lm.x:.2f},{lm.y:.2f},{lm.z:.2f})"
            cv2.putText(frame, label, (x + 6, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
