# Unity Kinekt — Setup

## Requirements
- Unity 2022.3 LTS or newer (URP template)
- [KinoSyphon](https://github.com/keijiro/KinoSyphon) — free Syphon receiver for Unity

## Steps

### 1. Create Unity Project
- Open Unity Hub → New Project → **Universal 3D (URP)**
- Name: `KinektViewer`

### 2. Import Syphon
- `Window → Package Manager → + → Add package from git URL`
- Paste: `https://github.com/keijiro/KinoSyphon.git`
- После установки появится `KinoSyphon` в Packages

### 3. Import Scripts
- Copy папки `Assets/Scripts/` и `Assets/Shaders/` в проект
- Перезагрузи Unity

### 4. Setup Scene

Create empty GameObject → `KinektManager`:

| Component | Settings |
|-----------|----------|
| **SyphonReceiver** | Server Name: `KinectMask` |
| **RingBuffer** | Capacity: 16, Stride: 3 |
| **OutlineCompositor** | Outline Color, Width, Drift — на вкус |

На **Main Camera** добавь `KinektManager` → перетащи `Main Camera` в Inspector.

### 5. Wire Syphon
- SyphonReceiver нужно привязать к текстуре из Syphon
- В `KinoSyphon` есть `SyphonReceiver.cs` — добавь его на `KinektManager`
- В его поле `targetTexture` укажи `liveMaskTexture` из OutlineCompositor

### 6. Run
- Запусти `pose_to_osc_7.py` (с Kinect или webcam)
- В Unity нажми Play
- Должен появиться эффект: живая маска + контурные слепки с затуханием

## Параметры настройки

| Параметр | Что делает |
|----------|------------|
| `snapshotCapacity` | Сколько прошлых кадров хранить (16 = ~5 сек) |
| `captureStride` | Каждый N-й кадр (3 = ~10 fps захват) |
| `outlineWidth` | Толщина контура в пикселях |
| `fadePower` | Скорость затухания старых слепков |
| `driftAmount` | На сколько старые слепки уезжают вбок |
| `hueShift` | Смена цвета от новых к старым |
| `outlineColor` | Базовый цвет контура |
