# Kinekt360 — Kinect on Mac Pipeline

## Overview

Kinekt360 is a modular pipeline for:
1. **Input** — reading data from Kinect v1/v2 via `libfreenect` on macOS
2. **Process** — computer vision, skeleton/pose tracking via MediaPipe, depth analysis
3. **Output** — real-time streaming to creative tools via OSC (Resolume, TouchDesigner), Syphon, WebSocket, MIDI, etc.

## Pipeline Architecture

```
[Input]          [Process]           [Output]
─────────        ─────────           ─────────
Kinect RGB  ──▶  MediaPipe Pose  ──▶ OSC
Kinect Depth ──▶ Depth Processing ──▶ Syphon (frame)
Kinect Audio──▶  Audio Analysis   ──▶ WebSocket
                                      MIDI
                                      NDI
```

Every stage is a standalone module. Stages communicate via queues / shared memory / callbacks — NOT hardcoded function chains.

## Current State (July 2026)

- `pose_to_osc.py` — skeleton tracking via MediaPipe → OSC (Resolume, port 7000)
- `pose_to_osc_2.py` — extended version with configurable landmark filtering
- `pose_landmarker.task` — MediaPipe pose landmarker model
- `freenect-python/` — Python CFFI bindings for libfreenect (cloned)
- `libfreenect` installed via Homebrew at `/opt/homebrew/lib/`

## Directory Structure

```
Kinekt360/
├── AGENTS.md                  # this file
├── .gitignore
├── pose_to_osc.py             # current main script
├── pose_to_osc_2.py           # extended variant
├── pose_landmarker.task       # MediaPipe model (git LFS or ignored)
├── freenect-python/           # libfreenect Python bindings
├── venv/                      # Python virtual environment
└── modules/                   # (future) modular pipeline
    ├── input/                 # Kinect readers
    ├── process/               # CV / ML processors
    └── output/                # OSC, Syphon, WebSocket, MIDI...
```

## Development Conventions

- **Language**: Python 3.11+, with type hints (`def foo() -> None:`)
- **Formatting**: `ruff` (line length 100)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Config**: constants at top of script in `# ==== НАСТРОЙКИ ====` block
- **Commits**: conventional commits in English (`feat:`, `fix:`, `refactor:`)
- **Model files** (`.task`) — keep in repo root, add to `.gitignore` if too large

## Dependencies

| Package | Purpose |
|---------|---------|
| `libfreenect` | Kinect driver (Homebrew) |
| `freenect` (Python) | Python bindings (local `freenect-python/`) |
| `mediapipe` | Pose/landmark detection |
| `opencv-python` | Frame capture & preview |
| `python-osc` | OSC output |
| `pySyphon` | (future) Syphon frame output |
| `websockets` | (future) WebSocket server |

## GitHub

- **Repo**: `kinekt-mac-pipeline` (placeholder — rename as needed)
