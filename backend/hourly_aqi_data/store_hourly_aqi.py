from dotenv import load_dotenv
load_dotenv()

import requests
import psycopg2
import joblib
import pandas as pd
import os
from datetime import datetime

# -----------------------
# API Configuration
# -----------------------

API_KEY = os.environ.get("OPENWEATHER_API_KEY")
LAT = 28.6139
LON = 77.2090

url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={LAT}&lon={LON}&appid={API_KEY}"

# -----------------------
# Database Connection
# -----------------------

db_url = os.environ.get("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(db_url)
else:
    conn = psycopg2.connect(
        database="aqi_database",
        user="postgres",
        password="shweta27",
        host="localhost",
        port="5432",
    )

cursor = conn.cursor()

# -----------------------
# Load ML Model (Safe Path)
# -----------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "..", "model", "best_aqi_model.pkl")

model = joblib.load(MODEL_PATH)

# -----------------------
# Fetch API Data
# -----------------------

try:
    response = requests.get(url, timeout=10)
    data = response.json()

    components = data["list"][0]["components"]

    pm2_5 = components["pm2_5"]
    pm10 = components["pm10"]
    no = components["no"]
    no2 = components["no2"]
    co = components["co"]
    so2 = components["so2"]
    o3 = components["o3"]

    print("API data fetched successfully")

except Exception as e:

    print("API failed. Using previous data...")

    cursor.execute("""
        SELECT pm2_5, pm10, no, no2, co, so2, o3
        FROM hourly_aqi_data
        ORDER BY id DESC
        LIMIT 1
    """)

    last_data = cursor.fetchone()

    if last_data is None:
        print("No previous data available.")
        exit()

    pm2_5, pm10, no, no2, co, so2, o3 = last_data

# -----------------------
# Feature Engineering
# -----------------------

today = datetime.now()

nox = no + no2
nh3 = 0
benzene = 0
toluene = 0

pm_ratio = pm2_5 / pm10 if pm10 != 0 else 0
nox_total = nox

year = today.year
month = today.month
day = today.day
day_of_week = today.weekday()
week_of_year = today.isocalendar()[1]

# -----------------------
# Create Model Features
# -----------------------

features = pd.DataFrame(
    [
        {
            "pm2.5": pm2_5,
            "pm10": pm10,
            "no": no,
            "no2": no2,
            "nox": nox,
            "nh3": nh3,
            "co": co,
            "so2": so2,
            "o3": o3,
            "benzene": benzene,
            "toluene": toluene,
            "pm_ratio": pm_ratio,
            "nox_total": nox_total,
            "year": year,
            "month": month,
            "day": day,
            "day_of_week": day_of_week,
            "week_of_year": week_of_year,
        }
    ]
)

# -----------------------
# Predict AQI
# -----------------------

predicted_aqi = model.predict(features)[0]

# -----------------------
# Insert Data into PostgreSQL
# -----------------------

cursor.execute(
    """
INSERT INTO hourly_aqi_data (
pm2_5, pm10, no, no2, nox, nh3, co, so2, o3,
benzene, toluene, pm_ratio, nox_total,
year, month, day, day_of_week, week_of_year,
predicted_aqi
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,
        %s,%s,%s,%s,
        %s,%s,%s,%s,%s,
        %s)
""",
    (
        pm2_5,
        pm10,
        no,
        no2,
        nox,
        nh3,
        co,
        so2,
        o3,
        benzene,
        toluene,
        pm_ratio,
        nox_total,
        year,
        month,
        day,
        day_of_week,
        week_of_year,
        predicted_aqi,
    ),
)

conn.commit()

print("AQI Stored Successfully")
print("Predicted AQI:", predicted_aqi)

# -----------------------
# Close Connections
# -----------------------

cursor.close()
conn.close()
