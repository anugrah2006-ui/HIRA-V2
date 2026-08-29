import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Setup API Logger
api_logger = logging.getLogger("API")
api_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOGS_DIR / "api.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
api_logger.addHandler(file_handler)

def mask_key(key):
    if not key or len(key) < 8:
        return "Not Set"
    return key[:4] + "*" * 12 + key[-4:]

class Config:
    def __init__(self):
        self.reload()

    def reload(self):
        load_dotenv(BASE_DIR / ".env", override=True)
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        self.WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
        self.GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        self.MAPS_API_KEY = os.getenv("MAPS_API_KEY")

    def validate_keys(self):
        print("\n--- HIRA V2 API Status ---")
        
        status = {
            "Gemini": self.GEMINI_API_KEY,
            "Groq": self.GROQ_API_KEY,
            "Weather": self.WEATHER_API_KEY,
            "News": self.GNEWS_API_KEY,
            "Google": self.GOOGLE_API_KEY
        }
        
        for name, key in status.items():
            masked = mask_key(key)
            if key:
                print(f"[OK] {name}: Connected ({masked})")
                api_logger.info(f"{name} initialized. Key: {masked}")
            else:
                print(f"[MISSING] {name}: Missing")
                api_logger.warning(f"{name} key missing at startup.")
                
        print("--------------------------\n")

config = Config()
