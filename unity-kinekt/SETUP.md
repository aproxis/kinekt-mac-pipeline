# Unity Kinekt — Setup

## Quick Start

### 1. Open project in Unity Hub
- Open Unity Hub → Open → выбери `unity-kinekt/`
- Дождись импорта всех ассетов (1-2 минуты)

### 2. Setup Main Camera
В Hierarchy выбери **Main Camera**. Добавь компоненты (Add Component):

| Компонент | Откуда |
|-----------|--------|
| **MaskCapture** | `Scripts/MaskCapture` |
| **RingBuffer** | `Scripts/RingBuffer` |
| **OutlineCompositor** | `Scripts/OutlineCompositor` |

Настрой **MaskCapture**:
- `serverName` = `KinectMask` (имя Syphon сервера из Python)
- `compositor` → перетащи `OutlineCompositor` (тот же объект)

### 3. Запусти Python (Терминал 2)
```bash
cd Kinekt360
source venv/bin/activate
python pose_to_osc_7.py
```

### 4. Play в Unity
Нажми **Play**. Если всё ок:
- Увидишь скелет + контурные копии
- FPS в углу экрана

Если чёрный экран — проверь консоль Unity (Window → General → Console).

## Параметры

### OutlineCompositor
| Параметр | По умолч | Что делает |
|----------|----------|------------|
| Outline Color | Cyan | Цвет контура |
| Outline Width | 3 | Толщина в пикселях |
| Fade Power | 1.5 | Затухание старых кадров |
| Drift Amount | 0.02 | Смещение старых слепков |
| Hue Shift | 0.3 | Сдвиг цвета со временем |
| Snapshot Capacity | 16 | Сколько кадров хранить |
| Capture Stride | 3 | Каждый N-й кадр маски |

## Если не работает

| Симптом | Причина | Фикс |
|---------|---------|------|
| Чёрный экран | Скрипты не на камере | Добавь все 3 скрипта на Main Camera |
| DllNotFoundException | Нет нативного плагина | Сделай git pull — .bundle уже добавлен |
| "Waiting for Syphon" | Python не запущен | Запусти `pose_to_osc_7.py` |
| Нет outline | Маска пустая | webcam не даёт depth — подключи Kinect |
