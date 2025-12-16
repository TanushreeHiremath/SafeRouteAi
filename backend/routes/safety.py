# backend/routes/safety.py
import math
from collections import Counter

import requests
from flask import Blueprint, request, jsonify

from db import crime_segments_col, feedback_col
from ml.safety_predictor import predict_safety_score, categorize
from config import Config

safety_bp = Blueprint("safety", __name__, url_prefix="/api")


# ---------- Generic helpers ----------

def safe_num(value):
    """Convert any value to a sane float: NaN/None/invalid -> 0."""
    try:
        if value is None:
            return 0.0
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f
    except (TypeError, ValueError):
        return 0.0


def sanitize_for_json(obj):
    """Recursively clean NaN/inf so response is valid JSON."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    return obj


# ---------- Weather ----------

def adjust_for_weather(score: float, weather: dict, weight: str = "medium") -> float:
    """
    Slightly decrease score for bad weather / night time.
    weight ∈ {low, medium, high}
    """
    if not weather:
        return score

    factor = {"low": 0.2, "medium": 0.4, "high": 0.7}.get(weight, 0.4)

    try:
        cond = weather["weather"][0]["main"].lower()
        dt = weather["dt"]
        sunrise = weather["sys"]["sunrise"]
        sunset = weather["sys"]["sunset"]
    except Exception:
        return score

    is_night = dt < sunrise or dt > sunset
    delta = 0.0
    if is_night:
        delta -= 0.3 * factor
    if "rain" in cond or "storm" in cond:
        delta -= 0.3 * factor

    score = max(1.0, min(5.0, score + delta))
    return score


def get_weather(lat: float, lon: float):
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={Config.OPENWEATHER_KEY}"
    )
    try:
        return requests.get(url, timeout=5).json()
    except Exception:
        return None


# ---------- Mapbox helpers ----------

def geocode_place(text: str, city: str):
    """
    Mapbox Geocoding: place text → (lon, lat).
    """
    if not text:
        return None

    query = f"{text}, {city}, India"
    url = (
        "https://api.mapbox.com/geocoding/v5/mapbox.places/"
        f"{requests.utils.quote(query)}.json"
        f"?limit=1&access_token={Config.MAPBOX_TOKEN}"
    )
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        lon, lat = features[0]["center"]
        return lon, lat
    except Exception as e:
        print("Geocoding error:", e)
        return None


def get_directions(src_lon, src_lat, dst_lon, dst_lat):
    """
    Mapbox Directions: returns up to 3 alternative driving routes with geojson geometry.
    """
    url = (
        "https://api.mapbox.com/directions/v5/mapbox/driving/"
        f"{src_lon},{src_lat};{dst_lon},{dst_lat}"
        f"?alternatives=true&geometries=geojson&overview=full"
        f"&access_token={Config.MAPBOX_TOKEN}"
    )
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        return data.get("routes", [])
    except Exception as e:
        print("Directions error:", e)
        return []


# ---------- Feedback helpers ----------

def get_feedback_stats(street: str, city: str):
    """
    Aggregate feedback for a particular street & city:
    - average rating
    - count of ratings
    - most common issue type
    """
    if not street:
        return None

    street = street.strip().lower()
    city = city.strip().lower()

    docs = list(
        feedback_col.find(
            {"street_name": street, "city": city},
            {"rating": 1, "issue_type": 1},
        )
    )
    if not docs:
        return None

    ratings = [
        doc.get("rating", 0)
        for doc in docs
        if doc.get("rating") is not None
    ]
    if not ratings:
        return None

    avg_rating = sum(ratings) / len(ratings)
    issue_counts = Counter(
        doc.get("issue_type", "")
        for doc in docs
        if doc.get("issue_type")
    )
    top_issue = issue_counts.most_common(1)[0][0] if issue_counts else None

    return {
        "count": len(ratings),
        "avg_rating": avg_rating,
        "top_issue": top_issue,
    }


def build_explanations(
    summary: dict,
    base_score: float,
    final_score: float,
    fb_stats,
    is_best: bool = False,
    is_worst: bool = False,
):
    """
    Build human-readable explanation lines for each route:
    - comparative reason (best / worst / moderate)
    - dataset-based reasons (police, metro, crime mix)
    - feedback-based reasons (ratings & common issues)
    - weather / re-scaling changes
    """
    explanations = []

    # 1) Comparative message based on ranking
    if is_best:
        explanations.append("This is the safest route among the available options.")
    elif is_worst:
        explanations.append("This is the riskiest route compared to other available options.")
    else:
        explanations.append("This route has a moderate safety level compared to the other options.")

    # 2) Dataset based
    police = safe_num(summary.get("Nearest police chowki (km)"))
    metro = safe_num(summary.get("Nearest metro station distance (km)"))
    rape = safe_num(summary.get("Rape"))
    kidnap = safe_num(summary.get("Kidnapping & Abduction_Total"))
    assault = safe_num(summary.get("Assault on Women"))
    acid = safe_num(summary.get("Acid attack"))
    stalking = safe_num(summary.get("Stalking"))
    harass = safe_num(summary.get("Sexual Harassment"))
    other_assault = safe_num(summary.get("Other Assault on Women"))

    violent = rape + kidnap + assault + acid
    non_violent = stalking + harass + other_assault

    if police <= 1.0:
        explanations.append("Segments on this route are close to a police chowki (≤ 1 km).")
    if metro <= 1.0:
        explanations.append("This route is near metro stations, improving access to help.")

    if violent == 0 and non_violent == 0:
        explanations.append("Very low recorded violent and non-violent crimes in the dataset.")
    elif 0 < violent <= 10:
        explanations.append("Some violent crime reported, but at relatively low levels.")
    elif violent > 10:
        explanations.append(
            "Higher levels of violent crimes (rape / assault / kidnapping) recorded in this area."
        )

    if stalking + harass > 0:
        explanations.append("There are reported cases of stalking / harassment on these streets.")

    # 3) Feedback based
    if fb_stats:
        avg = fb_stats["avg_rating"]
        count = fb_stats["count"]
        top_issue = fb_stats["top_issue"]

        if avg <= 2.5:
            msg = f"Recent user feedback is negative (avg {avg:.1f}/5 over {count} reports)"
            if top_issue:
                msg += f", especially about {top_issue.replace('_', ' ')}."
            else:
                msg += "."
            explanations.append(msg)
        elif avg >= 4.0:
            explanations.append(
                f"User feedback so far is positive (avg {avg:.1f}/5 over {count} reports)."
            )

    # 4) Base vs final
    if abs(final_score - base_score) > 0.2:
        if final_score < base_score:
            explanations.append("Score reduced slightly due to weather or recent feedback.")
        else:
            explanations.append("Score boosted slightly because it is the best option available.")

    return explanations


# ---------- Routes ----------

@safety_bp.post("/routes")
def safe_routes():
    """
    Main route scoring endpoint.

    Request JSON:
    {
      "source_text": "MG Road",
      "dest_text": "Electronic City",
      "city": "bengaluru" | "delhi",
      "weather_weight": "low" | "medium" | "high"
    }
    (or fallback with {source: {lat,lon}, dest: {lat,lon}})
    """
    data = request.get_json(force=True)
    city = data.get("city", "bengaluru").lower()
    weight = data.get("weather_weight", "medium")

    # ---- Handle source/destination text ----
    src_text = data.get("source_text")
    dst_text = data.get("dest_text")

    src_coords = dst_coords = None
    if src_text and dst_text:
        src_coords = geocode_place(src_text, city)
        dst_coords = geocode_place(dst_text, city)

    # Fallback to direct coordinates if geocoding fails
    if not src_coords or not dst_coords:
        source = data.get("source")
        dest = data.get("dest")
        if not source or not dest:
            return jsonify({"error": "source/dest text or coordinates required"}), 400
        src_coords = (float(source["lon"]), float(source["lat"]))
        dst_coords = (float(dest["lon"]), float(dest["lat"]))

    src_lon, src_lat = src_coords
    dst_lon, dst_lat = dst_coords

    # ---- Weather ----
    weather = get_weather(src_lat, src_lon)

    # ---- Mapbox directions ----
    mapbox_routes = get_directions(src_lon, src_lat, dst_lon, dst_lat)
    if not mapbox_routes:
        return jsonify({"routes": []}), 200

    # ---- Crime segments ----
    segments = list(crime_segments_col.find({"city": city}))
    if not segments:
        return jsonify({"routes": []}), 200

    # Split crime segments roughly across routes
    num_routes = min(3, len(mapbox_routes))
    chunk = max(1, len(segments) // num_routes)
    route_segment_groups = []
    start = 0
    for i in range(num_routes):
        end = start + chunk if i < num_routes - 1 else len(segments)
        route_segment_groups.append(segments[start:end])
        start = end

    # ---- First pass: compute raw scores for ranking ----
    raw_scores_all = []
    for idx in range(num_routes):
        segs = route_segment_groups[idx]
        if not segs:
            raw_scores_all.append(None)
            continue

        scores = [predict_safety_score(seg) for seg in segs]
        raw_score = sum(scores) / len(scores)
        raw_scores_all.append(raw_score)

    # Identify best (highest raw) and worst (lowest raw) routes
    valid_scores = [(i, s) for i, s in enumerate(raw_scores_all) if s is not None]
    if valid_scores:
        best_route_index = max(valid_scores, key=lambda x: x[1])[0]
        worst_route_index = min(valid_scores, key=lambda x: x[1])[0]
    else:
        best_route_index = worst_route_index = 0

    # ---- Second pass: build payload with weather + feedback + explanations ----
    routes_payload = []

    for idx in range(num_routes):
        segs = route_segment_groups[idx]
        if not segs:
            continue

        api_route = mapbox_routes[idx]

        raw_score = raw_scores_all[idx]
        if raw_score is None:
            continue

        # --- Apply weather modifier ---
        score_after_weather = adjust_for_weather(raw_score, weather, weight)

        # --- Feedback stats for the representative street ---
        example = segs[0]
        street_name = (
            example.get("street name")
            or example.get("Street name")
            or example.get("sreet name")
            or ""
        )
        fb_stats = get_feedback_stats(street_name, city)

        # --- Feedback penalty / boost ---
        final_score = score_after_weather
        if fb_stats and fb_stats["avg_rating"] <= 2.5:
            final_score -= 0.3  # small penalty for bad feedback
        elif fb_stats and fb_stats["avg_rating"] >= 4.0:
            final_score += 0.2  # small boost for good feedback

        # Clamp 1–5
        final_score = max(1.0, min(5.0, final_score))
        label = categorize(final_score)

        # Distances & geometry from Mapbox
        distance_km = api_route.get("distance", 0) / 1000.0
        duration_min = api_route.get("duration", 0) / 60.0
        geometry = api_route.get("geometry", {})

        # Summary card info
        summary = {
            "Street name": street_name,
            "Nearest metro station distance (km)": safe_num(
                example.get("nearest metro station distance(in km)", 0)
            ),
            "Type of road": example.get("type of road"),
            "Crime (total index)": safe_num(example.get("crime", 0)),
            "Nearest police chowki (km)": safe_num(
                example.get("nearest police chowki", 0)
            ),
            "Population density": safe_num(example.get("population density", 0)),
            "Rape": safe_num(example.get("rape", 0)),
            "Kidnapping & Abduction_Total": safe_num(
                example.get("kidnapping & abduction_total", 0)
            ),
            "Acid attack": safe_num(example.get("acid attack", 0)),
            "Assault on Women": safe_num(example.get("assault on women", 0)),
            "Sexual Harassment": safe_num(example.get("sexual harassment", 0)),
            "Use of criminal force to women": safe_num(
                example.get("use of criminal force to women", 0)
            ),
            "Stalking": safe_num(example.get("stalking", 0)),
            "Other Assault on Women": safe_num(
                example.get("other assault on women", 0)
            ),
            "District": example.get("district"),
        }

        is_best = idx == best_route_index
        is_worst = idx == worst_route_index

        explanations = build_explanations(
            summary,
            base_score=raw_score,
            final_score=final_score,
            fb_stats=fb_stats,
            is_best=is_best,
            is_worst=is_worst,
        )

        routes_payload.append(
            {
                "route_id": f"route_{idx+1}",
                "name": f"Route Option {idx+1}",
                "distance_km": round(distance_km, 2),
                "duration_min": round(duration_min, 1),
                "avg_safety_score": round(final_score, 2),   # final (shown with color)
                "raw_safety_score": round(raw_score, 2),     # original ML score
                "safety_label": label,
                "summary": summary,
                "geometry": geometry,
                "source_coords": [src_lon, src_lat],
                "dest_coords": [dst_lon, dst_lat],
                "feedback_stats": fb_stats,
                "explanations": explanations,
            }
        )

    payload = {"routes": routes_payload}
    payload = sanitize_for_json(payload)
    return jsonify(payload), 200


# ---------- Live Safety ----------

@safety_bp.get("/live-safety")
def live_safety():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    radius_km = float(request.args.get("radius_km", 5))
    city = request.args.get("city", "bengaluru").lower()

    if not lat or not lon:
        return jsonify({"error": "lat and lon required"}), 400

    segments = list(crime_segments_col.find({"city": city}))
    if not segments:
        return jsonify(
            {
                "lat": float(lat),
                "lon": float(lon),
                "radius_km": radius_km,
                "safety_score": 3.0,
                "safety_label": "moderate",
            }
        )

    scores = [predict_safety_score(seg) for seg in segments]
    avg = sum(scores) / len(scores)
    label = categorize(avg)

    payload = {
        "lat": float(lat),
        "lon": float(lon),
        "radius_km": radius_km,
        "safety_score": round(avg, 2),
        "safety_label": label,
    }
    payload = sanitize_for_json(payload)
    return jsonify(payload), 200
