import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change_this_secret")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/saferoute_ai")
    MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "YOUR_MAPBOX_TOKEN")
    OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "YOUR_OPENWEATHER_KEY")
    # paths to datasets
    BENGALURU_DATA = os.getenv(
        "BENGALURU_DATA", "backend/data/crime_bengaluru.xlsx"
    )
    DELHI_DATA = os.getenv(
        "DELHI_DATA", "backend/data/crime_delhi.xlsx"
    )
