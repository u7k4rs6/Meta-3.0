# Screenshot-AI — Multi-Version Toolkit

A background service that captures your screen, sends it to Gemini, and delivers answers via clipboard, automated typing, or floating overlays. Perfect for coding, conceptual questions, MCQs, and interview preparation.

---

## 🛠️ Setup (all versions)

### 1. Install dependencies
```bash
pip install google-genai pynput mss Pillow pyperclip python-dotenv sounddevice pyaudiowpatch numpy scipy
```
*Note: `pyaudiowpatch` and `sounddevice` are required for the "Full Control" audio features.*

### 2. Configure Environment
Create a `.env` file in the root project folder:
```text
GEMINI_API_KEY=your-key-here
```
Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey).

### 3. Run
You can run the watcher (restarts on save):
```bash
python run.py
```
Or run a specific version directly (e.g., `python AutoType.py`).

---

## 📋 Version 1 — Clipboard
**File:** `ClipboardCopy.py`

Captures screenshots and copies the AI-generated code directly to your clipboard.
- **Goal:** Fastest way to get code snippets for pasting.
- **Multi-Model Fallback:** Automatically tries Flash → Pro → Flash Lite if one fails.

| Hotkey  | Action                                |
| ------- | ------------------------------------- |
| `k + ,` | Add current screenshot to queue       |
| `k + .` | Send all queued screenshots to Gemini |
| `k + /` | Clear the queue                       |

---

## ⌨️ Version 2 — Auto-Type
**File:** `AutoType.py`

Simulates human-like typing to enter code character-by-character.
- **Bypasses:** Sites that block `Ctrl+V` (e.g., HackerRank, LeetCode).
- **Multi-Model Fallback:** Automatically tries Flash → Pro → Flash Lite if one fails.
- **Smart Formatting:** Normalizes indentation to 4 spaces and removes comments/markdown.

| Hotkey  | Action                                |
| ------- | ------------------------------------- |
| `k + ,` | Add screenshot to queue               |
| `k + .` | Start processing queue                |
| `k + /` | Clear queue                           |
| `a + s` | **Pause / Resume** typing             |
| `k + x` | **Abort** typing immediately          |

---

## 🧠 Version 3 — General Purpose
**File:** `general.py`

An adaptive version that detects the question type and responds accordingly.
- **Multi-Model Fallback:** Automatically tries Flash → Pro → Flash Lite if one fails.
- **Coding:** Returns raw executable code.
- **MCQ:** Returns correct option + brief reason.
- **Theory:** Concise summary.
- **Math:** Step-by-step solution.

---

## 🎯 Version 4 — MCQ Optimized
**File:** `mcq/main.py`

Specialized for Multiple Choice Questions with a tiny, persistent overlay.
- **Invisible:** Overlay is hidden from screenshots and screen sharing.
- **Multi-Question Support:** Handles multiple MCQs in one screenshot by separating answers with a pipe (`|`).
- **Multi-Answer Support:** Returns comma-separated options (e.g., `A,C`) if a single question has multiple correct answers.
- **Single-Char:** Returns just the option for standard questions.
- **Multi-Model Fallback:** Automatically tries Flash → Pro → Flash Lite if one fails.

| Hotkey  | Action                                   |
| ------- | ---------------------------------------- |
| `k + ,` | Add MCQ screenshot                       |
| `k + .` | Send to Gemini → Update overlay answer   |
| `m + n` | Toggle overlay visibility (Hide / Show)  |

---

## 👑 Version 5 — Full Control / Interviewer Mode
**File:** `full Control/main.py`

The most advanced version, featuring a floating Markdown overlay, conversation memory, and audio capabilities.
- **Interactive:** Follow-up on previous questions via built-in chat UI.
- **Conversation Memory:** Remembers the last 10 turns for context.
- **Multi-Model Fallback:** Automatically tries Flash → Pro → Flash Lite for screenshots, follow-ups, AND audio transcription.
- **Audio (Mic):** Hold the microphone button to record your voice; release to transcribe and ask Gemini.
- **Interviewer Mode:** Listen to system audio (Transcribes what you hear, e.g., an interviewer speaking) and automatically suggests answers.

| Hotkey  | Action                                       |
| ------- | -------------------------------------------- |
| `k + ,` | Add screenshot to context                    |
| `k + .` | Send context to Gemini                       |
| `k + c` | **Clear Memory** and Chat history            |
| `k + t` | Display test content (Verify UI)             |
| `m + n` | Toggle overlay visibility                    |
| 🎤 Button| Hold to Record / Release to Send             |
| 🔊 Button| Toggle System Audio (Interviewer) Listener   |

---

## 📊 Quick Comparison

| Feature                      | Clipboard | Auto-Type | General | MCQ | Full Control |
| ---------------------------- | --------- | --------- | ------- | --- | ------------ |
| Output Method                | Clipboard | Typing    | Typing  | Overlay | Overlay      |
| Invisible to Screenshots     | ❌         | ✅         | ❌       | ✅   | ✅            |
| Multi-Model Fallback         | ✅         | ✅         | ✅       | ✅   | ✅            |
| Follow-up Questions          | ❌         | ❌         | ❌       | ❌   | ✅            |
| Audio / Voice Input          | ❌         | ❌         | ❌       | ❌   | ✅            |
| System Audio Listen          | ❌         | ❌         | ❌       | ❌   | ✅ (Interviewer) |
| Markdown Rendering           | ❌         | ❌         | ❌       | ❌   | ✅            |
| Best For                     | Quick Copy| Paste Blocked| Any     | Exams| Interviews    |

---

## ⚠️ Disclaimer
This tool is for educational and accessibility purposes only. Please adhere to the academic integrity policies of your institution or organization.

