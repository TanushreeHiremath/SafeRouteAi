from flask import Blueprint, request
import requests
from config import Config

weather_bp = Blueprint("weather", __name__, url_prefix="/api")


@weather_bp.get("/weather")
def get_weather():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if not lat or not lon:
        return {"error": "lat and lon required"}, 400

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={Config.OPENWEATHER_KEY}"
    )
    res = requests.get(url, timeout=10)
    return res.json()
