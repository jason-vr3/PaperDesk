# Third-party notices

PaperDesk source is licensed under AGPL-3.0-or-later. Copyright (c) 2026 jason-vr3 and contributors.

| Component | Version | License / upstream |
|---|---|---|
| PyMuPDF / bundled MuPDF | 1.26.7 | GNU AGPL v3 or commercial license; this release uses the AGPL option. https://pymupdf.readthedocs.io/en/latest/about.html |
| PySide6 Essentials / Qt | 6.8.3 | LGPL v3 / GPL / commercial options; dynamically linked, using the LGPL option. https://doc.qt.io/qtforpython-6/licenses.html |
| Shiboken6 | 6.8.3 | LGPL v3; included with PySide6 |
| Pillow | 13.0.0 | HPND and bundled codec notices; https://python-pillow.github.io/ |
| CPython | 3.12 | PSF License; bundled by PyInstaller |
| PyInstaller bootloader | 6.22.3 | GPL with bootloader exception; https://pyinstaller.org/en/stable/license.html |

Full notices shipped by installed distributions are copied into `licenses/` by the build script. Keep that folder with binary redistributions. Python's bundled license is also retained by PyInstaller. Qt dynamic libraries remain external in `_internal/PySide6`; do not replace the folder-based package with a locked-down distribution that prevents library replacement or debugging modifications. Qt/PySide sources are available from https://code.qt.io/ and https://download.qt.io/official_releases/QtForPython/ matching the listed version. MuPDF sources: https://mupdf.com/releases/ .

No paid SDK, cloud processing service, or downloaded runtime is required by the end-user application.
