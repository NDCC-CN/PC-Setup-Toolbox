# PC Setup Toolbox (装机助手)

An **offline** Windows PC setup toolbox that helps you set up your computer quickly. Just double-click to use — no Python installation needed. It turns a freshly-installed Windows into a "ready to code, ready to use" machine.

> Author: NDCC ｜ A GUI program written in pure Python 3.7 + Tkinter, with Win7 support

---

## What this software does

It does four things for a Windows PC: **set up the development environment, optimize the system, detect hardware, and diagnose problems**.

---

## Features

### ① Set up the development environment (one-click install / uninstall)

Python, C/C++ (GCC), Java (JDK), Node.js, Git, VS Code — each comes in two versions:

| Software | For old PCs (Win7) | For new PCs (Win10/11) |
|------|-----------------|---------------------|
| Python | 3.8.10 | 3.13.15 |
| C/C++ | GCC (MSVCRT runtime) | GCC (UCRT runtime) |
| Java | JDK 8 | JDK 21 |
| Node.js | 13.14.0 | 26.10.0 |
| Git | 2.46.2 | 2.55.0.5 |
| VS Code | 1.85.2 | 1.139.0 |

> Why two versions? Because many newer versions no longer support Win7. This tool picks the right version for you — old version for old PCs, new version for new PCs.

- **One-click install** with automatic PATH setup (no manual environment variable editing)
- **Tamper-proof**: every installer has a built-in SHA-256 fingerprint, verified before installation; if a file has been modified, it refuses to install
- **One-click uninstall** as well

### ② Optimize the system

- Pause / resume Windows updates
- Show file extensions, show hidden files
- Clean temporary files, empty the recycle bin
- Move Downloads / Desktop / Documents to the D: drive

### ③ Detect hardware

CPU, GPU, screen resolution, screen size and color gamut, GPU mode — see the full spec of this PC in one click.

### ④ Diagnose problems

GPU/screen, device drivers, memory/disk — three categories of issues, click to get a verdict, plus a "one-click diagnosis" summary.

> Dangerous operations (emptying the recycle bin, moving folders, configuring remote desktop) ask for confirmation before executing.

---

## How to use

1. Get a zip package containing two things:
   - `Toolbox.exe` (the main program)
   - `packages\` (the installer folder)
2. Extract anywhere and **double-click `Toolbox.exe`**.
3. Click the button for the software you want to install → choose the version → done.

> Note: `Toolbox.exe` and the `packages\` folder must be in the same directory for the program to find the installers.

---

## For developers

### Directory structure

```
├── src/            # source code (main.py, hashes.py)
├── rdpwrap/        # remote desktop components
├── Toolbox.spec    # PyInstaller build config
├── build_hashes.py # generates installer fingerprints
├── 启动.bat         # run from source without packaging
└── packages/       # installers (not in repo, too large)
```

### Rebuild

```bash
# 1. Only needed if you changed the installers: regenerate fingerprints
python build_hashes.py

# 2. Build the exe
python -m PyInstaller Toolbox.spec --noconfirm

# 3. Output is dist\Toolbox.exe
```

> Build environment: Python 3.7.9 + PyInstaller 5.13.2 (3.7 is used for Win7 compatibility).

---

## Disclaimer

This software is not for commercial use.

If you modify this software, please keep the author attribution (NDCC).

This software is still in the testing stage. The author is not responsible for any problems that occur. Please back up your important data before use.
