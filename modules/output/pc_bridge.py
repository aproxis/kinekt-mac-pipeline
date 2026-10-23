"""PlayCanvas bridge: OSC (UDP 9002) -> WebSocket (8091) JSON.

Отдельный потребитель: не меняет адреса/поведение существующего моста
(Resolume :7000, monitor :9001, Ableton :11000). Запуск автономный:

    ./venv/bin/python -m modules.output.pc_bridge

Протокол сообщения (30 Гц):
    {"type":"pose","count":2,"fps":30,"ts":..., "people":[
        {"id":0,"present":true,
         "hands":{"left":[x,y,z,vis],"right":[x,y,z,vis]},
         "head":[x,y,z,vis]}]}
Координаты — нормализованные MediaPipe (0..1, y вниз), как в /pose/{i}/{joint}.
"""
from __future__ import annotations

import base64
import hashlib
import json
import socket
import socketserver
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler

from pythonosc import dispatcher, osc_server

WS_HOST = "127.0.0.1"
WS_PORT = 8091
OSC_LISTEN_PORT = 9002
SEND_HZ = 30.0
STALE_AFTER = 2.0

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

_lock = threading.Lock()
_people: dict[int, dict] = {}
_count = 0
_fps = 0
_last_pose_at = 0.0
_clients: set = set()
_clients_lock = threading.Lock()


def _parse_pose(address: str, *args) -> None:
    global _last_pose_at
    parts = address.strip("/").split("/")
    if len(parts) != 3:
        return
    try:
        person = int(parts[1])
    except ValueError:
        return
    joint = parts[2]
    if joint in ("x", "y", "z", "vis"):
        return
    if len(args) < 3:
        return
    x, y, z = (float(v) for v in args[:3])
    vis = float(args[3]) if len(args) > 3 else 1.0
    with _lock:
        rec = _people.setdefault(person, {"joints": {}, "present": True})
        rec["joints"][joint] = [x, y, z, vis]
        _last_pose_at = time.time()


def _parse_count(address: str, *args) -> None:
    global _count
    if not args:
        return
    try:
        _count = int(args[0])
    except (TypeError, ValueError):
        return
    with _lock:
        for person in list(_people):
            if person >= _count:
                _people.pop(person, None)


def _parse_fps(address: str, *args) -> None:
    global _fps
    if args:
        try:
            _fps = int(args[0])
        except (TypeError, ValueError):
            pass


def _snapshot() -> dict:
    now = time.time()
    with _lock:
        fresh = (now - _last_pose_at) <= STALE_AFTER
        people = []
        by_id = sorted(_people.items())
        for person_id, rec in by_id:
            if person_id >= 4:
                continue
            joints = rec["joints"]
            entry = {
                "id": person_id,
                "present": bool(fresh and rec.get("present")),
                "hands": {
                    "left": joints.get("left_wrist"),
                    "right": joints.get("right_wrist"),
                },
                "head": joints.get("nose"),
            }
            people.append(entry)
        return {
            "type": "pose",
            "count": _count if fresh else 0,
            "fps": _fps,
            "ts": int(now * 1000),
            "people": people,
        }


def _osc_thread() -> None:
    disp = dispatcher.Dispatcher()
    disp.map("/pose/*/*", _parse_pose)
    disp.map("/pose/count", _parse_count)
    disp.map("/fps", _parse_fps)
    server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", OSC_LISTEN_PORT), disp)
    print(f"[pc-bridge] OSC listening on udp://127.0.0.1:{OSC_LISTEN_PORT}", flush=True)
    server.serve_forever()


def _ws_send(client: socket.socket, payload: bytes) -> None:
    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack(">H", length)
    else:
        header.append(127)
        header += struct.pack(">Q", length)
    client.sendall(bytes(header) + payload)


def _ws_recv(client: socket.socket) -> bool:
    """Читает кадр клиента; True — соединение живо."""
    try:
        first = client.recv(2)
        if len(first) < 2:
            return False
        opcode = first[0] & 0x0F
        masked = bool(first[1] & 0x80)
        length = first[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", client.recv(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", client.recv(8))[0]
        mask = client.recv(4) if masked else b""
        data = b""
        while len(data) < length:
            chunk = client.recv(length - len(data))
            if not chunk:
                return False
            data += chunk
        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 0x8:
            return False
        if opcode == 0x9:
            client.sendall(b"\x8a" + bytes([len(data)]) + data)
        return True
    except OSError:
        return False


class _WSHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            raw = b""
            while b"\r\n\r\n" not in raw and len(raw) < 16384:
                chunk = self.rfile.readline()
                if not chunk:
                    return
                raw += chunk
            headers = {}
            for line in raw.decode("latin-1").split("\r\n")[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            key = headers.get("sec-websocket-key")
            if not key:
                self.wfile.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode()).digest()
            ).decode()
            self.wfile.write(
                (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
                ).encode()
            )
            self.wfile.flush()
            client = self.connection
            with _clients_lock:
                _clients.add(client)
            self.server.on_client_connected()
            print("[pc-bridge] scene connected", flush=True)
            while _ws_recv(client):
                pass
        except Exception as exc:  # noqa: BLE001
            print(f"[pc-bridge] client error: {exc}", flush=True)
        finally:
            with _clients_lock:
                _clients.discard(self.connection)


class _WSServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def on_client_connected(self) -> None:
        pass


def _broadcast_loop() -> None:
    interval = 1.0 / SEND_HZ
    dead = []
    while True:
        payload = json.dumps(_snapshot(), separators=(",", ":")).encode()
        with _clients_lock:
            targets = list(_clients)
        for client in targets:
            try:
                _ws_send(client, payload)
            except OSError:
                dead.append(client)
        if dead:
            with _clients_lock:
                for client in dead:
                    _clients.discard(client)
            dead.clear()
        time.sleep(interval)


def main() -> None:
    threading.Thread(target=_osc_thread, daemon=True).start()
    threading.Thread(target=_broadcast_loop, daemon=True).start()
    server = _WSServer((WS_HOST, WS_PORT), _WSHandler)
    print(f"[pc-bridge] WebSocket ws://{WS_HOST}:{WS_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[pc-bridge] stopped", flush=True)


if __name__ == "__main__":
    main()
