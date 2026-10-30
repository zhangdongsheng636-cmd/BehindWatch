# Third-party components

BehindWatch source is provided alongside the application. No code was copied from bhy or peeker.

- YOLOX-Nano model and preprocessing/output conventions: Megvii-BaseDetection/YOLOX, Apache-2.0. Official 0.1.1rc0 ONNX release; exact source and SHA-256 in models/manifest.json. License in licenses/YOLOX.txt.
- ONNX Runtime 1.20.1: Microsoft, MIT; licenses/ONNXRuntime.txt and distributed metadata.
- cv2-enumerate-cameras 1.3.2: MIT; licenses/CameraEnumerator.txt and distributed metadata.
- PySide6 / Qt 6.8.3 / Shiboken6: LGPL-3.0 / applicable Qt third-party terms. Qt remains in separately replaceable DLLs in _internal. Full relevant license texts and package metadata accompany this distribution. Qt/PySide source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/ and https://download.qt.io/archive/qt/6.8/6.8.3/submodules/ . Users may modify/replace LGPL libraries and debug modifications; no additional restriction is imposed by this application.
- OpenCV 4.11.0: Apache-2.0; opencv-python wheel packaging includes additional third-party notices in its distribution metadata.
- NumPy 2.2.6: BSD-3-Clause and bundled numerical library terms in its distribution metadata.
- CPython 3.11: Python Software Foundation license; included in licenses/Python.txt.
- PyInstaller: GPL with bootloader exception; used to package this application, see https://pyinstaller.org/en/stable/license.html .

Application icon and short chime are generated specifically for this project. No remote fonts, analytics, cloud endpoints, or automatic update service are used by the application.
