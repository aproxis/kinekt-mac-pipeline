"""Персистентность профилей маппингов. Не знает про Ableton —
ре-валидацию guard'а делает main.py через on_changed хук."""
import json
import os

import state
import config

# вызывается после сохранения/загрузки маппингов (если задан — ставит main.py)
on_changed = None


def _notify_changed():
    if on_changed is not None:
        try:
            on_changed()
        except Exception:
            pass


def ensure_profiles_dir():
    os.makedirs(config.PROFILES_DIR, exist_ok=True)


def profile_path(name):
    return os.path.join(config.PROFILES_DIR, f"{name}.json")


def list_profiles():
    ensure_profiles_dir()
    names = []
    for f in sorted(os.listdir(config.PROFILES_DIR)):
        if f.endswith(".json"):
            names.append(f[:-5])
    return names


def load_mappings():
    """Загрузка при старте: текущий профиль → legacy mappings.json → дефолт."""
    ensure_profiles_dir()
    path = profile_path(state.current_profile)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        with state.mappings_lock:
            state.live_mappings = data
        print(f"Profile '{state.current_profile}': {len(data)} mappings")
        return data

    if os.path.exists(config.MAPPINGS_PATH):
        with open(config.MAPPINGS_PATH) as f:
            data = json.load(f)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        with state.mappings_lock:
            state.live_mappings = data
        print(f"Migrated mappings.json -> profiles/{state.current_profile}.json")
        return data

    default = [
        {"id": 1, "joint": "right_wrist", "axis": "y", "track": 4, "device": 0, "param": 144, "smoothing": 0.8, "threshold": 0.005},
        {"id": 2, "joint": "left_wrist", "axis": "y", "track": 4, "device": 0, "param": 148, "smoothing": 0.8, "threshold": 0.005},
    ]
    with open(path, "w") as f:
        json.dump(default, f, indent=2)
    with state.mappings_lock:
        state.live_mappings = default
    print(f"Created default profile: {len(default)} mappings")
    return default


def save_mappings(data):
    """Сохранение текущего профиля. ФИКС: state.live_mappings обновляется
    (раньше баг — без global, присваивание было локальной переменной)."""
    with state.mappings_lock:
        state.live_mappings = data
    path = profile_path(state.current_profile)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved profile '{state.current_profile}': {len(data)} mappings")
    _notify_changed()


def load_profile(name):
    path = profile_path(name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    with state.mappings_lock:
        state.live_mappings = data
    state.current_profile = name
    print(f"Switched to profile '{name}': {len(data)} mappings")
    _notify_changed()
    return data


def save_as_profile(name, data):
    path = profile_path(name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved as profile '{name}': {len(data)} mappings")


def delete_profile(name):
    if name == config.CURRENT_PROFILE:
        return False
    path = profile_path(name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
