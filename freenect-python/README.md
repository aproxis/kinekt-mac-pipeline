# libfreenect Python Wrapper

A modern Python 3-compatible wrapper for [libfreenect](https://github.com/OpenKinect/libfreenect), providing access to Microsoft Kinect v1 functionality.

> ⚠️ This project builds upon the original Python wrapper by [Brandyn White](mailto:bwhite@dappervision.com)(https://github.com/bwhite). I have ported and updated it for Python 3 compatibility and ongoing maintenance.

---

## 🚀 Installation

### 📦 From PyPI (Recommended)

You can now install the package directly from PyPI:

```bash
pip install freenect
```

### 🔧 From Source

Clone the repository and install manually:

```bash
git clone https://github.com/dewminawijekoon/freenect-python.git
cd freenect-python
pip install .
```

### 🧪 For Development

To install in editable mode with development dependencies:

```bash
git clone https://github.com/dewminawijekoon/freenect-python.git
cd freenect-python
pip install -e ".[dev]"
```

## 📦 Prerequisites

Make sure `libfreenect` is installed on your system before using this wrapper.

Follow the official instructions:
👉 [https://github.com/OpenKinect/libfreenect](https://github.com/OpenKinect/libfreenect)

---

## ⚡ Quick Start

```python
import freenect
import numpy as np

# Capture a depth image
depth, timestamp = freenect.sync_get_depth()
print(f"Depth shape: {depth.shape}")

# Capture an RGB image
rgb, timestamp = freenect.sync_get_video()
print(f"RGB shape: {rgb.shape}")
```

---

## ✨ Features

* Access Kinect depth and RGB video streams
* Synchronous & asynchronous capture modes
* Seamless integration with NumPy
* Cross-platform support (Linux, macOS, Windows)

---

## 📋 Requirements

* Python 3.8+
* NumPy
* libfreenect (installed system-wide)

---

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).

---

## 🤝 Contributing

Contributions are welcome! Feel free to open issues, fork the repo, or submit pull requests.

---

## 🐛 Issues

Encounter a problem? Open an issue and include a detailed description to help us assist you better.
