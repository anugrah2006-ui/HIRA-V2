import re

import requests

from core.config import api_logger, config


COUNTRY_NAMES = {
    "IN": "India",
    "US": "United States",
    "GB": "United Kingdom",
}

KNOWN_LOCATIONS = {
    "greater noida": {
        "name": "Greater Noida",
        "state": "Uttar Pradesh",
        "country": "India",
        "lat": 28.4744,
        "lon": 77.5040,
    },
    "greater noida 201310": {
        "name": "Greater Noida",
        "state": "Uttar Pradesh",
        "country": "India",
        "lat": 28.4744,
        "lon": 77.5040,
    },
}


def _clean_location_text(location):
    return re.sub(r"\s+", " ", str(location or "")).strip(" .,!?:;\"'")


def _display_location(data):
    parts = [
        data.get("name"),
        data.get("state"),
        data.get("country"),
    ]
    return ", ".join(part for part in parts if part)


def _location_payload(data, original_query):
    payload = {
        "query": original_query,
        "name": data.get("name") or original_query,
        "state": data.get("state"),
        "country": data.get("country"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
    }
    payload["display_name"] = _display_location(payload)
    return payload


def resolve_location(location):
    """Resolve a free-form location into a reusable location payload."""
    if isinstance(location, dict):
        if location.get("display_name") or location.get("name"):
            return {"success": True, "data": location}
        return {"success": False, "error": "Saved location is incomplete."}

    query = _clean_location_text(location)
    if not query:
        return {"success": False, "error": "Please provide a city or location."}

    known_key = query.lower()
    if known_key in KNOWN_LOCATIONS:
        return {"success": True, "data": _location_payload(KNOWN_LOCATIONS[known_key], query)}

    if not config.WEATHER_API_KEY:
        fallback = {
            "name": query.title(),
            "state": None,
            "country": None,
            "lat": None,
            "lon": None,
        }
        return {"success": True, "data": _location_payload(fallback, query)}

    url = "https://api.openweathermap.org/geo/1.0/direct"
    candidates = [query]
    without_pin = re.sub(r"\b\d{5,6}\b", "", query).strip()
    if without_pin and without_pin != query:
        candidates.append(without_pin)

    for candidate in candidates:
        try:
            response = requests.get(
                url,
                params={"q": candidate, "limit": 1, "appid": config.WEATHER_API_KEY},
                timeout=10,
            )
            if response.status_code in (401, 403):
                api_logger.error(f"Weather geocoding auth error: {response.status_code}")
                break
            response.raise_for_status()
            results = response.json()
            if not results:
                continue

            first = results[0]
            data = {
                "name": first.get("name") or candidate.title(),
                "state": first.get("state"),
                "country": COUNTRY_NAMES.get(first.get("country"), first.get("country")),
                "lat": first.get("lat"),
                "lon": first.get("lon"),
            }
            return {"success": True, "data": _location_payload(data, query)}
        except Exception as exc:
            api_logger.warning(f"Weather geocoding failed for {candidate}: {exc}")

    if known_key.replace(" 201310", "") == "greater noida":
        return {"success": True, "data": _location_payload(KNOWN_LOCATIONS["greater noida"], query)}

    return {"success": False, "error": f"I couldn't resolve the location {query}."}


def get_weather_result(location):
    """Fetch current weather and return a structured result."""
    resolved = resolve_location(location)
    if not resolved["success"]:
        return resolved

    location_data = resolved["data"]
    if not config.WEATHER_API_KEY:
        api_logger.warning("Weather API key missing.")
        return {
            "success": False,
            "location": location_data,
            "error": "Weather API key is missing. Add WEATHER_API_KEY to your .env file.",
        }

    url = "https://api.openweathermap.org/data/2.5/weather"
    if location_data.get("lat") is not None and location_data.get("lon") is not None:
        params = {
            "lat": location_data["lat"],
            "lon": location_data["lon"],
            "appid": config.WEATHER_API_KEY,
            "units": "metric",
        }
    else:
        params = {
            "q": location_data.get("display_name") or location_data.get("name"),
            "appid": config.WEATHER_API_KEY,
            "units": "metric",
        }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code in (401, 403):
            api_logger.error(f"Weather API auth error: {response.status_code}")
            return {
                "success": False,
                "location": location_data,
                "error": "Weather service authentication failed. Check your API key.",
            }
        if response.status_code == 429:
            api_logger.error("Weather API rate limit exceeded.")
            return {
                "success": False,
                "location": location_data,
                "error": "Weather service is currently busy. Please try again later.",
            }

        response.raise_for_status()
        data = response.json()

        if str(data.get("cod")) != "200":
            return {
                "success": False,
                "location": location_data,
                "error": "I couldn't find the weather for that location.",
            }

        main = data.get("main", {})
        weather = (data.get("weather") or [{}])[0]
        result = {
            "location": location_data,
            "temperature_c": main.get("temp"),
            "feels_like_c": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "description": weather.get("description", "current conditions"),
            "source_city": data.get("name"),
        }
        api_logger.info(f"Successfully fetched weather for {location_data.get('display_name')}.")
        return {"success": True, "data": result}
    except requests.exceptions.Timeout:
        api_logger.error(f"Weather API timeout for location: {location_data}")
        return {
            "success": False,
            "location": location_data,
            "error": "Weather service timed out.",
        }
    except Exception as exc:
        api_logger.error(f"Weather API error: {exc}")
        return {
            "success": False,
            "location": location_data,
            "error": "Weather service is currently unavailable.",
        }


def format_weather_result(result):
    if not result.get("success"):
        return result.get("error", "Weather service is currently unavailable.")

    data = result["data"]
    location = data["location"].get("display_name") or data["location"].get("name")
    temp = data.get("temperature_c")
    feels_like = data.get("feels_like_c")
    description = data.get("description")

    if temp is None:
        return f"I found {location}, but the weather response did not include temperature."

    sentence = f"It's currently {temp:.1f} C in {location} with {description}."
    if feels_like is not None:
        sentence += f" It feels like {feels_like:.1f} C."
    return sentence


def get_weather(city):
    """Backward-compatible plain-text weather helper."""
    return format_weather_result(get_weather_result(city))
