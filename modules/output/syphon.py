"""Syphon: серверы для всех стримов + публикация кадра."""
import numpy as np
import cv2

import config
import state

try:
    import syphon
    from syphon.utils.numpy import copy_image_to_mtl_texture
    from syphon.utils.raw import create_mtl_texture
    SYPHON_AVAILABLE = True
except ImportError:
    SYPHON_AVAILABLE = False


class SyphonOutput:
    def __init__(self):
        self.servers = {}     # sid -> server
        self.textures = {}    # sid -> mtl texture

        if not config.SEND_SYPHON:
            return
        if not SYPHON_AVAILABLE:
            print("syphon-python не установлен -- Syphon-вывод отключён")
            return

        for sid, sinfo in config.SYPHON_STREAMS.items():
            try:
                sv = syphon.SyphonMetalServer(sinfo["name"])
                self.servers[sid] = sv
                self.textures[sid] = None
                print(f"  Syphon: {sinfo['name']}")
            except Exception as e:
                print(f"  Syphon {sinfo['name']} error: {e}")

    def publish(self, sid, frame_bgr):
        """Отправляет BGR-кадр в Syphon-стрим (если включён в панели)."""
        sv = self.servers.get(sid)
        if sv is None or not state.runtime.get(f"stream_{sid}", False):
            return
        h, w = frame_bgr.shape[:2]
        if self.textures[sid] is None:
            self.textures[sid] = create_mtl_texture(sv.device, w, h)
        rgba = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGBA)
        copy_image_to_mtl_texture(rgba, self.textures[sid])
        sv.publish_frame_texture(self.textures[sid])

    def stop_all(self):
        for sv in self.servers.values():
            try:
                sv.stop()
            except Exception:
                pass
