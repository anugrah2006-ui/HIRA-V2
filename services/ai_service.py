from core.config import config, api_logger
from google import genai
import os
import requests


def _create_gemini_client():
    """Create a Gemini client with the configured Gemini key.

    google-genai warns and may prefer GOOGLE_API_KEY when both environment
    variables are present. HIRA keeps GOOGLE_API_KEY for other services, so
    hide it only while constructing the Gemini client.
    """
    google_api_key = os.environ.pop("GOOGLE_API_KEY", None)
    try:
        return genai.Client(api_key=config.GEMINI_API_KEY)
    finally:
        if google_api_key is not None:
            os.environ["GOOGLE_API_KEY"] = google_api_key

def _generate_with_groq(prompt):
    if not config.GROQ_API_KEY:
        raise ValueError("Groq API key is missing.")
    
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=15)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def generate_text(command):
    """Generates text using Gemini with a fallback to Groq."""
    if not config.GEMINI_API_KEY and not config.GROQ_API_KEY:
        api_logger.error("Both Gemini and Groq API keys are missing.")
        return "AI providers are missing. Please add GEMINI_API_KEY or GROQ_API_KEY to your .env file."

    # Primary: Gemini
    if config.GEMINI_API_KEY:
        try:
            client = _create_gemini_client()
            
            try:
                chat = client.chats.create(model="gemini-2.5-flash")
                response = chat.send_message(command)
                api_logger.info("Successfully generated text with Gemini (gemini-2.5-flash).")
                return response.text or "I couldn't generate a response."
            except Exception as primary_exc:
                api_logger.warning(f"Gemini primary model failed: {primary_exc}. Trying fallback...")
                
                chat = client.chats.create(model="gemini-1.5-flash")
                response = chat.send_message(command)
                api_logger.info("Successfully generated text with Gemini fallback (gemini-1.5-flash).")
                return response.text or "I couldn't generate a response with the fallback model either."
                
        except Exception as exc:
            api_logger.warning(f"Gemini API failed completely: {exc}. Falling back to Groq.")
    
    # Fallback: Groq
    if config.GROQ_API_KEY:
        try:
            result = _generate_with_groq(command)
            api_logger.info("Successfully generated text with Groq fallback.")
            return result
        except Exception as exc:
            api_logger.error(f"Groq API fallback failed: {exc}")
            
    return "Sorry, I am unable to process that request right now as all AI providers failed."

def generate_text_stream(command):
    """Generates text using Gemini with a fallback to Groq, yielding chunks."""
    if not config.GEMINI_API_KEY and not config.GROQ_API_KEY:
        api_logger.error("Both Gemini and Groq API keys are missing.")
        yield "AI providers are missing. Please add GEMINI_API_KEY or GROQ_API_KEY to your .env file."
        return

    # Primary: Gemini
    if config.GEMINI_API_KEY:
        try:
            client = _create_gemini_client()
            
            try:
                response = client.models.generate_content_stream(
                    model="gemini-2.5-flash",
                    contents=command,
                )
                api_logger.info("Successfully streaming text with Gemini (gemini-2.5-flash).")
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as primary_exc:
                api_logger.warning(f"Gemini primary model failed: {primary_exc}. Trying fallback...")
                
                response = client.models.generate_content_stream(
                    model="gemini-1.5-flash",
                    contents=command,
                )
                api_logger.info("Successfully streaming text with Gemini fallback (gemini-1.5-flash).")
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return
                
        except Exception as exc:
            api_logger.warning(f"Gemini API streaming failed completely: {exc}. Falling back to Groq.")
    
    # Fallback: Groq (simulate streaming since requests doesn't stream by default in our groq impl)
    if config.GROQ_API_KEY:
        try:
            # For this MVP we just fetch the whole thing and yield it in one chunk
            result = _generate_with_groq(command)
            api_logger.info("Successfully generated text with Groq fallback (pseudo-stream).")
            yield result
            return
        except Exception as exc:
            api_logger.error(f"Groq API fallback failed: {exc}")
            
    yield "Sorry, I am unable to process that request right now as all AI providers failed."
