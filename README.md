# HIRA - Hyper Intelligent Robotic Assistant

A comprehensive AI-powered voice and text-based assistant for Windows with intelligent command processing, fallback modes, and robust error handling.

## Features

### 🎙️ Voice & Text Input
- **Voice Mode**: Speak commands naturally (requires PyAudio)
- **Text Mode**: Type commands (automatic fallback if no microphone)
- **Fuzzy Wake-Word Detection**: Recognizes "hira", "hear a", "hiraa", etc.

### 🤖 AI Capabilities
- **Gemini Integration**: Advanced AI for general queries
- **Web Browsing**: Open websites (Google, YouTube, Facebook, etc.)
- **News Headlines**: Get latest news from NewsAPI
- **Weather Information**: Real-time weather by city
- **Wikipedia Search**: Find information on any topic

### 📋 Productivity Features
- **Task Management**: Add, list, and clear tasks
- **Notes & Reminders**: Voice or text-based note taking
- **Timer**: Set timers with voice or text input
- **Code Generation**: Ask AI to write code for you
- **Code Explanation**: Explain code from clipboard

### 🎮 System Control
- **Brightness Control**: Adjust screen brightness
- **Volume Control**: Mute, increase, or decrease volume
- **Screenshots**: Capture desktop screenshots
- **App Launcher**: Open Chrome, VS Code, Notepad
- **Power Control**: Shutdown, restart, lock computer
- **Focus Mode**: Activate productivity mode

### 💻 System Monitoring
- **PC Health**: Monitor CPU, RAM, disk, and battery
- **CPU Temperature**: Check processor temperature

---

## Installation

### Prerequisites
- **Python 3.8+** (tested on 3.11+)
- **Windows OS** (primary platform)
- **Internet Connection** (for AI and API features)

### Step 1: Clone/Download the Repository
```bash
cd "HIRA V1"
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Optional: Install PyAudio for Voice Mode
PyAudio is optional. If missing, HIRA runs in text mode.

**Windows - Using pre-built wheel (recommended):**
```bash
pip install pipwin
pipwin install pyaudio
```

**Or download from:** https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

### Step 3: Configure API Keys
```bash
# Copy the example environment file
copy .env.example .env

# Edit .env and add your API keys
# (See setup section below)
```

### Step 4: Get API Keys

#### 🔑 Gemini API Key
1. Visit: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key to `.env` as `GEMINI_API_KEY`

#### 📰 NewsAPI Key
1. Visit: https://newsapi.org
2. Sign up for free account
3. Get API key from dashboard
4. Copy to `.env` as `NEWS_API_KEY`

#### 🌤️ Weather API Key (OpenWeatherMap)
1. Visit: https://openweathermap.org/api
2. Sign up and get free tier API key
3. Copy to `.env` as `WEATHER_API_KEY`

### Step 5: Create .env File
```bash
# .env file content:
GEMINI_API_KEY=your_gemini_key_here
NEWS_API_KEY=your_newsapi_key_here
WEATHER_API_KEY=your_openweathermap_key_here
```

### Step 6: Run HIRA
```bash
py main.py
```

To force text mode:
```bash
py main.py --text
```

---

## Usage

### Voice Mode (if PyAudio installed)
1. Application will listen for the wake word: **"hira"**
2. Speak your command after hearing the confirmation
3. Examples:
   - "weather" → asks which city
   - "tell me about python" → Wikipedia search
   - "play despacito" → plays on YouTube
   - "add task buy milk" → adds to task list

### Text Mode (automatic fallback)
1. Type commands directly at the prompt
2. Works with all voice commands
3. Type "exit" or "quit" to close

### Common Commands

```
# Information
- "tell me about [topic]" - Wikipedia search
- "weather" - Get weather for a city
- "news" - Get top 5 headlines
- "time" - Get current time
- "date" - Get today's date

# Control
- "play [song]" - Play on YouTube
- "open google/youtube/chrome/vscode" - Open app/website
- "take note" - Save a note
- "remind me [text]" - Save reminder
- "set timer [seconds]" - Set timer

# System
- "screenshot" - Take screenshot
- "pc health" - Check system stats
- "temperature" - Check CPU temp
- "mute/increase/decrease volume" - Volume control
- "brightness" - Adjust screen brightness
- "shutdown/restart/lock" - System power
- "free up ram" - Clean recycle bin

# AI Features
- "write code [task]" - Generate code
- "summarize clipboard" - Summarize text
- "explain code" - Explain code from clipboard
- "fix grammar" - Fix grammar in clipboard
- "[any question]" - Ask AI assistant
```

---

## Troubleshooting

### PyAudio Installation Fails
**Problem:** `pip install pyaudio` returns errors

**Solution:**
1. Download pre-built wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
2. Select matching Python version and architecture
3. Install: `pip install pyaudio-*.whl`

Alternatively, HIRA works perfectly in text mode without PyAudio.

### "Missing Environment Variables" Error
**Problem:** Application exits with missing API key error

**Solution:**
1. Ensure `.env` file exists in the HIRA directory
2. Add all three API keys (GEMINI_API_KEY, NEWS_API_KEY, WEATHER_API_KEY)
3. Restart the application

### Speech Recognition Not Working
**Problem:** "Could not understand the audio" or timeouts

**Solution:**
1. Check microphone is working (test in Windows Sound Settings)
2. Ensure quiet environment for better recognition
3. Speak clearly and at normal pace
4. Application auto-calibrates to ambient noise

### Weather/News Shows Error
**Problem:** API returns error

**Solution:**
1. Check your API keys in `.env`
2. Verify you have remaining quota (check on NewsAPI/OpenWeatherMap websites)
3. Check internet connection
4. Try again after a few seconds

---

## Project Structure

```
HIRA V1/
├── main.py                    # Main application
├── requirements.txt           # Python dependencies
├── .env.example              # Example environment file
├── README.md                 # This file
├── BUG_FIXES_ANALYSIS.md    # Detailed bug fixes
├── memory.json              # Persistent memory
├── todo.json                # Task list
├── notes.txt                # Notes
├── reminders.txt            # Reminders
├── hira_debug.log          # Debug log
└── generated_code.py        # Generated code storage
```

---

## Features in Detail

### Microphone & Audio
- ✅ Automatic PyAudio detection
- ✅ Graceful fallback to text mode
- ✅ Ambient noise calibration
- ✅ Fuzzy wake-word matching
- ✅ Proper resource cleanup

### Error Handling
- ✅ Comprehensive exception handling
- ✅ Informative error messages
- ✅ Automatic error recovery
- ✅ Logging for debugging
- ✅ Max error limit (prevents infinite loops)

### Security
- ✅ No hardcoded API keys
- ✅ Environment variables for secrets
- ✅ API key never logged
- ✅ Input validation on all APIs

### Reliability
- ✅ Graceful shutdown (Ctrl+C)
- ✅ Keyboard interrupt handling
- ✅ Network error handling
- ✅ Timeout management
- ✅ Resource cleanup

---

## Logging

HIRA creates a debug log file: `hira_debug.log`

### View logs:
```bash
# On Windows
type hira_debug.log

# Or open in any text editor
notepad hira_debug.log
```

### Log levels:
- **DEBUG**: Detailed operation info
- **INFO**: General info (commands, features)
- **WARNING**: Non-critical issues
- **ERROR**: Recoverable errors
- **CRITICAL**: Fatal errors

---

## Performance

- **Startup Time**: ~2-3 seconds (Gemini initialization)
- **Command Response**: ~1-5 seconds (depends on API)
- **Voice Recognition**: ~2-3 seconds (includes speaking)
- **Memory Usage**: ~150-200 MB

---

## Known Limitations

1. **WMI (Windows Only)** - Temperature reading requires OpenHardwareMonitor
2. **Speech Recognition** - Requires internet for Google Speech API
3. **PyAudio Optional** - Some systems may have installation issues
4. **API Rate Limits** - NewsAPI and Weather API have free tier limits
5. **Language** - Currently supports English only

---

## Compatibility

| Component | Status |
|-----------|--------|
| Python 3.11+ | ✅ Tested |
| Python 3.8-3.10 | ✅ Supported |
| Windows 10/11 | ✅ Tested |
| Windows 7/8 | ⚠️ Untested |
| Linux | ⚠️ Partial support |
| macOS | ⚠️ Partial support |

---

## Future Enhancements

- [ ] Multi-language support
- [ ] Offline speech recognition
- [ ] Custom wake-word training
- [ ] Voice profile adaptation
- [ ] Cloud sync for tasks/notes
- [ ] Mobile app integration
- [ ] Plugin system for custom commands
- [ ] Advanced NLP for better understanding

---

## Contributing

Found a bug or have a suggestion? Please create an issue with:
1. Description of the problem
2. Steps to reproduce
3. Error messages or logs
4. Your system information

---

## License

[Your License Here]

---

## Support

For issues, troubleshooting, or feature requests:
1. Check this README
2. Review `BUG_FIXES_ANALYSIS.md` for detailed fixes
3. Check `hira_debug.log` for error details
4. Verify all API keys are configured

---

## Disclaimer

HIRA is provided as-is. Use at your own risk. The author is not responsible for:
- Damage to your system
- Data loss
- Misuse of AI-generated code
- API rate limit charges

Always review generated code before execution and keep your API keys secret.

---

**Made with ❤️ - HIRA Assistant V1**
