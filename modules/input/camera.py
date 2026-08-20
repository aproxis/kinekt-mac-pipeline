"""Источники кадров: Kinect и Webcam за общим интерфейсом FrameSource.

Всё остальное приложение не знает, Kinect это или вебка:
  source.read() -> Frame(frame_bgr, display_frame, depth_mm) | None
    frame_bgr     — НЕотзеркаленный BGR (для MediaPipe — left/right не путаются)
    display_frame — зеркальный BGR (для превью/скелета)
    depth_mm      — глубина или None
  source.set_tilt(deg), source.has_depth, source.close()
"""
from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np

import state


@dataclass
class Frame:
    frame_bgr: np.ndarray       # для MediaPipe (неотзеркаленный)
    display_frame: np.ndarray   # для превью (зеркальный)
    depth_mm: Optional[np.ndarray]


class FrameSource(ABC):
    has_depth: bool = False

    @abstractmethod
    def read(self) -> Optional[Frame]:
        pass

    @abstractmethod
    def set_tilt(self, angle_deg: int) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


def video_callback(dev, data, timestamp):
    with state.frame_lock:
        state.latest_rgb = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)


def depth_callback(dev, data, timestamp):
    with state.frame_lock:
        state.latest_depth = data.copy()


class KinectSource(FrameSource):
    def __init__(self, initial_tilt: int):
        import freenect
        self._freenect = freenect
        self.ctx = None
        self.dev = None
        self.has_depth = True
        self._tilt = initial_tilt
        self._open()

    def _open(self):
        f = self._freenect
        ctx = f.init()
        if not ctx:
            raise RuntimeError("Не удалось получить контекст freenect")
        dev = f.open_device(ctx, 0)
        if not dev:
            f.shutdown(ctx)
            raise RuntimeError("Не удалось открыть устройство Kinect")

        f.set_video_mode(dev, f.RESOLUTION_MEDIUM, f.VIDEO_RGB)
        f.set_depth_mode(dev, f.RESOLUTION_MEDIUM, f.DEPTH_MM)
        f.set_video_callback(dev, video_callback)
        f.set_depth_callback(dev, depth_callback)
        f.set_tilt_degs(dev, self._tilt)
        print(f"Tilt выставлен: {self._tilt}°")
        f.start_video(dev)
        f.start_depth(dev)

        self.ctx, self.dev = ctx, dev

    def read(self) -> Optional[Frame]:
        self._freenect.process_events(self.ctx)
        with state.frame_lock:
            rgb = state.latest_rgb
            depth = state.latest_depth
        if rgb is None or depth is None:
            return None

        frame_bgr = rgb                       # неотзеркаленный — для MediaPipe
        depth_mm_raw = cv2.flip(depth, 1)
        display_frame = cv2.flip(frame_bgr, 1)  # зеркальный — для превью
        return Frame(frame_bgr, display_frame, depth_mm_raw)

    def set_tilt(self, angle_deg: int) -> None:
        self._tilt = max(-30, min(30, angle_deg))
        self._freenect.set_tilt_degs(self.dev, self._tilt)

    def close(self):
        if self.dev:
            self._freenect.stop_video(self.dev)
            self._freenect.stop_depth(self.dev)
            self._freenect.close_device(self.dev)
        if self.ctx:
            self._freenect.shutdown(self.ctx)
        self.dev = self.ctx = None


class WebcamSource(FrameSource):
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Не удалось открыть вебку")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.has_depth = False

    def read(self) -> Optional[Frame]:
        ret, frame_bgr = self.cap.read()
        if not ret:
            return None
        return Frame(frame_bgr, cv2.flip(frame_bgr, 1), None)

    def set_tilt(self, angle_deg: int) -> None:
        pass

    def close(self):
        self.cap.release()


def create_camera(camera_source: str, initial_tilt: int) -> FrameSource:
    """auto: пробуем Kinect, при неудаче — webcam."""
    if camera_source in ("kinect", "auto"):
        try:
            src = KinectSource(initial_tilt)
            state.camera_mode = "kinect"
            return src
        except Exception as e:
            if camera_source == "kinect":
                raise
            print(f"Kinect не найден ({e}), пробую webcam")

    src = WebcamSource()
    state.camera_mode = "webcam"
    print("Режим: webcam (MacBook камера) — без depth/тилта")
    return src
