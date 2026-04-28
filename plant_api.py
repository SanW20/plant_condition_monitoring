import requests
from config import PERENUAL_API_KEY

PERENUAL_SEARCH_URL = "https://perenual.com/api/species-list"
PERENUAL_DETAIL_URL = "https://perenual.com/api/species/details/{id}"


def search_plants(query: str, max_results: int = 3) -> list[dict]:
    """
    Search Perenual by common or scientific name.
    Returns up to max_results cleaned result dicts for the picker UI.
    """
    if not PERENUAL_API_KEY:
        raise ValueError("PERENUAL_API_KEY not set in .env")

    resp = requests.get(
        PERENUAL_SEARCH_URL,
        params={
            "key": PERENUAL_API_KEY,
            "q": query,
            "page": 1,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("data", [])[:max_results]:
        results.append({
            "perenual_id": item.get("id"),
            "common_name": item.get("common_name", "Unknown"),
            "scientific_name": (
                item.get("scientific_name", [""])[0]
                if isinstance(item.get("scientific_name"), list)
                else item.get("scientific_name", "")
            ),
            "thumbnail": (
                item.get("default_image", {}).get("thumbnail", "")
                if item.get("default_image")
                else ""
            ),
            "description": item.get("description", ""),
        })
    return results


def get_plant_details(perenual_id: int) -> dict:
    """
    Fetch full plant details from Perenual by ID.
    Returns a normalised dict used for alert logic and display.
    """
    if not PERENUAL_API_KEY:
        raise ValueError("PERENUAL_API_KEY not set in .env")

    resp = requests.get(
        PERENUAL_DETAIL_URL.format(id=perenual_id),
        params={"key": PERENUAL_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    item = resp.json()

    # Parse min temperature — Perenual returns hardiness zone e.g. "7a"
    # We map zone to approximate min Celsius
    min_temp = _hardiness_to_celsius(item.get("hardiness", {}))

    # Watering field is a string like "frequent", "average", "minimum", "none"
    watering_raw = item.get("watering", "average")
    if isinstance(watering_raw, list):
        watering_raw = watering_raw[0] if watering_raw else "average"
    watering = watering_raw.lower().strip() if watering_raw else "average"

    sunlight_raw = item.get("sunlight", [])
    if not isinstance(sunlight_raw, list):
        sunlight_raw = [sunlight_raw] if sunlight_raw else []

    return {
        "perenual_id": perenual_id,
        "common_name": item.get("common_name") or "Unknown",
        "scientific_name": (
            item.get("scientific_name", [""])[0]
            if isinstance(item.get("scientific_name"), list)
            else (item.get("scientific_name") or "")
        ),
        "description": item.get("description") or "",
        "thumbnail": (
            item.get("default_image", {}).get("thumbnail", "")
            if item.get("default_image")
            else ""
        ),
        "watering": watering,
        "sunlight": sunlight_raw,
        "drought_tolerant": bool(item.get("drought_tolerant") or False),
        "indoor": bool(item.get("indoor") or False),
        "min_temp_celsius": min_temp,
        "max_temp_celsius": 38,  # General upper limit for most plants
        "care_level": item.get("care_level") or "moderate",
    }


def _hardiness_to_celsius(hardiness: dict) -> float:
    """
    Convert USDA hardiness zone to approximate minimum temperature in Celsius.
    Perenual returns hardiness as {"min": "7a", "max": "10b"} or similar.
    We use the min zone to determine cold tolerance.

    USDA zone -> min temp (Celsius) approximate midpoints:
      1  -> -45, 2 -> -40, 3 -> -34, 4 -> -29, 5 -> -23,
      6  -> -18, 7 -> -12, 8 ->  -7, 9 ->  -1, 10 ->  4,
      11 ->  10, 12 ->  15
    """
    zone_map = {
        "1": -45, "2": -40, "3": -34, "4": -29, "5": -23,
        "6": -18, "7": -12, "8": -7,  "9": -1,  "10": 4,
        "11": 10, "12": 15,
    }
    default_min = 5  # safe default if hardiness data is missing

    if not hardiness:
        return default_min

    min_zone_str = hardiness.get("min", "")
    if not min_zone_str:
        return default_min

    # Strip letter suffix e.g. "7a" -> "7"
    zone_number = "".join(c for c in str(min_zone_str) if c.isdigit())
    return zone_map.get(zone_number, default_min) 
