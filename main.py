import datetime
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
import re
from pathlib import Path
from urllib.parse import quote_plus

import psutil
import pyperclip
import pyttsx3
import requests
import speech_recognition as sr

from core.config import config, api_logger
from services.ai_service import generate_text
from services.hardware_service import format_pc_temperature_result, get_pc_temperature
from services.weather_service import format_weather_result, get_weather_result, resolve_location
from services.news_service import get_latest_news
from services.google_service import normalize_youtube_query, play_youtube_video

try:
    import webview
except Exception:
    webview = None

try:
    from core.bridge import Api
except Exception:
    Api = None

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import screen_brightness_control as sbc
except Exception:
    sbc = None

try:
    import wikipedia
except Exception:
    wikipedia = None

try:
    import wmi
except Exception:
    wmi = None


BASE_DIR = Path(__file__).resolve().parent
MEMORY_FILE = BASE_DIR / "memory.json"
TODO_FILE = BASE_DIR / "todo.json"
GENERATED_CODE_FILE = BASE_DIR / "generated_code.py"
NOTES_FILE = BASE_DIR / "notes.txt"
REMINDERS_FILE = BASE_DIR / "reminders.txt"
MIC_INIT_TIMEOUT = 7

recognizer = sr.Recognizer()
engine = None

microphone_source = None
selected_microphone_index = None
microphone_initialization_error = None


def log(message):
    print(f"[HIRA] {message}")


def get_engine():
    global engine
    try:
        return pyttsx3.init()
    except Exception as exc:
        log(f"Text-to-speech unavailable: {exc}")
        engine = False
        return False


def speak(text, print_text=True):
    if print_text:
        print(f"HIRA: {text}")
    tts_engine = get_engine()
    if not tts_engine:
        return

    try:
        tts_engine.say(text)
        tts_engine.runAndWait()
        tts_engine.stop()
    except Exception as exc:
        log(f"Speech output failed: {exc}")


def load_json_file(path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        log(f"Invalid JSON in {path.name}; using defaults.")
        return default


def save_json_file(path, data):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


memory = load_json_file(MEMORY_FILE, {})


def load_memory():
    return load_json_file(MEMORY_FILE, {})


def save_memory(data):
    save_json_file(MEMORY_FILE, data)


def update_memory(**updates):
    memory.update(updates)
    save_memory(memory)


def _title_from_memory_value(value):
    if not value:
        return None
    return str(value).replace("_", " ").title()


def get_saved_weather_location():
    current_location = memory.get("current_location")
    if isinstance(current_location, dict) and (
        current_location.get("display_name") or current_location.get("name")
    ):
        return current_location

    preferred_city = _title_from_memory_value(memory.get("preferred_city"))
    if not preferred_city:
        return None

    preferred_state = _title_from_memory_value(memory.get("preferred_state"))
    location = {
        "query": preferred_city,
        "name": preferred_city,
        "state": preferred_state,
        "country": "India" if preferred_state else None,
        "lat": None,
        "lon": None,
    }
    location["display_name"] = ", ".join(
        part for part in (location["name"], location["state"], location["country"]) if part
    )
    return location


def remember_weather_location(location_text):
    resolved = resolve_location(location_text)
    if not resolved["success"]:
        return resolved

    location = resolved["data"]
    updates = {
        "current_location": location,
        "awaiting_weather_location": False,
        "preferred_city": str(location.get("name", "")).replace(" ", "_").lower(),
    }
    if location.get("state"):
        updates["preferred_state"] = str(location["state"]).replace(" ", "_").lower()
    update_memory(**updates)
    return {"success": True, "data": location}


def format_location_ack(location):
    name = location.get("name") or location.get("display_name") or "that location"
    return f"Got it. I'll use {name} as your current location."


def load_todo():
    return load_json_file(TODO_FILE, [])


def save_todo(tasks):
    save_json_file(TODO_FILE, tasks)


def append_line(path, text):
    with path.open("a", encoding="utf-8") as file:
        file.write(text.strip() + "\n")


def is_pyaudio_installed():
    try:
        import pyaudio  # noqa: F401
        return True
    except Exception as exc:
        log(f"PyAudio import failed: {exc}")
        return False


def list_microphones():
    try:
        return sr.Microphone.list_microphone_names()
    except Exception as exc:
        log(f"Failed to list microphones: {exc}")
        return []


def _threaded_init_mic(device_index, result):
    try:
        result["mic"] = sr.Microphone(device_index=device_index)
    except Exception as exc:
        result["error"] = exc


def create_microphone_instance(device_index=None, timeout_seconds=MIC_INIT_TIMEOUT):
    result = {}
    thread = threading.Thread(
        target=_threaded_init_mic,
        args=(device_index, result),
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        return None, TimeoutError("Microphone initialization timed out")
    if "error" in result:
        return None, result["error"]
    return result.get("mic"), None


def initialize_microphone():
    global microphone_source, selected_microphone_index, microphone_initialization_error

    microphone_source = None
    microphone_initialization_error = None

    if not is_pyaudio_installed():
        microphone_initialization_error = RuntimeError("PyAudio is not installed.")
        return False

    available_names = list_microphones()
    if not available_names:
        microphone_initialization_error = RuntimeError("No microphone devices were detected.")
        return False

    configured_index = memory.get("microphone_device_index")
    if isinstance(configured_index, str) and configured_index.isdigit():
        configured_index = int(configured_index)
    if not isinstance(configured_index, int):
        configured_index = None

    if configured_index is not None and 0 <= configured_index < len(available_names):
        selected_microphone_index = configured_index
    elif len(available_names) == 1:
        selected_microphone_index = 0
    else:
        selected_microphone_index = None

    microphone_source, error = create_microphone_instance(selected_microphone_index)
    if error:
        microphone_initialization_error = error
        return False

    try:
        with microphone_source as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            microphone_source._noise_calibrated = True
        return True
    except Exception as exc:
        microphone_initialization_error = exc
        microphone_source = None
        return False


def listen_on_microphone(timeout=5, phrase_time_limit=5):
    if microphone_source is None:
        return None

    try:
        with microphone_source as source:
            if not getattr(microphone_source, "_noise_calibrated", False):
                recognizer.adjust_for_ambient_noise(source, duration=1)
                microphone_source._noise_calibrated = True
            return recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    except sr.WaitTimeoutError:
        raise
    except Exception as exc:
        log(f"Microphone listening failed: {exc}")
        return None





def get_clipboard_text():
    try:
        return pyperclip.paste()
    except Exception:
        return ""


def write_code_from_prompt(prompt, filename=GENERATED_CODE_FILE):
    instruction = f"Write complete executable Python code for:\n{prompt}\nReturn only code."
    code = generate_text(instruction)
    if not code or code.startswith("Sorry") or "API key is missing" in code:
        return "Failed to generate code."

    code = code.replace("```python", "").replace("```", "").strip()
    Path(filename).write_text(code, encoding="utf-8")

    try:
        subprocess.Popen([sys.executable, str(filename)])
        return f"Code generated, saved as {filename}, and executed."
    except Exception as exc:
        return f"Code generated but could not be executed: {exc}"


def get_cpu_temperature():
    result = get_pc_temperature()
    cpu_temperature = result.get("data", {}).get("CPU")
    if cpu_temperature is None:
        return "CPU: unavailable"
    return f"CPU: {cpu_temperature:.1f} C"


def get_pc_health():
    try:
        cpu = psutil.cpu_percent(interval=1)
        memory_info = psutil.virtual_memory()
        disk = psutil.disk_usage(str(BASE_DIR.anchor or "C:\\"))
        battery = psutil.sensors_battery()
        lines = [
            f"CPU usage: {cpu}%",
            f"RAM usage: {memory_info.percent}%",
            f"Disk usage: {disk.percent}%",
        ]
        if battery:
            lines.append(f"Battery: {battery.percent}%")
        return "\n".join(lines)
    except Exception as exc:
        log(f"PC health check failed: {exc}")
        return "PC health information is unavailable right now."


def write_code_from_prompt(prompt, filename=GENERATED_CODE_FILE):
    instruction = f"Write complete executable Python code for:\n{prompt}\nReturn only code."
    code = generate_text(instruction)
    if not code or code.startswith("Sorry") or "API key is missing" in code:
        return "Failed to generate code."

    code = code.replace("```python", "").replace("```", "").strip()
    Path(filename).write_text(code, encoding="utf-8")

    try:
        subprocess.Popen([sys.executable, str(filename)])
        return f"Code generated, saved as {filename}, and executed."
    except Exception as exc:
        return f"Code generated but could not be executed: {exc}"


def handle_text_capture(prompt, voice_prompt=None):
    if microphone_source is not None:
        if voice_prompt:
            speak(voice_prompt)
        try:
            audio = listen_on_microphone(timeout=5, phrase_time_limit=8)
            if audio is not None:
                return recognizer.recognize_google(audio)
        except Exception:
            pass

    return input(prompt).strip()


def extract_code_blocks(text):
    """Returns a list of (language, code) tuples extracted from markdown code blocks."""
    pattern = r"```([a-zA-Z0-9+#]*)\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL)
    return [(lang.strip().lower(), code.strip()) for lang, code in matches]

def contains_code(text):
    """Returns True if there are code blocks in the text."""
    return bool(extract_code_blocks(text))

def save_generated_code(blocks):
    """Saves each extracted block to a separate file and returns a list of filenames."""
    ext_map = {
        "python": "py", "py": "py",
        "html": "html", "css": "css", "javascript": "js", "js": "js",
        "c": "c", "cpp": "cpp", "c++": "cpp", "c#": "cs", "java": "java",
        "sql": "sql", "json": "json", "xml": "xml", "markdown": "md", "md": "md",
        "sh": "sh", "bash": "sh"
    }
    
    saved_files = []
    for i, (lang, code) in enumerate(blocks):
        ext = ext_map.get(lang, "txt")
        suffix = f"_{i}" if i > 0 else ""
        filename = BASE_DIR / f"generated_code{suffix}.{ext}"
        
        try:
            filename.write_text(code, encoding="utf-8")
            saved_files.append(filename.name)
        except Exception as exc:
            log(f"Failed to save code block: {exc}")
            
    return saved_files

def clean_text_for_tts(text):
    """Removes markdown formatting and code blocks for cleaner TTS reading."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`.*?`", "", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\n+", " ", text)
    return text.strip()

def summarize_for_speech(text):
    """Summarizes text if it's too long for TTS."""
    clean_text = clean_text_for_tts(text)
    if len(clean_text) > 400:
        sentences = clean_text.split(". ")
        summary = ""
        for sentence in sentences:
            if len(summary) + len(sentence) < 300:
                summary += sentence + ". "
            else:
                break
        if not summary:
            summary = clean_text[:300] + "..."
        return summary + " I have displayed the detailed explanation on your screen."
    return clean_text


def is_youtube_play_command(lowered):
    return (
        lowered.startswith("play ")
        or (lowered.startswith("open ") and " youtube" in lowered)
    )


def is_hardware_temperature_command(lowered):
    temperature_words = ("temperature", "temp", "hot", "heat", "thermal")
    hardware_words = (
        "pc",
        "cpu",
        "gpu",
        "system",
        "laptop",
        "computer",
        "hardware",
        "ssd",
        "nvme",
        "processor",
        "graphics",
    )
    return any(word in lowered for word in temperature_words) and any(
        word in lowered for word in hardware_words
    )


def is_weather_command(lowered):
    if is_hardware_temperature_command(lowered):
        return False
    weather_words = ("weather", "raining", "rain", "outside")
    temperature_words = ("temperature", "temp", "hot", "cold")
    return any(word in lowered for word in weather_words) or any(
        word in lowered for word in temperature_words
    )


def extract_weather_location(command):
    patterns = [
        r"\b(?:weather|temperature|temp|raining|rain)\s+(?:in|for|at)\s+(.+)$",
        r"\b(?:in|for|at)\s+([a-zA-Z][a-zA-Z\s,\-0-9]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, command, flags=re.IGNORECASE)
        if match:
            location = match.group(1)
            location = re.sub(r"\b(today|now|currently|outside)\b", "", location, flags=re.IGNORECASE)
            return re.sub(r"\s+", " ", location).strip(" .,!?:;\"'")
    return ""


def handle_weather_command(command):
    location_text = extract_weather_location(command)
    saved_location = get_saved_weather_location()

    if location_text:
        remembered = remember_weather_location(location_text)
        if remembered["success"]:
            saved_location = remembered["data"]
        else:
            speak(remembered["error"])
            return False

    if not saved_location:
        update_memory(awaiting_weather_location=True)
        location_text = handle_text_capture(
            "Enter city: ",
            "Which city would you like the weather for?",
        )
        if not location_text:
            speak("Please tell me your location first.")
            return False
        remembered = remember_weather_location(location_text)
        if not remembered["success"]:
            speak(remembered["error"])
            return False
        saved_location = remembered["data"]
        speak(format_location_ack(saved_location))

    result = get_weather_result(saved_location)
    report = format_weather_result(result)
    print(report)
    speak(report)
    return False


def process_command(command):
    if not command:
        return False

    lowered = command.lower().strip()

    websites = {
        "google": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "instagram": "https://www.instagram.com",
        "facebook": "https://www.facebook.com",
        "twitter": "https://twitter.com",
        "linkedin": "https://www.linkedin.com",
        "whatsapp": "https://web.whatsapp.com",
        "prime": "https://www.primevideo.com",
    }

    try:
        explicit_command_markers = (
            "help",
            "commands",
            "open ",
            "play ",
            "add task ",
            "list tasks",
            "clear tasks",
            "take note",
            "remind me",
            "set timer",
            "news",
            "who is",
            "tell me about",
            "mute volume",
            "increase volume",
            "decrease volume",
            "increase brightness",
            "decrease brightness",
            "screenshot",
            "pc health",
            "system status",
            "write code ",
            "summarize clipboard",
            "explain code",
            "fix grammar",
        )
        exit_commands = {"exit", "quit", "stop", "goodbye", "shutdown hira"}
        pending_location_reply = (
            memory.get("awaiting_weather_location")
            and lowered not in exit_commands
            and not is_weather_command(lowered)
            and not is_hardware_temperature_command(lowered)
            and not any(marker in lowered for marker in explicit_command_markers)
        )
        if pending_location_reply:
            remembered = remember_weather_location(command)
            if remembered["success"]:
                speak(format_location_ack(remembered["data"]))
            else:
                speak(remembered["error"])
            return False

        for site, url in websites.items():
            if f"open {site}" in lowered:
                speak(f"Opening {site}")
                webbrowser.open(url)
                return False

        if lowered in {"help", "commands"}:
            speak(
                "Try commands like weather in Delhi, news, play music, list tasks, "
                "add task buy milk, take note, remind me call mom, pc health, or exit."
            )
            return False

        if "time" in lowered:
            speak(f"The time is {datetime.datetime.now().strftime('%I:%M %p')}")
            return False

        if "date" in lowered:
            speak(f"Today is {datetime.datetime.now().strftime('%A, %d %B %Y')}")
            return False

        if is_youtube_play_command(lowered):
            video_query = normalize_youtube_query(command)
            if not video_query:
                speak("Please tell me the song name.")
                return False
            result = play_youtube_video(video_query)
            if result["success"]:
                speak(f"Playing {result['query']} on YouTube.")
            else:
                speak(result["error"])
            return False

        if lowered.startswith("add task "):
            task = command[9:].strip()
            tasks = load_todo()
            tasks.append(task)
            save_todo(tasks)
            speak(f"Added task: {task}")
            return False

        if "list tasks" in lowered:
            tasks = load_todo()
            if tasks:
                speak("Here are your tasks.")
                for index, task in enumerate(tasks, start=1):
                    print(f"{index}. {task}")
            else:
                speak("You have no tasks.")
            return False

        if "clear tasks" in lowered:
            save_todo([])
            speak("All tasks cleared.")
            return False

        if lowered.startswith("take note"):
            note = command[len("take note"):].strip() or handle_text_capture("Enter note: ", "What note should I save?")
            append_line(NOTES_FILE, note)
            speak("Note saved.")
            return False

        if lowered.startswith("remind me"):
            reminder = command[len("remind me"):].strip() or handle_text_capture("Enter reminder: ", "What should I remind you about?")
            append_line(REMINDERS_FILE, reminder)
            speak("Reminder saved.")
            return False

        if lowered.startswith("set timer"):
            parts = lowered.split()
            seconds = next((int(part) for part in parts if part.isdigit()), None)
            if seconds is None:
                speak("Please provide the timer duration in seconds.")
                return False

            def countdown():
                time.sleep(seconds)
                speak("Time's up!")

            threading.Thread(target=countdown, daemon=True).start()
            speak(f"Timer set for {seconds} seconds.")
            return False

        if "news" in lowered:
            for headline in get_latest_news():
                print(headline)
                speak(headline)
            return False

        if is_hardware_temperature_command(lowered):
            result = get_pc_temperature()
            report = format_pc_temperature_result(result)
            print(report)
            speak(report)
            return False

        if is_weather_command(lowered):
            return handle_weather_command(command)

        if "who is" in lowered or "tell me about" in lowered:
            topic = lowered.replace("who is", "").replace("tell me about", "").strip()
            if wikipedia is None:
                speak("Wikipedia support is unavailable because the package is not installed.")
            else:
                try:
                    result = wikipedia.summary(topic, sentences=2)
                    print(result)
                    speak(result)
                except Exception:
                    speak("I couldn't find information on that topic.")
            return False

        if "mute volume" in lowered:
            if pyautogui is None:
                speak("Volume control is unavailable because pyautogui is not installed.")
            else:
                pyautogui.press("volumemute")
                speak("Volume muted.")
            return False

        if "increase volume" in lowered or "decrease volume" in lowered:
            if pyautogui is None:
                speak("Volume control is unavailable because pyautogui is not installed.")
            else:
                key = "volumeup" if "increase" in lowered else "volumedown"
                for _ in range(5):
                    pyautogui.press(key)
                speak("Volume adjusted.")
            return False

        if "increase brightness" in lowered or "decrease brightness" in lowered:
            if sbc is None:
                speak("Brightness control is unavailable because the brightness package is not installed.")
            else:
                try:
                    current = sbc.get_brightness()[0]
                    step = 20 if "increase" in lowered else -20
                    sbc.set_brightness(max(0, min(100, current + step)))
                    speak("Brightness adjusted.")
                except Exception:
                    speak("Unable to adjust brightness.")
            return False

        if "screenshot" in lowered:
            if pyautogui is None:
                speak("Screenshot support is unavailable because pyautogui is not installed.")
            else:
                filename = BASE_DIR / f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                pyautogui.screenshot(str(filename))
                speak(f"Screenshot saved to {filename.name}.")
            return False

        if "pc health" in lowered or "system status" in lowered:
            report = get_pc_health()
            print(report)
            speak(report)
            return False

        if lowered.startswith("write code "):
            prompt = command[len("write code "):].strip()
            speak(write_code_from_prompt(prompt))
            return False

        if "summarize clipboard" in lowered:
            clipboard_text = get_clipboard_text()
            if not clipboard_text:
                speak("Your clipboard is empty.")
            else:
                result = generate_text(f"Summarize this text:\n\n{clipboard_text}")
                print(result)
                speak(result[:500])
            return False

        if "explain code" in lowered:
            clipboard_text = get_clipboard_text()
            if not clipboard_text:
                speak("Your clipboard is empty.")
            else:
                result = generate_text(f"Explain this code clearly:\n\n{clipboard_text}")
                print(result)
                speak(result[:500])
            return False

        if "fix grammar" in lowered:
            clipboard_text = get_clipboard_text()
            if not clipboard_text:
                speak("Your clipboard is empty.")
            else:
                result = generate_text(f"Fix the grammar of this text:\n\n{clipboard_text}")
                print(result)
                speak(result[:500])
            return False

        if lowered in {"exit", "quit", "stop", "goodbye", "shutdown hira"}:
            speak("Goodbye.")
            return True

        response = generate_text(command)
        
        # 1. Print full response
        print(f"\nHIRA:\n{response}\n")
        
        # 2. Extract code blocks
        code_blocks = extract_code_blocks(response)
        
        if code_blocks:
            # Code found: Save and formulate speech
            saved_files = save_generated_code(code_blocks)
            files_str = ", ".join(saved_files)
            speak_msg = "I've generated the code and displayed it on your screen."
            if saved_files:
                speak_msg += f" I've also saved it to {files_str}."
            
            # Add summary of the non-code part
            clean_explanation = clean_text_for_tts(response)
            if clean_explanation:
                first_sentence = clean_explanation.split(". ")[0] + "."
                speak_msg += " " + first_sentence
                
            speak(speak_msg, print_text=False)
        else:
            # No code found, process for normal speech
            clean_text = clean_text_for_tts(response)
            if len(clean_text) > 400:
                summary = summarize_for_speech(response)
                speak(summary, print_text=False)
            else:
                speak(clean_text, print_text=False)
                
        return False

    except Exception as exc:
        log(f"Error while processing command: {exc}")
        speak("Sorry, an error occurred.")
        return False


def run_text_mode():
    speak("HIRA is running in text mode. Type help to see sample commands.")
    while True:
        try:
            command = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if process_command(command):
            break


def run_voice_mode():
    speak("Voice mode is active. Say HIRA to wake me up.")
    while True:
        try:
            print("Listening for wake word...")
            audio = listen_on_microphone(timeout=5, phrase_time_limit=3)
            if audio is None:
                continue

            command = recognizer.recognize_google(audio)
            if "hira" not in command.lower():
                continue

            speak("Yes?")
            audio = listen_on_microphone(timeout=5, phrase_time_limit=8)
            if audio is None:
                speak("I couldn't hear your command. Please try again.")
                continue

            command = recognizer.recognize_google(audio)
            print(f"You said: {command}")
            if process_command(command):
                break

        except sr.UnknownValueError:
            continue
        except sr.WaitTimeoutError:
            continue
        except KeyboardInterrupt:
            print()
            break
        except Exception as exc:
            log(f"Voice loop error: {exc}")


def run_gui_mode():
    try:
        from core.gui import run_native_gui
        log("Starting HIRA V3 Native Desktop...")
        run_native_gui(process_command)
    except ImportError as e:
        log(f"GUI mode requires PySide6. Error: {e}")
        log("Run: pip install PySide6")
        return run_text_mode()

def main():
    config.validate_keys()
    
    force_text_mode = any(arg in {"--text", "--no-voice"} for arg in sys.argv[1:])
    gui_mode = "--gui" in sys.argv[1:]

    if gui_mode:
        run_gui_mode()
        return

    if force_text_mode:
        run_text_mode()
        return

    if initialize_microphone():
        run_voice_mode()
    else:
        if microphone_initialization_error:
            log(f"Microphone unavailable: {microphone_initialization_error}")
        run_text_mode()


if __name__ == "__main__":
    main()
