import os
from dotenv import load_dotenv

load_dotenv()

# Weather
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
TALLINN_LAT = float(os.getenv("TALLINN_LAT", "59.437"))
TALLINN_LON = float(os.getenv("TALLINN_LON", "24.753"))

# Plant API
PERENUAL_API_KEY = os.getenv("PERENUAL_API_KEY", "")

# Email
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# App
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "plants.json")
SECRET_KEY = os.getenv("SECRET_KEY", "samudika-plant-care-secret")

# Zone exposure levels — used in alert logic
# "open"     = fully exposed to elements
# "partial"  = some shelter but not enclosed
# "enclosed" = protected environment (greenhouse)
ZONE_EXPOSURE = {
    "ground":      "open",
    "terrace":     "partial",
    "greenhouse":  "enclosed",
}

# Watering interval in days derived from Perenual watering field
WATERING_INTERVALS = {
    "frequent":  2,
    "average":   4,
    "minimum":   7,
    "none":      14,
}
