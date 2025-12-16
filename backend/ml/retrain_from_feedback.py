# backend/ml/retrain_from_feedback.py
import os
from datetime import datetime

import pandas as pd

from config import Config
from db import feedback_col
from ml.train_model import (
    load_city,
    compute_baseline_safety,
    choose_best_model,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
import joblib


ISSUE_TO_COLUMN = {
    "stalking": "stalking",
    "harassment": "sexual harassment",
    "assault_on_women": "assault on women",
    "kidnapping_abduction": "kidnapping & abduction_total",
    "use_of_criminal_force": "use of criminal force to women",
    "acid_attack_threat": "acid attack",
    "other_assault": "other assault on women",
}


def apply_feedback(df: pd.DataFrame, city: str) -> pd.DataFrame:
    """
    For each low-rating feedback item, increment appropriate crime column
    on that street, so retraining will treat it as riskier.
    """
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    fb_docs = list(feedback_col.find({"city": city.lower()}))
    if not fb_docs:
        return df

    print(f"Applying {len(fb_docs)} feedback docs for {city}...")

    for doc in fb_docs:
        rating = int(doc.get("rating", 0))
        street = (doc.get("street_name") or "").strip().lower()
        issue = (doc.get("issue_type") or "").strip().lower()

        # Only use clearly "bad" ratings
        if rating >= 3 or not street:
            continue

        col_name = ISSUE_TO_COLUMN.get(issue)
        if not col_name:
            continue

        mask = df["street name"].str.strip().str.lower() == street
        if not mask.any():
            continue

        col = col_name.lower()
        if col not in df.columns:
            continue

        # Increment by small amount per bad rating
        df.loc[mask, col] = df.loc[mask, col].fillna(0) + (4 - rating)

    return df


def main():
    # Load original data like train_model
    bengaluru = load_city(Config.BENGALURU_DATA, "bengaluru")
    delhi = load_city(Config.DELHI_DATA, "delhi")

    # Apply feedback penalties BEFORE computing safety
    bengaluru = apply_feedback(bengaluru, "bengaluru")
    delhi = apply_feedback(delhi, "delhi")

    df = pd.concat([bengaluru, delhi], ignore_index=True)

    # Safety label from crime + penalties
    df = compute_baseline_safety(df)

    target_col = "safety_score_calculated"
    numeric_cols = [c for c in df.columns if df[c].dtype != "O" and c != target_col]
    X = df[numeric_cols]
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    best_model, metrics = choose_best_model(X_train, X_test, y_train, y_test)

    # Retrain both models on full train set for saving
    dt_model = DecisionTreeRegressor(random_state=42)
    dt_model.fit(X_train, y_train)

    rf_model = RandomForestRegressor(n_estimators=250, random_state=42)
    rf_model.fit(X_train, y_train)

    os.makedirs(os.path.join("backend", "ml"), exist_ok=True)

    joblib.dump(
        {"model": dt_model, "features": numeric_cols},
        os.path.join("backend", "ml", "decision_tree_safety.pkl"),
    )
    joblib.dump(
        {"model": rf_model, "features": numeric_cols},
        os.path.join("backend", "ml", "random_forest_safety.pkl"),
    )
    joblib.dump(
        {
            "model": best_model,
            "features": numeric_cols,
            "metrics": metrics,
            "retrained_at": datetime.utcnow().isoformat(),
        },
        os.path.join("backend", "ml", "final_safety_model.pkl"),
    )

    print("✅ Retrained model saved to final_safety_model.pkl")


if __name__ == "__main__":
    main()
