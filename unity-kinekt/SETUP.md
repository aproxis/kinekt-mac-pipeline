# Unity Kinekt — Setup

## Requirements
- Unity 6000.5+ (уже установлен)
- KlakSyphon (уже в проекте, `Assets/KlakSyphon/`)
- Python `pose_to_osc_7.py` с включённым `SEND_MASK_SYPHON = True`

## Структура проекта

```
unity-kinekt/
├── Assets/
│   ├── KlakSyphon/        ← Syphon receiver (Keijiro)
│   ├── Scripts/
│   │   ├── MaskCapture.cs  ← принимает маску из Syphon, кормит RingBuffer
│   │   ├── RingBuffer.cs   ← кольцевой буфер N кадров
│   │   └── OutlineCompositor.cs ← рендерит эффект через шейдер
│   └── Shaders/
│       └── OutlineComposite.shader ← контур + fade + drift + hue
```

## Setup Scene

### 1. Create GameObject `KinektManager`
Add components:

| Component | Settings |
|-----------|----------|
| **MaskCapture** | Server Name: `KinectMask`, Capture Size: 512x512, Interval: 3 |
| **RingBuffer** | Capacity: 24, Stride: 3 |
| **OutlineCompositor** | Outline Color, Width, Fade, Drift — настрой под себя |

### 2. Camera
На **Main Camera** добавь скрипт `OutlineCompositor` (уже есть на KinektManager).

### 3. Play
- Запусти `pose_to_osc_7.py` — увидишь эффект в Unity Game view

## Параметры OutlineCompositor

| Параметр | По умолч | Что делает |
|----------|----------|------------|
| Outline Color | Cyan | Базовый цвет контура |
| Outline Width | 3 | Толщина в пикселях |
| Fade Power | 1.5 | Скорость затухания старых кадров |
| Drift Amount | 0.02 | На сколько старые слепки уезжают |
| Hue Shift | 0.3 | Смена цвета от новых к старым |
| Snapshot Capacity | 16 | Сколько кадров хранить |
| Capture Stride | 3 | Каждый N-й кадр (экономия perf) |
