"""HTTP сервер Web UI. Запускается явно через start_web_server() — без side-effects на импорте."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import config
import state
import profiles
from modules.output import ableton


def start_web_server():
    def make_handler():
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/api/joints":
                    with state.joint_state_lock:
                        data = dict(state.joint_state)
                    self.send_json(data)

                elif path == "/api/mappings":
                    with state.mappings_lock:
                        self.send_json(state.live_mappings)

                elif path == "/api/profiles":
                    self.send_json(profiles.list_profiles())

                elif path == "/api/profiles/current":
                    with state.mappings_lock:
                        self.send_json({"name": state.current_profile, "mappings": state.live_mappings})

                elif path == "/api/ableton/scan":
                    ableton.ableton_guard.validate(force=True)
                    self.send_json(ableton.scan_ableton())

                elif path == "/api/ableton/status":
                    self.send_json(ableton.ableton_guard.status_dict())

                elif path == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    try:
                        with open(config.WEB_INDEX) as f:
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
                    profiles.save_mappings(data)
                    self.send_json({"ok": True})

                elif self.path == "/api/profiles/load":
                    name = data.get("name")
                    if not name:
                        self.send_json({"error": "name required"}, 400)
                    elif profiles.load_profile(name) is None:
                        self.send_json({"error": f"profile '{name}' not found"}, 404)
                    else:
                        self.send_json({"ok": True, "name": name})

                elif self.path == "/api/profiles/save":
                    name = data.get("name")
                    mappings = data.get("mappings")
                    if not name or mappings is None:
                        self.send_json({"error": "name and mappings required"}, 400)
                    profiles.save_as_profile(name, mappings)
                    self.send_json({"ok": True, "name": name})

                else:
                    self.send_json({"error": "not found"}, 404)

            def do_DELETE(self):
                parsed = urlparse(self.path)
                if parsed.path == "/api/profiles":
                    query = parse_qs(parsed.query)
                    name = query.get("name", [None])[0]
                    if not name:
                        self.send_json({"error": "name required"}, 400)
                    elif profiles.delete_profile(name):
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

        return Handler

    try:
        server = HTTPServer((config.WEB_HOST, config.WEB_PORT), make_handler())
    except OSError as e:
        print(f"Web UI: НЕ УДАЛОСЬ поднять сервер на :{config.WEB_PORT} — {e} "
              f"(порт занят? используй другой WEB_PORT в config.py)")
        return
    print(f"Web UI: http://localhost:{config.WEB_PORT}")
    server.serve_forever()