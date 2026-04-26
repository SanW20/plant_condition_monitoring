import json
import uuid
import re
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

from config import DATA_FILE, SECRET_KEY
from weather import get_weather
from plant_api import search_plants, get_plant_details
from alerts import check_plant, check_all_plants
from scheduler import start_scheduler, run_check

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Start background scheduler when app starts
_scheduler = start_scheduler()


# ------------------------------------------------------------------
# Data helpers
# ------------------------------------------------------------------

def _load_plants() -> list[dict]:
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f).get("plants", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_plants(plants: list[dict]):
    with open(DATA_FILE, "w") as f:
        json.dump({"plants": plants}, f, indent=2)


def _get_plant(plant_id: str) -> dict | None:
    return next((p for p in _load_plants() if p["id"] == plant_id), None)


def _parse_age_months(age_str: str) -> int:
    """
    Parse user input like '6 months', '2 years', '1 year 3 months' -> int months.
    Falls back to 0 if unparseable.
    """
    age_str = age_str.lower().strip()
    months = 0
    year_match = re.search(r"(\d+)\s*year", age_str)
    month_match = re.search(r"(\d+)\s*month", age_str)
    if year_match:
        months += int(year_match.group(1)) * 12
    if month_match:
        months += int(month_match.group(1))
    return months


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route("/")
def index():
    """Dashboard — all plants grouped by zone with current weather + alerts."""
    plants = _load_plants()

    try:
        weather = get_weather()
        weather_error = None
    except Exception as e:
        weather = {}
        weather_error = str(e)

    # Group plants by zone
    zones = {
        "greenhouse": [],
        "terrace": [],
        "ground": [],
    }
    for plant in plants:
        zone = plant.get("zone", "ground")
        plant_alerts = check_plant(plant, weather) if weather else []
        zones.setdefault(zone, []).append({
            "plant": plant,
            "alerts": plant_alerts,
            "status": _status_from_alerts(plant_alerts),
        })

    return render_template(
        "index.html",
        zones=zones,
        weather=weather,
        weather_error=weather_error,
        total_plants=len(plants),
    )


@app.route("/plant/<plant_id>")
def plant_detail(plant_id):
    """Single plant detail view — Perenual info, watering log, current alerts."""
    plant = _get_plant(plant_id)
    if not plant:
        flash("Plant not found.", "error")
        return redirect(url_for("index"))

    try:
        weather = get_weather()
        weather_error = None
    except Exception as e:
        weather = {}
        weather_error = str(e)

    plant_alerts = check_plant(plant, weather) if weather else []
    perenual = plant.get("cached_perenual_data", {})

    return render_template(
        "plant_detail.html",
        plant=plant,
        perenual=perenual,
        alerts=plant_alerts,
        weather=weather,
        weather_error=weather_error,
        status=_status_from_alerts(plant_alerts),
    )


@app.route("/add", methods=["GET", "POST"])
def add_plant():
    """
    Step 1 — show form.
    Step 2 (POST with search) — show top 3 Perenual results.
    Step 3 (POST with confirm) — save plant.
    """
    search_results = None
    form_data = {}

    if request.method == "POST":
        action = request.form.get("action", "search")

        # ---- Step 3: Confirm selection and save ----
        if action == "confirm":
            perenual_id = int(request.form.get("perenual_id", 0))
            name = request.form.get("name", "").strip()
            zone = request.form.get("zone", "ground")
            age_str = request.form.get("age", "0 months").strip()
            notes = request.form.get("notes", "").strip()

            if not name:
                flash("Plant name is required.", "error")
                return redirect(url_for("add_plant"))

            # Fetch and cache Perenual data
            try:
                perenual_data = get_plant_details(perenual_id)
            except Exception as e:
                flash(f"Could not fetch plant details: {e}", "error")
                return redirect(url_for("add_plant"))

            age_months = _parse_age_months(age_str)

            new_plant = {
                "id": str(uuid.uuid4()),
                "name": name,
                "species_query": request.form.get("species_query", ""),
                "perenual_id": perenual_id,
                "zone": zone,
                "age_months": age_months,
                "age_input": age_str,
                "date_added": datetime.now(timezone.utc).isoformat(),
                "last_watered": None,
                "notes": notes,
                "cached_perenual_data": perenual_data,
            }

            plants = _load_plants()
            plants.append(new_plant)
            _save_plants(plants)

            flash(f"{name} added successfully!", "success")
            return redirect(url_for("plant_detail", plant_id=new_plant["id"]))

        # ---- Step 2: Search Perenual and show top 3 ----
        species_query = request.form.get("species_query", "").strip()
        form_data = {
            "name": request.form.get("name", "").strip(),
            "zone": request.form.get("zone", "ground"),
            "age": request.form.get("age", "").strip(),
            "notes": request.form.get("notes", "").strip(),
            "species_query": species_query,
        }

        if not species_query:
            flash("Please enter a species or common name to search.", "error")
        else:
            try:
                search_results = search_plants(species_query, max_results=3)
                if not search_results:
                    flash(f"No results found for '{species_query}'. Try a different name.", "warning")
            except Exception as e:
                flash(f"Plant search failed: {e}", "error")

    return render_template(
        "add_plant.html",
        search_results=search_results,
        form_data=form_data,
    )


@app.route("/plant/<plant_id>/water", methods=["POST"])
def mark_watered(plant_id):
    """Mark a plant as watered right now."""
    plants = _load_plants()
    for plant in plants:
        if plant["id"] == plant_id:
            plant["last_watered"] = datetime.now(timezone.utc).isoformat()
            break
    _save_plants(plants)
    flash("Watering logged.", "success")
    return redirect(url_for("plant_detail", plant_id=plant_id))


@app.route("/plant/<plant_id>/delete", methods=["POST"])
def delete_plant(plant_id):
    """Remove a plant from the list."""
    plants = [p for p in _load_plants() if p["id"] != plant_id]
    _save_plants(plants)
    flash("Plant removed.", "success")
    return redirect(url_for("index"))


@app.route("/plant/<plant_id>/edit", methods=["GET", "POST"])
def edit_plant(plant_id):
    """Edit plant name, zone, age, and notes."""
    plants = _load_plants()
    plant = next((p for p in plants if p["id"] == plant_id), None)
    if not plant:
        flash("Plant not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        plant["name"] = request.form.get("name", plant["name"]).strip()
        plant["zone"] = request.form.get("zone", plant["zone"])
        age_str = request.form.get("age", "").strip()
        if age_str:
            plant["age_months"] = _parse_age_months(age_str)
            plant["age_input"] = age_str
        plant["notes"] = request.form.get("notes", "").strip()
        _save_plants(plants)
        flash("Plant updated.", "success")
        return redirect(url_for("plant_detail", plant_id=plant_id))

    return render_template("edit_plant.html", plant=plant)


@app.route("/check", methods=["POST"])
def manual_check():
    """Manually trigger a check + email (called from dashboard)."""
    result = run_check()
    alert_count = len(result.get("alerts", []))
    ok_count = len(result.get("ok", []))
    if result.get("error"):
        flash(f"Check failed: {result['error']}", "error")
    elif alert_count == 0:
        flash(f"Check complete — all {ok_count} plant(s) are OK. No email sent.", "success")
    else:
        flash(
            f"Check complete — {alert_count} alert(s) found across your plants. "
            f"Email sent to {app.config.get('EMAIL_RECIPIENT', 'your inbox')}.",
            "warning",
        )
    return redirect(url_for("index"))


@app.route("/api/weather")
def api_weather():
    """JSON endpoint for current weather (used for live refresh on dashboard)."""
    try:
        weather = get_weather()
        return jsonify({"ok": True, "weather": weather})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------------
# Template helpers
# ------------------------------------------------------------------

def _status_from_alerts(alerts: list[dict]) -> str:
    if not alerts:
        return "ok"
    levels = [a.get("level", "warning") for a in alerts]
    if "critical" in levels:
        return "critical"
    return "warning"


@app.template_filter("age_label")
def age_label_filter(age_months: int) -> str:
    from alerts import _age_label
    return _age_label(age_months)


@app.template_filter("days_since")
def days_since_filter(last_watered_str: str | None) -> str:
    from alerts import _days_since_watered
    days = _days_since_watered(last_watered_str)
    if days is None:
        return "Never"
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
