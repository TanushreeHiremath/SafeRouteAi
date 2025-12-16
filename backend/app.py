# backend/app.py

from flask import Flask
from flask_cors import CORS
from config import Config
from auth.routes import auth_bp
from routes.weather import weather_bp
from routes.safety import safety_bp
from routes.feedback import feedback_bp   # <--- NEW
from db import crime_segments_col
import pandas as pd
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)

    # Register API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(safety_bp)
    app.register_blueprint(feedback_bp)   # <--- NEW

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


def bootstrap_crime_data():
    """
    Load datasets into MongoDB (only once).
    If data already exists, skip loading.
    """
    if crime_segments_col.estimated_document_count() > 0:
        print("✔ Crime dataset already exists in MongoDB — skipping import.")
        return

    print("\n📂 Importing crime datasets into MongoDB...\n")

    # Universal loader supporting CSV and Excel
    def load_dataset(path, city):
        if not os.path.exists(path):
            print(f"⚠ WARNING: File not found → {path}")
            return

        ext = os.path.splitext(path)[-1].lower()

        try:
            if ext == ".csv":
                df = pd.read_csv(path, encoding="latin-1")
            elif ext in [".xlsx", ".xls"]:
                df = pd.read_excel(path)
            else:
                print(f"❌ Unsupported file format: {ext}")
                return
        except Exception as e:
            print(f"❌ Error reading {path}: {e}")
            return

        # Normalize column names
        df.columns = [str(c).strip().lower() for c in df.columns]
        df["city"] = city.lower()

        # Convert to list of dicts and push to MongoDB
        records = df.to_dict(orient="records")

        if len(records) > 0:
            crime_segments_col.insert_many(records)
            print(f"✅ Imported {len(records)} records for {city}")
        else:
            print(f"⚠ No records found in {path}")

    # Load Bengaluru & Delhi data using variables from config
    load_dataset(Config.BENGALURU_DATA, "Bengaluru")
    load_dataset(Config.DELHI_DATA, "Delhi")

    print("\n✔ Dataset import complete.\n")


if __name__ == "__main__":
    bootstrap_crime_data()
    app = create_app()
    print("\n🚀 Server running at: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
