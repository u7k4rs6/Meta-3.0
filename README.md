# Don't Cheat AI Toolkit v2.0

A complete, unified desktop application for AI assistance. It captures your screen, listens to audio, and sends context to Gemini. Answers are delivered via clipboard, automated typing, or floating transparent overlays. Perfect for coding, conceptual questions, MCQs, and interview preparation.

---

## 🛠️ Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```
*(Includes `google-genai`, `pynput`, `mss`, `Pillow`, `pyperclip`, `sounddevice`, `pyaudiowpatch`, `pyinstaller`)*

### 2. Configure Environment
Create a `.env` file in the root project folder containing your free Gemini API key:
```text
GEMINI_API_KEY=your-key-here
```
*(Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey))*

### 3. Run the Desktop App
```bash
python main.py
```
This opens the sleek, dark-mode **Launcher UI**. From here, you can:
1. Select the specific AI agent you want to run (e.g., Clipboard, AutoType, Real-Time Transcript).
2. Configure **Settings** (hotkeys, typing speeds, overlay colors & transparency).
3. Click **Launch** to start the listener in the background.

### 4. Build a Standalone Executable (Optional)
Don't want to run from terminal every time? Build a `.exe`:
```bash
python build.py
```
This drops a standalone `DontCheat.exe` into the `dist/` folder. You can pin it to your taskbar!

---

## 🤖 Available Agents

The v2.0 architecture combines all 6 legacy scripts into a single unified app. Every agent supports model fallbacks (`Flash -> Pro -> Flash Lite`), customizable hotkeys, and config persistence.

### 1. Clipboard Copy
Captures screenshots and copies the AI-generated code directly to your clipboard.
- **Goal:** Fastest way to get raw code snippets for pasting.

### 2. Auto-Type
Simulates human-like typing to enter code character-by-character.
- **Bypasses:** Sites that block `Ctrl+V` (e.g., HackerRank, LeetCode).
- **Features:** Start / Stop / Pause hotkeys. Smart indentation formatting.

### 3. General AI
An adaptive tool that detects the question type and auto-types the response.
- **Coding:** Returns raw executable code.
- **Theory / Math:** Types the step-by-step solution.

### 4. MCQ AI
Specialized for Multiple Choice Questions with a tiny, transparent, borderless overlay.
- **Features:** Returns comma-separated options (`A,C`) if multiple answers are correct. Completely invisible to screen recording/sharing software.

### 5. Multi-File Auto-Type
Specialized for **Low-Level Design (LLD)** and multi-file coding workflows.
- **Workflow:** Gemini generates logic for multiple files. The tool types a summary, and you advance through typing each file sequence using the `Next File` hotkey.

### 6. Full Control (Interview Mode)
The most advanced overlay, featuring an interactive markdown chat, memory, and mic/system audio capabilities.
- **Features:** Hold a hotkey to record your mic, or toggle the system audio listener to transcribe what an interviewer is saying. Follow up directly in the chat box.

### 7. Real-Time Transcript
Always-on dual-stream audio capture (Mic + System Audio).
- **Features:** Builds a silent real-time transcript in the background. Press the query hotkey to instantly analyze the transcript history and answer the interviewer's most recent question in the overlay.

---

## ⚙️ Customization (settings.json)
All customizations are done via the built-in **Settings** panel in the Launcher GUI.
Changes are saved to `settings.json` locally and remembered forever.
- Rebind any hotkey.
- Change typing simulator speeds.
- Change overlay transparency (alpha), background color, text color, and accent color.
- Re-order Gemini model fallbacks.

## ⚠️ Disclaimer
This tool is for educational and accessibility purposes only. Please adhere to the academic integrity policies of your institution or organization.
