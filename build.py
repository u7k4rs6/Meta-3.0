"""
build.py — PyInstaller build script
Run: python build.py
Output: dist/DontCheat.exe
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",                         # No console window for the launcher
    "--name", "DontCheat",
    "--add-data", f"{ROOT}/src;src",      # Bundle the src package
    "--hidden-import", "google.genai",
    "--hidden-import", "sounddevice",
    "--hidden-import", "pyaudiowpatch",
    "--hidden-import", "pynput.keyboard._win32",
    "--hidden-import", "pynput.mouse._win32",
    "--hidden-import", "PIL._tkinter_finder",
    "--hidden-import", "pystray",
    "--collect-all", "google.genai",
    f"{ROOT}/main.py",
]

print(">>  Building DontCheat.exe with PyInstaller...")
print(" ".join(cmd))
result = subprocess.run(cmd, cwd=ROOT)

if result.returncode == 0:
    print("\n>>  Build succeeded! -> dist/DontCheat.exe")
else:
    print("\n!!  Build failed. See output above.")
    sys.exit(1)
