import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import DATA_FILE
from weather import get_weather
from alerts import check_all_plants
from email_sender import send_alert_email


def run_check():
    """
    Core job: fetch weather, check all plants, send email if any alerts fire.
    Called by APScheduler every 3 hours and also callable manually via Flask route.
    """
    print("[scheduler] Running plant check...")

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        plants = data.get("plants", [])
    except Exception as e:
        print(f"[scheduler] Could not load plants.json: {e}")
        return {"error": str(e)}

    if not plants:
        print("[scheduler] No plants registered — skipping check.")
        return {"alerts": [], "ok": [], "message": "No plants registered."}

    try:
        weather = get_weather()
    except Exception as e:
        print(f"[scheduler] Weather fetch failed: {e}")
        return {"error": str(e)}

    result = check_all_plants(plants, weather)

    alert_count = len(result.get("alerts", []))
    ok_count = len(result.get("ok", []))
    print(f"[scheduler] Check complete — {alert_count} plant(s) with alerts, {ok_count} OK.")

    if alert_count > 0:
        send_alert_email(result)

    return result


def start_scheduler():
    """
    Start the background scheduler.
    Runs run_check() every 3 hours.
    Should be called once at Flask app startup.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=run_check,
        trigger=IntervalTrigger(hours=3),
        id="plant_check",
        name="Plant care check every 3 hours",
        replace_existing=True,
    )
    scheduler.start()
    print("[scheduler] Background scheduler started — checks every 3 hours.")
    return scheduler
