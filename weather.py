import requests
from config import (
    OPENWEATHERMAP_API_KEY,
    TALLINN_LAT,
    TALLINN_LON,
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OWM_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def _fetch_open_meteo():
    """
    Primary weather source — no API key required.
    Returns current conditions + 48h hourly forecast.
    """
    params = {
        "latitude": TALLINN_LAT,
        "longitude": TALLINN_LON,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "precipitation",
            "weather_code",
        ],
        "hourly": [
            "temperature_2m",
            "precipitation",
            "wind_speed_10m",
        ],
        "forecast_days": 2,
        "wind_speed_unit": "ms",
        "timezone": "Europe/Tallinn",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    current = data["current"]
    hourly = data["hourly"]

    # Build 48h forecast list
    forecast_hours = []
    for i, time_str in enumerate(hourly["time"]):
        forecast_hours.append({
            "time": time_str,
            "temp": hourly["temperature_2m"][i],
            "rain": hourly["precipitation"][i],
            "wind": hourly["wind_speed_10m"][i],
        })

    # Next 12h min temp and total rain
    next_12 = forecast_hours[:12]
    next_24 = forecast_hours[:24]

    return {
        "source": "open-meteo",
        "current_temp": current["temperature_2m"],
        "current_humidity": current["relative_humidity_2m"],
        "current_wind": current["wind_speed_10m"],
        "current_rain": current["precipitation"],
        "min_temp_12h": min(h["temp"] for h in next_12),
        "max_temp_24h": max(h["temp"] for h in next_24),
        "total_rain_24h": sum(h["rain"] for h in next_24),
        "max_wind_24h": max(h["wind"] for h in next_24),
        "forecast_hours": forecast_hours,
    }


def _fetch_owm():
    """
    Fallback weather source — requires OWM API key.
    Used when Open-Meteo fails.
    """
    if not OPENWEATHERMAP_API_KEY:
        raise ValueError("OWM API key not set in .env")

    current_resp = requests.get(
        OWM_CURRENT_URL,
        params={
            "lat": TALLINN_LAT,
            "lon": TALLINN_LON,
            "appid": OPENWEATHERMAP_API_KEY,
            "units": "metric",
        },
        timeout=10,
    )
    current_resp.raise_for_status()
    current = current_resp.json()

    forecast_resp = requests.get(
        OWM_FORECAST_URL,
        params={
            "lat": TALLINN_LAT,
            "lon": TALLINN_LON,
            "appid": OPENWEATHERMAP_API_KEY,
            "units": "metric",
            "cnt": 16,  # 16 x 3h = 48h
        },
        timeout=10,
    )
    forecast_resp.raise_for_status()
    forecast = forecast_resp.json()

    items = forecast["list"]
    next_4 = items[:4]   # ~12h
    next_8 = items[:8]   # ~24h

    forecast_hours = [
        {
            "time": item["dt_txt"],
            "temp": item["main"]["temp"],
            "rain": item.get("rain", {}).get("3h", 0),
            "wind": item["wind"]["speed"],
        }
        for item in items
    ]

    return {
        "source": "openweathermap",
        "current_temp": current["main"]["temp"],
        "current_humidity": current["main"]["humidity"],
        "current_wind": current["wind"]["speed"],
        "current_rain": current.get("rain", {}).get("1h", 0),
        "min_temp_12h": min(i["main"]["temp"] for i in next_4),
        "max_temp_24h": max(i["main"]["temp"] for i in next_8),
        "total_rain_24h": sum(i.get("rain", {}).get("3h", 0) for i in next_8),
        "max_wind_24h": max(i["wind"]["speed"] for i in next_8),
        "forecast_hours": forecast_hours,
    }


def get_weather():
    """
    Returns merged weather dict.
    Tries Open-Meteo first, falls back to OWM on any error.
    """
    try:
        return _fetch_open_meteo()
    except Exception as primary_error:
        try:
            return _fetch_owm()
        except Exception as fallback_error:
            raise RuntimeError(
                f"Both weather sources failed.\n"
                f"Open-Meteo: {primary_error}\n"
                f"OWM: {fallback_error}"
            )
 
