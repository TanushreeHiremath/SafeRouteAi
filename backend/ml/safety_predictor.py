import os
import joblib
import numpy as np

# Load the single best model selected during training
BASE_DIR = os.path.dirname(__file__)
FINAL_MODEL_PATH = os.path.join(BASE_DIR, "final_safety_model.pkl")

_bundle = joblib.load(FINAL_MODEL_PATH)
_model = _bundle["model"]
FEATURE_COLS = _bundle["features"]
METRICS = _bundle.get("metrics", {})


def build_feature_vector(street_row: dict) -> np.ndarray:
    """
    Convert a MongoDB street document into a numeric feature vector
    using the same column order as the training phase.
    Unknown / missing features → 0.
    """
    values = []
    for col in FEATURE_COLS:
        val = street_row.get(col, 0)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = 0.0
        values.append(val)
    return np.array([values], dtype=float)


def predict_safety_score(street_row: dict) -> float:
    """
    Predict safety score (1–5) for a single street row using the final model.
    """
    x = build_feature_vector(street_row)
    score = float(_model.predict(x)[0])
    # Clamp between [1, 5]
    score = max(1.0, min(5.0, score))
    return score


def categorize(score: float) -> str:
    """
    Map numeric score to label:
    < 2.5  -> 'unsafe'
    < 3.5  -> 'moderate'
    else   -> 'very_safe'
    """
    if score < 2.5:
        return "unsafe"
    elif score < 3.5:
        return "moderate"
    return "very_safe"
