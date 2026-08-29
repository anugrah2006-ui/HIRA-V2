import requests
from core.config import config, api_logger

def get_latest_news():
    """Fetches top 5 latest news headlines."""
    if not config.GNEWS_API_KEY:
        api_logger.warning("News API key missing.")
        return ["News API key is missing. Add GNEWS_API_KEY to your .env file."]

    url = "https://newsapi.org/v2/top-headlines"
    params = {"country": "in", "apiKey": config.GNEWS_API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code in (401, 403):
            api_logger.error(f"News API Auth Error: {response.status_code}")
            return ["News service authentication failed. Check your API key."]
        elif response.status_code == 429:
            api_logger.error("News API Rate Limit Exceeded.")
            return ["News service is currently busy."]
            
        response.raise_for_status()
        data = response.json()
        
        headlines = [article["title"] for article in data.get("articles", [])[:5]]
        if headlines:
            api_logger.info("Successfully fetched latest news.")
            return headlines
        return ["No news headlines found."]
        
    except requests.exceptions.Timeout:
        api_logger.error("News API timeout.")
        return ["News service timed out."]
    except Exception as exc:
        api_logger.error(f"News API Error: {exc}")
        return ["News service is temporarily unavailable."]
