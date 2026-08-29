import os
import sys
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)

google_api_key = os.environ.pop("GOOGLE_API_KEY", None)
try:
    client = genai.Client(api_key=api_key)
finally:
    if google_api_key is not None:
        os.environ["GOOGLE_API_KEY"] = google_api_key

try:
    chat = client.chats.create(model="gemini-2.5-flash")
    response = chat.send_message("Explain how AI works in a few words")
    print(response.text)
except Exception as e:
    print(f"Warning: Primary model failed ({e}). Trying fallback...", file=sys.stderr)
    try:
        chat = client.chats.create(model="gemini-1.5-flash")
        response = chat.send_message("Explain how AI works in a few words")
        print(response.text)
    except Exception as fallback_e:
        print(f"Error calling Gemini API: {fallback_e}", file=sys.stderr)
