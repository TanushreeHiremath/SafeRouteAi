import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
from config import Config


def load_city(path: str, city_name: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[-1].lower()

    if ext == ".csv":
        df = pd.read_csv(path, encoding="latin-1")
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    df.columns = [str(c).strip().lower() for c in df.columns]
    df["city"] = city_name.lower()
    return df


def col_like(df: pd.DataFrame, substr: str):
    substr = substr.lower()
    for c in df.columns:
        if substr in c:
            return c
    return None


def compute_baseline_safety(df: pd.DataFrame) -> pd.DataFrame:
    rape_col = col_like(df, "rape")
    kidnap_col = col_like(df, "kidnap")
    acid_col = col_like(df, "acid")
    assault_col = col_like(df, "assault")

    sex_har_col = col_like(df, "sexual har")
    force_col = col_like(df, "criminal force")
    stalk_col = col_like(df, "stalk")
    other_assault_col = col_like(df, "other assault")

    crime_total_col = col_like(df, "crime")
    metro_dist_col = col_like(df, "metro")
    police_dist_col = col_like(df, "police")
    pop_density_col = col_like(df, "population")
    road_type_col = col_like(df, "type of road")

    numeric_cols = [
        crime_total_col, rape_col, kidnap_col, acid_col, assault_col,
        sex_har_col, force_col, stalk_col, other_assault_col,
        metro_dist_col, police_dist_col, pop_density_col
    ]

    for c in numeric_cols:
        if c and df[c].dtype == "O":
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in numeric_cols:
        if c:
            df[c] = df[c].fillna(0)

    violent = 0
    for c in [rape_col, kidnap_col, assault_col, acid_col]:
        if c:
            violent += df[c]

    non_violent = 0
    for c in [sex_har_col, force_col, stalk_col, other_assault_col]:
        if c:
            non_violent += df[c]

    df["violent_crimes"] = violent
    df["non_violent_crimes"] = non_violent

    if crime_total_col:
        df["total_crimes"] = df[crime_total_col]
    else:
        df["total_crimes"] = df["violent_crimes"] + df["non_violent_crimes"]

    df["total_crimes"] = df["total_crimes"].fillna(0)

    min_c = df["total_crimes"].min()
    max_c = df["total_crimes"].max()
    denom = (max_c - min_c) if max_c != min_c else 1

    df["crime_norm"] = (df["total_crimes"] - min_c) / denom
    df["safety_base"] = 5 - 4 * df["crime_norm"]

    safety_adj = df["safety_base"].copy()

    if police_dist_col:
        p = df[police_dist_col]
        safety_adj += (p <= 0.5) * 0.4
        safety_adj += (p <= 1.0) * 0.2

    if metro_dist_col:
        m = df[metro_dist_col]
        safety_adj += (m <= 0.5) * 0.2
        safety_adj += (m <= 1.0) * 0.1

    if pop_density_col:
        pop = df[pop_density_col]
        safety_adj -= (pop > 25000) * 0.2
        safety_adj -= (pop > 35000) * 0.3

    if road_type_col:
        road = df[road_type_col].astype(str).str.lower()
        safety_adj += (road.str.contains("major") | road.str.contains("highway")) * 0.3
        safety_adj -= (road.str.contains("residential")) * 0.1

    df["safety_score_calculated"] = safety_adj.clip(1, 5)

    return df


def choose_best_model(X_train, X_test, y_train, y_test):
    dt = DecisionTreeRegressor(random_state=42)
    dt.fit(X_train, y_train)
    dt_pred = dt.predict(X_test)

    rf = RandomForestRegressor(n_estimators=250, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)

    dt_r2 = r2_score(y_test, dt_pred)
    rf_r2 = r2_score(y_test, rf_pred)

    print("\n===== MODEL PERFORMANCE =====")
    print("Decision Tree:")
    print(f"  MSE: {mean_squared_error(y_test, dt_pred):.4f}")
    print(f"  MAE: {mean_absolute_error(y_test, dt_pred):.4f}")
    print(f"  R2 : {dt_r2:.4f}\n")

    print("Random Forest:")
    print(f"  MSE: {mean_squared_error(y_test, rf_pred):.4f}")
    print(f"  MAE: {mean_absolute_error(y_test, rf_pred):.4f}")
    print(f"  R2 : {rf_r2:.4f}")
    print("================================\n")

    if dt_r2 >= rf_r2:
        print("Selected best model: DECISION_TREE")
        return dt, {"DecisionTree_R2": dt_r2}
    else:
        print("Selected best model: RANDOM_FOREST")
        return rf, {"RandomForest_R2": rf_r2}


def main():
    bengaluru = load_city(Config.BENGALURU_DATA, "Bengaluru")
    delhi = load_city(Config.DELHI_DATA, "Delhi")

    df = pd.concat([bengaluru, delhi], ignore_index=True)
    df = compute_baseline_safety(df)

    target = "safety_score_calculated"
    features = [c for c in df.columns if df[c].dtype != "O" and c != target]

    X = df[features]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    best_model, metrics = choose_best_model(X_train, X_test, y_train, y_test)

    save_dir = os.path.dirname(__file__)
    final_path = os.path.join(save_dir, "final_safety_model.pkl")

    joblib.dump({"model": best_model, "features": features, "metrics": metrics}, final_path)

    print(f"✔ Model saved successfully at:\n{final_path}")


if __name__ == "__main__":
    main()
