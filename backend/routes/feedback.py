# backend/routes/feedback.py
from flask import Blueprint, request, jsonify
from datetime import datetime

from db import feedback_col

feedback_bp = Blueprint("feedback", __name__, url_prefix="/api")


@feedback_bp.post("/feedback")
def submit_feedback():
    """
    Body:
    {
      "route_id": "...",
      "rating": 1-5,
      "street_name": "...",
      "issue_type": "...",
      "comments": "...",
      "city": "bengaluru" | "delhi"
    }
    """
    data = request.get_json(force=True)

    try:
        rating = int(data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0

    if rating < 1 or rating > 5:
        return jsonify({"error": "rating must be between 1 and 5"}), 400

    doc = {
        "route_id": data.get("route_id"),
        "city": (data.get("city") or "").lower(),
        "street_name": (data.get("street_name") or "").strip().lower(),
        "issue_type": (data.get("issue_type") or "").strip().lower(),
        "comments": data.get("comments") or "",
        "rating": rating,
        "created_at": datetime.utcnow(),
    }

    feedback_col.insert_one(doc)
    return jsonify({"ok": True}), 201
