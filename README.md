#  Plant Care Assistant

A lightweight Flask web app that tracks your plants across multiple zones and sends email alerts when conditions require action — based on each plant's actual care requirements combined with live Tallinn weather data.

## The Problem

Plants in Tallinn face rapidly changing weather. A tomato on your terrace can't tolerate below 5°C, but there's no tool that knows *that specific threshold* for *your specific plant* and cross-references it with *tonight's actual forecast* to tell you to cover it before dark.


## How It Works

When a check runs (every 3 hours automatically, or manually on demand):

1. Live weather is fetched for Tallinn from **Open-Meteo** (primary) with **OpenWeatherMap** as fallback
2. Each plant's care tolerances are pulled from the **Perenual API** (min temperature, watering needs, drought tolerance)
3. Alert logic combines plant tolerance + zone exposure + forecast — no AI, pure rules
4. If any alert fires, one consolidated email is sent listing every plant that needs attention

## Zones

| Zone | Exposure | Notes |
|---|---|---|
| Greenhouse | Enclosed | Heat stress alerts, frost warnings only on severe drops |
| Terrace | Partial | Cover needed, wind risk, frost warnings |
| Ground | Open | All alerts including heavy rain / waterlogging |


## Alert Types

| Alert | Trigger |
|---|---|
| Frost Warning | Forecast < 0°C in next 12h |
| Cover Needed | Forecast < plant's min temperature, terrace or ground |
| Water Needed | Days since watered exceeds plant's interval AND < 5mm rain forecast |
| Wind Risk | Wind > 12 m/s AND plant is under 12 months old |
| Heat Stress | Forecast > 30°C AND plant is not drought tolerant |
| Heavy Rain | Rain > 20mm/24h on ground zone |

## Features

- Add plants by searching the Perenual database — top 3 results shown as a picker
- Enter plant age as natural text: `6 months`, `2 years`, `1 year 3 months`
- Per-plant watering log with one-click "Mark as Watered"
- Edit plant details (name, zone, age, notes) without re-fetching species data
- Live weather bar on the dashboard showing current Tallinn conditions
- Background scheduler checks every 3 hours, email only sent when alerts exist
- Manual "Run Check Now" button on the dashboard

## Tech Stack

- **Python + Flask** — web framework
- **Open-Meteo** — primary weather (no API key required)
- **OpenWeatherMap** — fallback weather
- **Perenual API** — plant care data
- **APScheduler** — background job scheduler
- **smtplib** — email via Gmail SMTP
- **python-dotenv** — environment variable management
- No database — plant data stored in `data/plants.json`

## Project Structure

```
/
├── app.py                  # Flask routes
├── weather.py              # Open-Meteo + OWM fallback
├── plant_api.py            # Perenual search, detail fetch, cache
├── alerts.py               # Alert logic: plant tolerance + zone + weather
├── email_sender.py         # Consolidated HTML email via smtplib
├── scheduler.py            # APScheduler background job every 3h
├── config.py               # Loads .env, exposes constants
├── data/
│   └── plants.json         # Plant records and watering logs
├── templates/
│   ├── index.html          # Zone dashboard
│   ├── add_plant.html      # Add plant with species picker
│   ├── plant_detail.html   # Single plant view + alerts
│   └── edit_plant.html     # Edit plant details
├── static/
│   └── style.css
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

### 1. Clone and install.

```bash
pip install -r requirements.txt
```

### 2. Get API keys

| Service | Where to register | Cost |
|---|---|---|
| Perenual | [perenual.com/docs](https://perenual.com/docs/api) | Free, 100 req/day |
| OpenWeatherMap | [openweathermap.org/api](https://openweathermap.org/api) | Free tier |
| Open-Meteo | No registration needed | Free |

For Gmail — enable 2-factor auth on your Google account, then go to:
**Google Account → Security → App Passwords** and create a password for Mail.

### 3. Configure `.env`

```bash
cp .env.example .env
```

Fill in your values:

```env
OPENWEATHERMAP_API_KEY=your_key_here
PERENUAL_API_KEY=your_key_here
EMAIL_SENDER=your@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENT=your@gmail.com
TALLINN_LAT=59.437
TALLINN_LON=24.753
SECRET_KEY=change-me-to-something-random
```

### 4. Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

## Usage

### Adding a plant
1. Click **+ Add Plant**
2. Enter a name, species (e.g. `tomato`, `lavender`), zone, age, and optional notes
3. Click **Search Species** — the top 3 Perenual matches are shown
4. Select the correct species and confirm
5. Plant is saved with all care data cached locally

### Watering log
- Click **Mark as Watered** on the dashboard card or plant detail page
- The app tracks days since last watering and compares against the plant's required interval

### Manual check
- Click **Run Check Now** on the dashboard
- Checks all plants against current weather and sends an email if any alerts fire

## Email Alert Format

```
Subject: Plant Alert — Tallinn, 26 Apr 2026, 22:00 UTC

Current: 4°C | Wind: 14 m/s | Rain 24h: 0.0mm

COVER NEEDED
  • Big Tom (6 months old) — Terrace
    Cannot tolerate below 5°C. Tonight forecast: 2°C.
    Note: "Slightly yellowing lower leaves"
    → Cover or move inside before dark.

WATER NEEDED
  • Lavender (2 years old) — Ground
    Average watering. Last watered 5 days ago. No rain forecast.
    → Water today.

No issues detected: Greenhouse Rose, Basil
```

## Notes

- Species data from Perenual is cached inside `plants.json` after the first fetch — subsequent runs do not hit the API again for existing plants
- The Perenual free tier allows 100 requests per day which is sufficient for personal use
- `data/plants.json` is not gitignored — your plant list persists across restarts and can be committed if desired 

