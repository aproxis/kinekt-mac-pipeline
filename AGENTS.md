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

## Version History (история — git tag `pre-refactor`)

| Скрипт | Key features |
|--------|-------------|
| `pose_to_osc.py` | Sync API, tilt через отдельный device handle — конфликты USB |
| `pose_to_osc_2.py` | Retry-механика при ошибках чтения кадра |
| `pose_to_osc_3.py` | **Callback-based capture**, единый `open_device()`, тилт без LIBUSB_ERROR_ACCESS |
| `pose_to_osc_4.py` | Dual OSC (Resolume + Protokol), **Syphon** video streaming |
| `pose_to_osc_5.py` | Flat OSC адреса, non-blocking сокеты |
| `pose_to_osc_6.py` | Smoothing, жесты, FPS, **webcam fallback** |
| `pose_to_osc_7.py` | Per-mapping smoothing/threshold, profiles, Web UI, normalization, invert |
| `pose_to_osc_8.py` | OpenCV-панель управления поверх превью (Tab) |
| `pose_to_osc_9.py` | 5 Syphon-стримов, 3-вкладочная панель, AbletonGuard, selfie-маска |
| **`main.py`** | Модульная архитектура (config/state/profiles/modules) — актуальная |

## Current State (Aug 2026)

- **`main.py`** — точка входа, тонкая оркестрация (~250 строк)
- Callback-based захват через `video_callback`/`depth_callback` + `freenect.process_events()`
- Dual OSC: Resolume на `192.168.1.5:7000` + локальный порт `9001` для Chataigne/Protokol
- Syphon: 5 стримов — `KinectSkeleton`, `KinectRGB`, `KinectDepth`, `KinectIR`, `KinectMask`
- Non-blocking сокеты — не крешится при отсутствии Resolume
- Smoothing координат — экспоненциальный фильтр (SMOOTHING_ALPHA)
- Жесты — `/gesture/0/right_hand_up`, `/gesture/0/right_hand_down`
- FPS — счётчик на превью + OSC `/fps`
- Присутствие — `/pose/presence` при входе/выходе человека из кадра
- Webcam fallback — если Kinect не подключён, автоматически использует MacBook камеру
- **Web UI** (`http://localhost:8090`) — live joints, Ableton scanner, mapping editor, profile manager
  (порт 8090 — 8080 занят локальным nginx)
- **Profiles** — `profiles/*.json`, переключение через dropdown в Web UI
- **Normalization** — joint 0-1 → реальный диапазон параметра (min/max из Ableton)
- **Per-mapping** — smoothing, threshold, scale, invert — каждый mapping настраивается отдельно
- **AbletonGuard** — защита от переспама: структурная валидация + rate limit + backoff
- **Selfie Segmentation** — пиксельная маска для webcam (без depth)
- **Protokol** — мониторинг всех OSC-сообщений в реальном времени

## Directory Structure

```
Kinekt360/
├── AGENTS.md                  # this file
├── .gitignore
├── main.py                    # точка входа (тонкая оркестрация)
├── config.py                  # статические настройки + PROJECT_ROOT
├── state.py                   # разделяемое состояние (runtime, locks)
├── profiles.py                # персистентность профилей маппингов
├── modules/
│   ├── input/
│   │   └── camera.py          # FrameSource: KinectSource / WebcamSource
│   ├── process/
│   │   ├── pose.py            # MediaPipe pose, скелет, жесты
│   │   └── mask.py            # маски: depth / selfie / pose
│   ├── output/
│   │   ├── osc.py             # OSC (Resolume + monitor)
│   │   ├── ableton.py         # AbletonOSC scanner + guard + маппинг
│   │   ├── syphon.py          # 5 Syphon-стримов
│   │   └── webui.py           # HTTP Web UI (start_web_server)
│   └── ui/
│       └── panel.py           # OpenCV-панель управления
├── web/
│   └── index.html             # Web UI фронтенд
├── profiles/                  # JSON-конфиги маппингов
├── pose_landmarker.task       # MediaPipe model (gitignored)
├── selfie_segmentation.tflite # Selfie segmentation (gitignored)
├── freenect-python/           # libfreenect Python bindings
├── unity-kinekt/              # Unity проект (outline trail эффект)
└── venv/                      # Python virtual environment
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
