"""AbletonOSC: запросы, сканер, AbletonGuard, применение маппинга."""
import socket
import threading
import time

from pythonosc import osc_message
from pythonosc.osc_message_builder import OscMessageBuilder

import config
import state

ableton_socket_lock = threading.Lock()   # сериализация доступа к порту 11001


def ableton_query(address, *args, timeout=4):
    with ableton_socket_lock:
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
            sender.sendto(builder.build().dgram, (config.ABLETON_OSC_IP, config.ABLETON_OSC_PORT))
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
    state.ableton_scanning = True
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
        state.ableton_scanning = False


class AbletonGuard:
    """Защита от переспама: структурная валидация + rate limit + backoff."""

    def __init__(self):
        self.valid_targets = set()       # {(track, device, param)}
        self.last_validate = 0.0
        self.validate_interval = 30.0
        self.last_sent = {}
        self.min_interval = 0.05
        self.msg_times = []
        self.max_msg_per_sec = 60
        self.backoff_until = 0.0
        self.backoff_seconds = 5.0
        self.status = "unknown"          # unknown | ok | backoff | live_offline
        self.invalid_mappings = set()

    def validate(self, force=False):
        now = time.time()
        if not force and now - self.last_validate < self.validate_interval:
            return
        self.last_validate = now

        try:
            r = ableton_query("/live/song/get/num_tracks", timeout=2)
            # Ableton не ответил — НЕ затираем старые targets (иначе все маппинги
            # станут invalid до следующей удачной валидации)
            if r is None:
                self.status = "live_offline"
                return

            num_tracks = int(r.params[-1])
            targets = set()
            for t in range(num_tracks):
                r = ableton_query("/live/track/get/num_devices", t, timeout=2)
                num_dev = int(r.params[-1]) if r else 0
                for d in range(num_dev):
                    r = ableton_query("/live/device/get/num_parameters", t, d, timeout=2)
                    num_p = int(r.params[-1]) if r else 0
                    for p in range(num_p):
                        targets.add((t, d, p))
            self.valid_targets = targets
            self.status = "ok"
        except Exception:
            self.status = "live_offline"

        with state.mappings_lock:
            self.invalid_mappings = {
                m["id"] for m in state.live_mappings
                if (m.get("track", 0), m.get("device", 0), m.get("param", 0)) not in self.valid_targets
            }

    def can_send(self, m):
        now = time.time()
        if now < self.backoff_until:
            return False
        if (m.get("track", 0), m.get("device", 0), m.get("param", 0)) not in self.valid_targets:
            return False
        last = self.last_sent.get(m.get("id"))
        if last is not None and now - last < self.min_interval:
            return False
        self.msg_times = [t for t in self.msg_times if now - t < 1.0]
        if len(self.msg_times) >= self.max_msg_per_sec:
            return False
        return True

    def mark_sent(self, m):
        now = time.time()
        self.last_sent[m.get("id")] = now
        self.msg_times.append(now)

    def peek_errors(self):
        if self.backoff_until > time.time():
            return
        now = time.time()
        if not self.msg_times or now - self.msg_times[-1] > 0.5:
            return
        with ableton_socket_lock:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", 11001))
                s.setblocking(False)
                try:
                    # дренируем ВЕСЬ буфер: ошибка → backoff, но старый мусор
                    # не должен ретриггерить backoff каждые 5 сек
                    while True:
                        data, _ = s.recvfrom(65535)
                        parsed = osc_message.OscMessage(data)
                        if parsed.address == "/live/error":
                            self.backoff_until = time.time() + self.backoff_seconds
                            self.status = "backoff"
                            print(f"[AbletonGuard] Ошибка AbletonOSC, пауза {self.backoff_seconds}с")
                except (BlockingIOError, socket.timeout):
                    pass
                finally:
                    s.close()
            except Exception:
                pass

    def status_dict(self):
        return {
            "status": self.status,
            "valid_targets": len(self.valid_targets),
            "invalid_mappings": sorted(self.invalid_mappings),
            "backoff_until": self.backoff_until,
            "msg_per_sec_limit": self.max_msg_per_sec,
        }


ableton_guard = AbletonGuard()


def apply_mapping(ableton_client, joint_name, x, y, z, visibility):
    """Применяет все маппинги для данного сустава к Ableton (guard + сглаживание)."""
    if ableton_client is None or state.ableton_scanning:
        return

    with state.mappings_lock:
        mappings = list(state.live_mappings)

    for m in mappings:
        if m["joint"] != joint_name:
            continue
        val = {"x": x, "y": y, "z": z, "vis": visibility}.get(m["axis"])
        if val is None:
            continue

        smoothing = m.get("smoothing", config.SMOOTHING_ALPHA)
        threshold = m.get("threshold", 0)
        skey = f"ableton_{m['id']}"
        sval = state.smooth_val(skey, val, smoothing)

        if m.get("invert", False):
            sval = 1.0 - sval

        scale = m.get("scale", 1.0)
        pmin = m.get("min", 0.0)
        pmax = m.get("max", 1.0)
        if scale != 1.0:
            sval = max(0.0, min(1.0, sval * scale))
        sval = pmin + max(0.0, min(1.0, sval)) * (pmax - pmin)

        last = state.last_sent.get(skey)
        if threshold and last is not None and abs(sval - last) < threshold:
            continue
        if not ableton_guard.can_send(m):
            continue

        state.last_sent[skey] = sval
        ableton_guard.mark_sent(m)
        ableton_client.send_message(
            "/live/device/set/parameter/value",
            [m["track"], m["device"], m["param"], sval]
        )
