import threading
import time

class Api:
    def __init__(self, process_command_func, get_pc_health_func):
        self.process_command_func = process_command_func
        self.get_pc_health_func = get_pc_health_func
        self.window = None

    def set_window(self, window):
        self.window = window

    def process_message(self, message):
        """Called from JavaScript when user sends a message"""
        print(f"UI received: {message}")
        try:
            # We call the existing aiprocess or process_command logic
            response = self.process_command_func(message)
            return response
        except Exception as e:
            return f"Error: {e}"

    def toggle_voice(self):
        """Called from JS to toggle voice mode"""
        return "Voice mode toggled"

    def start_voice_mode(self):
        """Called from JS when Voice Mode tab is clicked."""
        print("[HIRA Bridge] Voice Mode Started.")
        # Future: Start background listener thread here
        return True

    def stop_voice_mode(self):
        """Called from JS when Text Mode tab is clicked or Esc is pressed."""
        print("[HIRA Bridge] Voice Mode Stopped.")
        # Future: Stop background listener thread here
        return True

    def push_to_talk(self):
        """Called from JS when the giant mic is clicked."""
        print("[HIRA Bridge] Push-to-talk triggered.")
        # Future: Trigger immediate manual listen
        return True

    def get_api_status(self):
        from core.config import config, mask_key
        return {
            "Gemini": {"connected": bool(config.GEMINI_API_KEY), "key": mask_key(config.GEMINI_API_KEY)},
            "Groq": {"connected": bool(config.GROQ_API_KEY), "key": mask_key(config.GROQ_API_KEY)},
            "Weather": {"connected": bool(config.WEATHER_API_KEY), "key": mask_key(config.WEATHER_API_KEY)},
            "News": {"connected": bool(config.GNEWS_API_KEY), "key": mask_key(config.GNEWS_API_KEY)},
            "Google": {"connected": bool(config.GOOGLE_API_KEY), "key": mask_key(config.GOOGLE_API_KEY)}
        }

    def open_env_file(self):
        import os
        import subprocess
        from pathlib import Path
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if not env_path.exists():
            env_path.write_text("# API Keys\n")
        
        try:
            if os.name == 'nt':
                os.startfile(str(env_path))
            else:
                subprocess.Popen(['open', str(env_path)])
            return "Opened .env file"
        except Exception as e:
            return f"Failed to open .env: {e}"

    def reload_apis(self):
        from core.config import config
        config.reload()
        return self.get_api_status()

    def update_system_status_loop(self):
        """Runs in a background thread to update PC health in UI"""
        while True:
            if self.window:
                try:
                    import psutil
                    cpu = f"{psutil.cpu_percent(interval=1)}%"
                    ram = f"{psutil.virtual_memory().percent}%"
                    self.window.evaluate_js(f"window.updateSystemStatus('{cpu}', '{ram}');")
                except Exception as e:
                    pass
            time.sleep(5)
