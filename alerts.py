from datetime import datetime, timezone
from config import ZONE_EXPOSURE, WATERING_INTERVALS


def check_plant(plant: dict, weather: dict) -> list[dict]:
    """
    Run all alert checks for a single plant against current weather.

    Returns a list of alert dicts:
      {
        "type":    str   — e.g. "COVER_NEEDED"
        "level":   str   — "warning" | "critical"
        "message": str   — human-readable, includes plant name + zone + reason
        "action":  str   — what to do
      }
    """
    alerts = []
    perenual = plant.get("cached_perenual_data", {})
    zone = plant.get("zone", "ground")
    exposure = ZONE_EXPOSURE.get(zone, "open")
    name = plant.get("name", "Plant")
    age_months = plant.get("age_months", 0)
    age_label = _age_label(age_months)

    min_temp = perenual.get("min_temp_celsius", 5)
    max_temp = perenual.get("max_temp_celsius", 38)
    watering_key = perenual.get("watering", "average")
    drought_tolerant = perenual.get("drought_tolerant", False)

    forecast_min_12h = weather.get("min_temp_12h", 20)
    forecast_max_24h = weather.get("max_temp_24h", 20)
    current_temp = weather.get("current_temp", 15)
    total_rain_24h = weather.get("total_rain_24h", 0)
    max_wind_24h = weather.get("max_wind_24h", 0)
    current_wind = weather.get("current_wind", 0)

    # ------------------------------------------------------------------
    # 1. FROST WARNING — applies to all zones, critical below 0°C
    # ------------------------------------------------------------------
    if forecast_min_12h < 0:
        if exposure == "enclosed":
            alerts.append({
                "type": "FROST_WARNING",
                "level": "warning",
                "message": (
                    f"{name} ({age_label}) in the {zone} — "
                    f"frost forecast ({forecast_min_12h:.1f}°C). "
                    f"Greenhouse provides some protection but check heating."
                ),
                "action": "Check greenhouse temperature and insulation.",
            })
        else:
            alerts.append({
                "type": "FROST_WARNING",
                "level": "critical",
                "message": (
                    f"{name} ({age_label}) in the {zone} — "
                    f"frost forecast ({forecast_min_12h:.1f}°C)."
                ),
                "action": "Move inside or cover with frost fleece immediately.",
            })

    # ------------------------------------------------------------------
    # 2. COVER NEEDED — temp drops below plant tolerance, non-enclosed
    # ------------------------------------------------------------------
    elif forecast_min_12h < min_temp and exposure != "enclosed":
        alerts.append({
            "type": "COVER_NEEDED",
            "level": "warning",
            "message": (
                f"{name} ({age_label}) in the {zone} cannot tolerate "
                f"below {min_temp}°C. Tonight forecast: {forecast_min_12h:.1f}°C."
            ),
            "action": "Cover with fleece or move to a sheltered spot before dark.",
        })

    # ------------------------------------------------------------------
    # 3. HEAT STRESS — high temp, non-drought-tolerant
    # ------------------------------------------------------------------
    if forecast_max_24h > max_temp and not drought_tolerant:
        alerts.append({
            "type": "HEAT_STRESS",
            "level": "warning",
            "message": (
                f"{name} ({age_label}) in the {zone} — "
                f"high temperature forecast ({forecast_max_24h:.1f}°C). "
                f"This plant is not drought tolerant."
            ),
            "action": (
                "Ensure adequate watering and shade. "
                "Open greenhouse ventilation if applicable."
            ),
        })

    # ------------------------------------------------------------------
    # 4. WATER NEEDED — interval exceeded and no rain coming
    # ------------------------------------------------------------------
    interval_days = WATERING_INTERVALS.get(watering_key, 4)
    days_since = _days_since_watered(plant.get("last_watered"))

    if days_since is not None:
        # Rain reduces urgency — if 5mm+ expected skip the alert
        if days_since >= interval_days and total_rain_24h < 5:
            alerts.append({
                "type": "WATER_NEEDED",
                "level": "warning",
                "message": (
                    f"{name} ({age_label}) in the {zone} needs watering. "
                    f"Last watered {days_since} day(s) ago "
                    f"(interval: every {interval_days} day(s)). "
                    f"No significant rain forecast ({total_rain_24h:.1f}mm/24h)."
                ),
                "action": "Water today.",
            })

    # ------------------------------------------------------------------
    # 5. HEAVY RAIN — waterlogging risk for ground plants
    # ------------------------------------------------------------------
    if total_rain_24h > 20 and exposure == "open":
        alerts.append({
            "type": "HEAVY_RAIN",
            "level": "warning",
            "message": (
                f"{name} ({age_label}) in the {zone} — "
                f"heavy rain forecast ({total_rain_24h:.1f}mm/24h). "
                f"Waterlogging risk for ground-level plants."
            ),
            "action": "Check drainage. Consider temporary cover if pot has no holes.",
        })

    # ------------------------------------------------------------------
    # 6. WIND RISK — young plants or exposed terrace/ground
    # ------------------------------------------------------------------
    if max_wind_24h > 12 and exposure != "enclosed":
        if age_months < 12:
            alerts.append({
                "type": "WIND_RISK",
                "level": "warning",
                "message": (
                    f"{name} ({age_label}) in the {zone} — "
                    f"young plant at risk from strong wind "
                    f"(forecast {max_wind_24h:.1f} m/s)."
                ),
                "action": "Stake the plant or move pot to a sheltered position.",
            })
        elif max_wind_24h > 20:
            alerts.append({
                "type": "WIND_RISK",
                "level": "warning",
                "message": (
                    f"{name} ({age_label}) in the {zone} — "
                    f"very strong wind forecast ({max_wind_24h:.1f} m/s)."
                ),
                "action": "Secure or move exposed pots.",
            })

    return alerts


def check_all_plants(plants: list[dict], weather: dict) -> dict:
    """
    Run checks for all plants.
    Returns:
      {
        "alerts":       [ { plant, alerts[] } ]   — only plants WITH alerts
        "ok":           [ plant_name, ... ]        — plants with no issues
        "weather":      weather dict
        "checked_at":   ISO timestamp
      }
    """
    triggered = []
    ok = []

    for plant in plants:
        plant_alerts = check_plant(plant, weather)
        if plant_alerts:
            triggered.append({
                "plant": plant,
                "alerts": plant_alerts,
            })
        else:
            ok.append(plant.get("name", "Unknown"))

    return {
        "alerts": triggered,
        "ok": ok,
        "weather": weather,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _days_since_watered(last_watered_str: str | None) -> int | None:
    if not last_watered_str:
        return None
    try:
        last = datetime.fromisoformat(last_watered_str)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last
        return delta.days
    except (ValueError, TypeError):
        return None


def _age_label(age_months: int) -> str:
    if age_months < 1:
        return "less than 1 month old"
    if age_months < 12:
        return f"{age_months} month{'s' if age_months != 1 else ''} old"
    years = age_months // 12
    months = age_months % 12
    label = f"{years} year{'s' if years != 1 else ''}"
    if months:
        label += f" {months} month{'s' if months != 1 else ''}"
    return label + " old" 
