# Full Control Transcript AI

A real-time, hands-free interview assistant that continuously transcribes your conversation and provides AI-powered solutions on demand.

## 🚀 Features

- **Hands-Free Operation**: No "push-to-talk" required. The system automatically listens to both your microphone and system audio (interviewer) in the background.
- **Dual-Stream Transcription**: Uses Gemini 2.0 to transcribe both the user and the system audio simultaneously.
- **Real-time Overlay**: Displays the ongoing transcript in a sleek, semi-transparent floating window.
- **Context-Aware Analysis**: Uses the entire transcript history to provide accurate answers to the latest questions.
- **Screenshot Integration**: Send a screenshot along with the transcript for visual problem-solving (e.g., LeetCode challenges).
- **Hallucination Protection**: Built-in volume thresholding (RMS) and specialized prompting to prevent the AI from generating text during silence.

## ⌨️ Hotkeys

| Hotkey | Action |
| :--- | :--- |
| `k` + `.` | **Analyze Transcript**: Sends the current text history to Gemini for a solution. |
| `k` + `,` | **Analyze with Screenshot**: Takes a screenshot and sends it with the transcript. |
| `k` + `c` | **Clear Memory**: Wipes the transcript history and clears the chat overlay. |
| `m` + `n` | **Toggle Overlay**: Hides or shows the floating AI window. |

## 🛠️ Setup

### Prerequisites

1.  **Python 3.10+**
2.  **WASAPI Loopback Support**: Windows is required for high-quality loopback audio.
3.  **Dependencies**:
    ```bash
    pip install google-genai sounddevice numpy mss pillow pynput python-dotenv pyaudiowpatch
    ```
4.  **Gemini API Key**: Add your key to a `.env` file in the root directory:
    ```env
    GEMINI_API_KEY=your_key_here
    ```

### Running the App

Run the watcher to start the application with auto-restart enabled:
```bash
python run.py
```

## 📋 How it Works

1.  **Listeners**: The `audio.py` module starts two concurrent streams—one for your mic and one for system loopback.
2.  **Filtering**: Every 10 seconds, the audio is analyzed for volume. If the sound level is too low (defined by `threshold`), it is discarded to avoid transcription hallucinations.
3.  **Transcription**: Valid audio is sent to Gemini for precise transcription and added to the rolling transcript history.
4.  **Querying**: When you press the hotkey, the entire history (and an optional screenshot) is bundled and sent as a context-rich prompt to Gemini Pro or Flash.
