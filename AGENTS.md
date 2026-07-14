# Kinekt360 — Kinect on Mac Pipeline

## Overview

Kinekt360 is a modular pipeline for:
1. **Input** — reading data from Kinect v1/v2 via `libfreenect` on macOS
2. **Process** — computer vision, skeleton/pose tracking via MediaPipe, depth analysis
3. **Output** — real-time streaming to creative tools via OSC (Resolume), Syphon, Chataigne

## Pipeline Architecture

```
[Input]            [Process]           [Output]
─────────          ─────────           ─────────────
Kinect RGB  ────▶  MediaPipe Pose  ──▶ OSC → Resolume (:7000)
Kinect Depth ────▶ Depth Processing  ─▶ OSC → Chataigne (:9001) → Resolume
                  (silhouette mask)    Syphon (video frame in Resolume)
                                       Protokol (OSC monitor :9001)
```

Every stage is a standalone module. Stages communicate via queues / shared memory / callbacks — NOT hardcoded function chains.

## Version History

| Script | Key features |
|--------|-------------|
| `pose_to_osc.py` | Sync API (`sync_get_video/depth`), tilt via separate device handle — конфликты USB |
| `pose_to_osc_2.py` | Retry-механика при ошибках чтения кадра |
| `pose_to_osc_3.py` | **Callback-based capture**, единый `open_device()` на всё время, тилт без LIBUSB_ERROR_ACCESS |
| `pose_to_osc_4.py` | Dual OSC (Resolume + Protokol), **Syphon** video streaming |
| `pose_to_osc_5.py` | Flat OSC адреса (`/pose/0/nose/x`), non-blocking сокеты |
| **`pose_to_osc_6.py`** | Smoothing, жесты (`/gesture/0/right_hand_up`), FPS, **webcam fallback** |
| `pose_to_osc_7.py` | Per-mapping smoothing/threshold, profiles system, Web UI (joints → param tree → mappings), manual VST3 param mapping |

## Current State (July 2026)

- **pose_to_osc_6.py** — текущий рабочий скрипт
- Callback-based захват через `video_callback`/`depth_callback` + `freenect.process_events()`
- Dual OSC: Resolume на `192.168.1.5:7000` + локальный порт `9001` для Chataigne/Protokol
- Syphon-сервер `KinectSkeleton` — живое видео с масками и скелетом в Resolume
- Non-blocking сокеты — не крешится при отсутствии Resolume
- Smoothing координат — экспоненциальный фильтр (SMOOTHING_ALPHA)
- Жесты — `/gesture/0/right_hand_up`, `/gesture/0/right_hand_down`
- FPS — счётчик на превью + OSC `/fps`
- Присутствие — `/pose/presence` при входе/выходе человека из кадра
- Webcam fallback — если Kinect не подключён, автоматически использует MacBook камеру
- Protokol — мониторинг всех OSC-сообщений в реальном времени
- `pose_landmarker.task` — MediaPipe pose landmarker model
- `freenect-python/` — Python CFFI bindings for libfreenect
- `libfreenect` installed via Homebrew at `/opt/homebrew/lib/`

## Directory Structure

```
Kinekt360/
├── AGENTS.md                  # this file
├── .gitignore
├── pose_to_osc.py             # v1 — sync API
├── pose_to_osc_2.py           # v2 — retries
├── pose_to_osc_3.py           # v3 — callback-based, single handle
├── pose_to_osc_4.py           # v4 — dual OSC + Syphon
├── pose_to_osc_5.py           # v5 — flat OSC + non-blocking
├── pose_to_osc_6.py           # v6 — smoothing, gestures, FPS, webcam (current)
├── pose_landmarker.task       # MediaPipe model (gitignored)
├── freenect-python/           # libfreenect Python bindings
├── venv/                      # Python virtual environment
└── modules/                   # (future) modular pipeline
```

## Development Conventions

- **Language**: Python 3.11+, with type hints (`def foo() -> None:`)
- **Formatting**: `ruff` (line length 100)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Config**: constants at top of script in `# ==== НАСТРОЙКИ ====` block
- **Commits**: conventional commits in English (`feat:`, `fix:`, `refactor:`)
- **Model files** (`.task`) — keep in repo root, added to `.gitignore`

## Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| `libfreenect` | Kinect driver (Homebrew) | ✅ installed |
| `freenect` (Python) | Python bindings (`freenect-python/`) | ✅ installed |
| `mediapipe` | Pose/landmark detection | ✅ installed |
| `opencv-python` | Frame capture & preview | ✅ installed |
| `python-osc` | OSC output | ✅ installed |
| `syphon-python` | Syphon frame output | ✅ installed |
| `pyobjc` | macOS bridge for Syphon | ✅ installed |

## External Tools

| Tool | Purpose |
|------|---------|
| **Resolume Arena** | VJ-микшер, принимает OSC на `:7000` + Syphon-видео |
| **Chataigne** | OSC-транслятор для гибкого маппинга жестов на любые адреса Resolume |
| **Protokol** | OSC-монитор (порт `9001`) — таблица всех входящих сигналов в реальном времени |

## GitHub

- **Repo**: [aproxis/kinekt-mac-pipeline](https://github.com/aproxis/kinekt-mac-pipeline)
