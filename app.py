from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import numpy as np
import joblib
import os
import requests
from datetime import datetime, timedelta
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import random
from backend.scheduler import start_scheduler

# ---------------------------------------------------
# Flask Configuration
# ---------------------------------------------------

app = Flask(
    __name__, template_folder="frontend/templates", static_folder="frontend/static"
)

app.secret_key = os.environ.get("SECRET_KEY", "d2233757fccb64801cd4b008f6fa00f1827d91730a85324a657112d5895f05f9")

# ---------------------------------------------------
# Email Configuration
# ---------------------------------------------------

app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "shwetagurram9@gmail.com")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "ylsq azsa wboh izhu")

mail = Mail(app)

# ---------------------------------------------------
# Load ML Model
# ---------------------------------------------------

model_path = os.path.join("backend", "model", "best_aqi_model.pkl")

try:
    model = joblib.load(model_path)
    print("Model loaded successfully")
except Exception as e:
    print("Model loading error:", e)
    model = None

# ---------------------------------------------------
# OpenWeather API
# ---------------------------------------------------

API_KEY = os.environ.get("OPENWEATHER_API_KEY")
LAT = 28.6139
LON = 77.2090

# ---------------------------------------------------
# Get Pollutant Data
# ---------------------------------------------------


def get_waqi_pollutants():
    """Secondary real-time source: World Air Quality Index API (free demo token)."""
    try:
        url = f"https://api.waqi.info/feed/geo:{LAT};{LON}/?token=demo"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("status") != "ok":
            return None

        iaqi = data["data"].get("iaqi", {})
        pm25 = iaqi.get("pm25", {}).get("v", 0)
        pm10 = iaqi.get("pm10", {}).get("v", 0)
        no2  = iaqi.get("no2",  {}).get("v", 0)
        so2  = iaqi.get("so2",  {}).get("v", 0)
        o3   = iaqi.get("o3",   {}).get("v", 0)
        co   = iaqi.get("co",   {}).get("v", 0) * 100  # WAQI co is in ppm*100

        pm_ratio = pm25 / pm10 if pm10 != 0 else 0

        return {
            "pm2.5": float(pm25),
            "pm10":  float(pm10),
            "no":    0,
            "no2":   float(no2),
            "nox":   float(no2),
            "nh3":   0,
            "co":    float(co),
            "so2":   float(so2),
            "o3":    float(o3),
            "benzene":  0,
            "toluene":  0,
            "pm_ratio": pm_ratio,
            "nox_total": float(no2),
            "is_simulated": False,
        }
    except Exception as e:
        print(f"WAQI fallback error: {e}")
        return None


def get_delhi_pollutants():

    # --- Primary: OpenWeather API ---
    url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={LAT}&lon={LON}&appid={API_KEY}"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code != 200 or "list" not in data:
            raise ValueError(f"OpenWeather API returned status {response.status_code}: {data.get('message', 'Unknown error')}")

        components = data["list"][0]["components"]
        pm25 = components.get("pm2_5", 0)
        pm10 = components.get("pm10", 0)
        no2  = components.get("no2", 0)
        so2  = components.get("so2", 0)
        o3   = components.get("o3", 0)
        co   = components.get("co", 0)
        pm_ratio = pm25 / pm10 if pm10 != 0 else 0

        return {
            "pm2.5": pm25, "pm10": pm10, "no": 0, "no2": no2,
            "nox": no2, "nh3": 0, "co": co, "so2": so2, "o3": o3,
            "benzene": 0, "toluene": 0, "pm_ratio": pm_ratio,
            "nox_total": no2, "is_simulated": False,
        }

    except Exception as e:
        print(f"OpenWeather API Error: {e}. Trying WAQI fallback...")

    # --- Secondary: WAQI real-time API ---
    waqi_data = get_waqi_pollutants()
    if waqi_data:
        print("Using WAQI real-time data for Delhi.")
        return waqi_data

    # --- Last resort: Simulated representative Delhi values ---
    print("Both APIs failed. Using simulated Delhi AQI data.")
    pm25 = 145.5
    pm10 = 230.2
    no2  = 38.4
    so2  = 12.1
    o3   = 58.7
    co   = 1150.0
    pm_ratio = pm25 / pm10
    return {
        "pm2.5": pm25, "pm10": pm10, "no": 0, "no2": no2,
        "nox": no2, "nh3": 0, "co": co, "so2": so2, "o3": o3,
        "benzene": 0, "toluene": 0, "pm_ratio": pm_ratio,
        "nox_total": no2, "is_simulated": True,
    }


# ---------------------------------------------------
# Cigarette Equivalent
# ---------------------------------------------------
def cigarette_equivalent(pm25):

    cig_day = pm25 / 22
    cig_week = cig_day * 7
    cig_month = cig_day * 30

    return round(cig_day, 1), round(cig_week, 1), round(cig_month, 1)


# ---------------------------------------------------
# AQI Indicator Position
# ---------------------------------------------------
def calculate_indicator(aqi):

    if aqi <= 50:
        return (aqi / 50) * 10
    elif aqi <= 100:
        return 10 + ((aqi - 50) / 50) * 10
    elif aqi <= 150:
        return 20 + ((aqi - 100) / 50) * 10
    elif aqi <= 200:
        return 30 + ((aqi - 150) / 50) * 10
    elif aqi <= 300:
        return 40 + ((aqi - 200) / 100) * 20
    else:
        return 60 + ((aqi - 300) / 200) * 40


# ---------------------------------------------------
# AQI Category
# ---------------------------------------------------
def get_aqi_category(aqi):

    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Moderate"
    elif aqi <= 150:
        return "Poor"
    elif aqi <= 200:
        return "Unhealthy"
    elif aqi <= 300:
        return "Severe"
    else:
        return "Hazardous"


# ---------------------------------------------------
# General Solutions
# ---------------------------------------------------
def get_smart_solutions(aqi, diseases=None):

    if diseases is None:
        diseases = []

    solutions = []

    # AQI-based logic
    if aqi <= 50:
        solutions = [
            {"icon": "fa-tree", "text": "Enjoy Outdoors", "sub": "Safe"},
        ]

    elif aqi <= 100:
        solutions = [
            {"icon": "fa-mask-face", "text": "Wear Mask", "sub": "Optional"},
            {
                "icon": "fa-person-walking",
                "text": "Limit Long Exposure",
                "sub": "Advised",
            },
        ]

    elif aqi <= 200:
        solutions = [
            {"icon": "fa-mask-face", "text": "Wear N95 Mask", "sub": "Must"},
            {"icon": "fa-house", "text": "Stay Indoors", "sub": "Recommended"},
            {"icon": "fa-wind", "text": "Use Air Purifier", "sub": "Recommended"},
        ]

    else:  # Severe / Hazardous
        solutions = [
            {"icon": "fa-house", "text": "Stay Indoors", "sub": "Must"},
            {"icon": "fa-wind", "text": "Use Air Purifier", "sub": "Must"},
            {"icon": "fa-car", "text": "Use Car Cabin Filter", "sub": "Must"},
            {"icon": "fa-mask-face", "text": "Wear N95 Mask", "sub": "Must"},
        ]

    # Disease-based additions
    if "asthma" in diseases:
        solutions.append(
            {"icon": "fa-kit-medical", "text": "Carry Inhaler", "sub": "Important"}
        )

    if "heart disease" in diseases:
        solutions.append(
            {
                "icon": "fa-heart-pulse",
                "text": "Avoid Physical Stress",
                "sub": "Important",
            }
        )

    if "allergy" in diseases:
        solutions.append(
            {
                "icon": "fa-head-side-cough",
                "text": "Avoid Dust Exposure",
                "sub": "Recommended",
            }
        )

    return solutions


# ---------------------------------------------------
# Health Recommendation
# ---------------------------------------------------
def get_health_advice(aqi, diseases=None):

    if diseases is None:
        diseases = []

    category = get_aqi_category(aqi)

    required = set()
    optional = set()

    diseases = [d.lower().strip() for d in diseases]

    # -------------------------
    # Risk Level
    # -------------------------
    if aqi <= 50:
        risk = "Low"
    elif aqi <= 100:
        risk = "Moderate"
    elif aqi <= 150:
        risk = "High"
    elif aqi <= 200:
        risk = "Very High"
    else:
        risk = "Critical"

    # -------------------------
    # General Advice
    # -------------------------
    if category == "Good":
        message = "Air quality is good. Enjoy outdoor activities."

    elif category == "Moderate":
        message = "Air quality is acceptable."
        optional.add("Reduce prolonged outdoor exertion.")

    elif category == "Poor":
        message = "Air quality is not ideal."
        required.add("Wear a mask when outside.")

    elif category == "Unhealthy":
        message = "Air quality is unhealthy."
        required.add("Avoid outdoor activities.")

    elif category == "Severe":
        message = "Air quality is very unhealthy."
        required.add("Stay indoors.")
        optional.add("Use air purifier.")

    else:
        message = "Air quality is hazardous."
        required.add("Stay indoors.")
        required.add("Avoid all outdoor exposure.")

    # -------------------------
    # Disease-Based Rules
    # -------------------------
    if "asthma" in diseases:
        if aqi > 100:
            required.add("Carry inhaler at all times.")
        if aqi > 150:
            required.add("Avoid outdoor exposure completely.")

    if "heart disease" in diseases:
        if aqi > 100:
            required.add("Limit physical exertion.")
        if aqi > 150:
            required.add("Stay in clean indoor environment.")

    if "allergy" in diseases:
        if aqi > 50:
            optional.add("Avoid dust and wear mask.")

    if "elderly" in diseases or "children" in diseases:
        if aqi > 100:
            required.add("Limit outdoor activity.")
        if aqi > 150:
            required.add("Stay indoors as much as possible.")

    if not required and not optional:
        optional.add("No major restrictions. Stay safe.")

    return {
        "category": category,
        "risk_level": risk,
        "message": message,
        "required_actions": list(required),
        "optional_actions": list(optional),
    }


# ---------------------------------------------------
# Send Professional AQI Email
# ---------------------------------------------------
def send_aqi_email(user_email, username, aqi, health_data):

    # Dynamic AQI color
    def get_aqi_color(aqi):
        if aqi <= 50:
            return "#2ecc71"
        elif aqi <= 100:
            return "#f1c40f"
        elif aqi <= 200:
            return "#e67e22"
        else:
            return "#e63946"

    aqi_color = get_aqi_color(aqi)

    subject = f"Delhi AQI Alert: {health_data['category']} ({aqi})"



    try:
        msg = Message(
            subject=subject, sender=app.config["MAIL_USERNAME"], recipients=[user_email]
        )

        msg.html = html_body
        mail.send(msg)

        print(f"Email sent to {user_email}")

    except Exception as e:
        print("Email Error:", e)


# ---------------------------------------------------
# Forecast Generator
# ---------------------------------------------------


def generate_forecast(days, model, pollutants):

    results = []
    today = datetime.today()

    for i in range(days):

        future = today + timedelta(days=i)

        features = np.array(
            [
                [
                    pollutants["pm2.5"],
                    pollutants["pm10"],
                    pollutants["no"],
                    pollutants["no2"],
                    pollutants["nox"],
                    pollutants["nh3"],
                    pollutants["co"],
                    pollutants["so2"],
                    pollutants["o3"],
                    pollutants["benzene"],
                    pollutants["toluene"],
                    pollutants["pm_ratio"],
                    pollutants["nox_total"],
                    future.year,
                    future.month,
                    future.day,
                    future.weekday(),
                    future.isocalendar()[1],
                ]
            ]
        )

        pred = int(model.predict(features)[0])

        results.append({"date": future.strftime("%d %b"), "aqi": pred})

    return results


# ---------------------------------------------------
# Home Route
# ---------------------------------------------------
@app.route("/")
@app.route("/forecast/<period>")
def home(period="week"):

    predicted_aqi = None
    category_text = None
    category_class = None
    indicator_position = 0
    forecast_data = []
    health = None
    solutions = []
    recommendations = []
    is_simulated = False

    cig_day = 0
    cig_week = 0
    cig_month = 0

    pollutant_display = {"pm25": 0, "pm10": 0, "no2": 0, "co": 0, "so2": 0, "o3": 0}

    pollutants = get_delhi_pollutants()

    if pollutants:

        is_simulated = pollutants.get("is_simulated", False)
        pollutant_display = {
            "pm25": round(pollutants["pm2.5"], 2),
            "pm10": round(pollutants["pm10"], 2),
            "no2": round(pollutants["no2"], 2),
            "co": round(pollutants["co"], 2),
            "so2": round(pollutants["so2"], 2),
            "o3": round(pollutants["o3"], 2),
        }

        cig_day, cig_week, cig_month = cigarette_equivalent(pollutants["pm2.5"])

    if model and pollutants:

        today = datetime.today()

        features = np.array(
            [
                [
                    pollutants["pm2.5"],
                    pollutants["pm10"],
                    pollutants["no"],
                    pollutants["no2"],
                    pollutants["nox"],
                    pollutants["nh3"],
                    pollutants["co"],
                    pollutants["so2"],
                    pollutants["o3"],
                    pollutants["benzene"],
                    pollutants["toluene"],
                    pollutants["pm_ratio"],
                    pollutants["nox_total"],
                    today.year,
                    today.month,
                    today.day,
                    today.weekday(),
                    today.isocalendar()[1],
                ]
            ]
        )

        predicted_aqi = int(model.predict(features)[0])

        # Get user data
        if "user_id" in session:
            user_diseases = session.get("diseases", [])
            age_group = session.get("age_group", "")
        else:
            user_diseases = []
            age_group = ""

        # Combine safely
        combined = user_diseases.copy()
        if age_group:
            combined.append(age_group)

        # SINGLE HEALTH CALL
        health = get_health_advice(predicted_aqi, combined)

        if predicted_aqi <= 50:
            category_text = "Good"
            category_class = "good"
        elif predicted_aqi <= 100:
            category_text = "Moderate"
            category_class = "moderate"
        elif predicted_aqi <= 150:
            category_text = "Poor"
            category_class = "poor"
        elif predicted_aqi <= 200:
            category_text = "Unhealthy"
            category_class = "unhealthy"
        elif predicted_aqi <= 300:
            category_text = "Severe"
            category_class = "severe"
        else:
            category_text = "Hazardous"
            category_class = "hazardous"

        indicator_position = calculate_indicator(predicted_aqi)

        days = 30 if period == "month" else 7
        forecast_data = generate_forecast(days, model, pollutants)

        user_diseases = session.get("diseases", [])

        # SOLUTIONS LOGIC
        if health:
            for action in health["required_actions"]:
                solutions.append(
                    {
                        "icon": "fa-triangle-exclamation",
                        "text": action,
                        "sub": "Important",
                    }
                )

            for action in health["optional_actions"]:
                solutions.append(
                    {"icon": "fa-lightbulb", "text": action, "sub": "Suggestion"}
                )

        # Initialize
        recommendations = []

        # Get user data
        if "user_id" in session:
            user_diseases = session.get("diseases", [])
            age_group = session.get("age_group", "")
        else:
            user_diseases = []
            age_group = ""

        # Combine
        combined = user_diseases.copy()
        if age_group:
            combined.append(age_group)

        # Get health advice
        health = get_health_advice(predicted_aqi, combined)

        # -------------------------
        # BUILD RECOMMENDATIONS
        # -------------------------
        if health:

            for action in health["required_actions"]:
                recommendations.append(
                    {"icon": "fa-triangle-exclamation", "text": action, "type": "Must"}
                )

            for action in health["optional_actions"]:
                recommendations.append(
                    {"icon": "fa-lightbulb", "text": action, "type": "Suggestion"}
                )

        # Extra smart cards
        if predicted_aqi:

            if predicted_aqi > 150:
                recommendations.append(
                    {
                        "icon": "fa-house",
                        "text": "Stay indoors as much as possible",
                        "type": "Must",
                    }
                )

            if predicted_aqi > 100:
                recommendations.append(
                    {
                        "icon": "fa-mask-face",
                        "text": "Use N95 mask when outside",
                        "type": "Must",
                    }
                )

            if predicted_aqi > 120:
                recommendations.append(
                    {
                        "icon": "fa-wind",
                        "text": "Use air purifier at home",
                        "type": "Suggestion",
                    }
                )

            if predicted_aqi <= 100:
                recommendations.append(
                    {
                        "icon": "fa-person-walking",
                        "text": "Safe for light outdoor activity",
                        "type": "Suggestion",
                    }
                )

        # Optional limit
        recommendations = recommendations[:5]

    return render_template(
        "index.html",
        prediction=predicted_aqi,
        category_text=category_text,
        category_class=category_class,
        indicator_position=indicator_position,
        forecast=forecast_data,
        pollutants=pollutant_display,
        cig_day=cig_day,
        cig_week=cig_week,
        cig_month=cig_month,
        selected_period=period,
        today_date=datetime.today().strftime("%d %B %Y"),
        health=health,
        solutions=solutions,
        recommendations=recommendations,
        is_simulated=is_simulated,
    )


# ---------------------------------------------------
# PostgreSQL Connection
# ---------------------------------------------------

try:
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
    print("Database connected successfully")
except Exception as db_err:
    print("Database connection failed:", db_err)
    print("Running in database-less mode. DB operations will fail.")
    conn = None
    cursor = None


# ---------------------------------------------------
# Login
# ---------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    db_offline = (conn is None)

    if request.method == "POST":
        if db_offline:
            # Database is offline, log in as Demo User for demonstration!
            username_input = request.form.get("username", "Demo User")
            session["user_id"] = 9999
            session["username"] = username_input.split("@")[0] if "@" in username_input else username_input
            session["diseases"] = ["asthma"]
            session["age_group"] = "adult"
            return redirect(url_for("home"))

        email = request.form["username"]
        password = request.form["password"]

        cursor.execute(
            "SELECT id, username, email, password FROM users WHERE email=%s", (email,)
        )

        user = cursor.fetchone()

        if user:

            stored_password = user[3]

            if check_password_hash(stored_password, password):
                session.permanent = False

                session["user_id"] = user[0]
                session["username"] = user[1]

                cursor.execute(
                    "SELECT diseases, age_group FROM users WHERE email=%s", (email,)
                )
                extra = cursor.fetchone()

                if extra:
                    session["diseases"] = extra[0].split(",") if extra[0] else []
                    session["age_group"] = extra[1]

                return redirect(url_for("home"))

        return render_template("login.html", error="Invalid Email or Password", db_offline=db_offline)

    return render_template("login.html", db_offline=db_offline)


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


from datetime import timedelta

app.permanent_session_lifetime = timedelta(minutes=60)


# ---------------------------------------------------
# Send OTP
# ---------------------------------------------------
@app.route("/send_otp", methods=["POST"])
def send_otp():

    data = request.get_json()
    email = data["email"]

    # Check if email already exists in database
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user:
        return jsonify({"status": "exists"})  # Stop OTP if email exists

    # Generate OTP
    otp = random.randint(100000, 999999)

    session["otp"] = str(otp)
    session["email"] = email

    msg = Message(
        subject="Delhi AQI Forecasting Email Verification",
        sender=app.config["MAIL_USERNAME"],
        recipients=[email],
    )

    msg.body = f"Your OTP for Delhi AQI Forecasting registration is {otp}"

    mail.send(msg)

    return jsonify({"status": "sent"})


# ---------------------------------------------------
# Verify OTP
# ---------------------------------------------------
@app.route("/verify_otp", methods=["POST"])
def verify_otp():

    data = request.get_json()
    user_otp = data["otp"]

    if user_otp == session.get("otp"):

        session["verified"] = True
        return jsonify({"status": "success"})

    else:

        return jsonify({"status": "failed"})


# ---------------------------------------------------
# Forgot password
# ---------------------------------------------------


@app.route("/send_reset_otp", methods=["POST"])
def send_reset_otp():

    data = request.get_json()
    email = data["email"]

    # Check email exists
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"status": "not_found"})

    otp = random.randint(100000, 999999)

    session["reset_otp"] = str(otp)
    session["reset_email"] = email

    msg = Message(
        subject="Delhi AQI Forecasting Password Reset OTP",
        sender=app.config["MAIL_USERNAME"],
        recipients=[email],
    )

    msg.body = f"Your OTP for password reset is {otp}"

    mail.send(msg)

    return jsonify({"status": "sent"})


@app.route("/verify_reset_otp", methods=["POST"])
def verify_reset_otp():

    data = request.get_json()
    otp = data["otp"]

    if otp == session.get("reset_otp"):

        session["reset_verified"] = True

        return jsonify({"status": "success"})

    return jsonify({"status": "failed"})


@app.route("/reset_password", methods=["POST"])
def reset_password():

    if not session.get("reset_verified"):
        return "OTP verification required"

    password = request.form["password"]
    confirm = request.form["confirm_password"]

    if password != confirm:
        return "Passwords do not match"

    hashed = generate_password_hash(password)

    email = session.get("reset_email")

    cursor.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, email))

    conn.commit()

    session.clear()

    return redirect("/login")


@app.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")


# ---------------------------------------------------
# Register
# ---------------------------------------------------


@app.route("/register", methods=["GET", "POST"])
def register():
    db_offline = (conn is None)

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if password != confirm:
            return "Passwords do not match"

        diseases = request.form.getlist("diseases")
        age_group = request.form.get("age_group")

        # Handle "None"
        if "None" in diseases:
            diseases = []

        if db_offline:
            # Database is offline, log in as Demo User with custom config!
            session["user_id"] = 9999
            session["username"] = username
            session["diseases"] = diseases
            session["age_group"] = age_group
            return redirect(url_for("home"))

        if not session.get("verified"):
            return "Verify Email First"

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        existing = cursor.fetchone()

        if existing:
            return "Email already registered"

        hashed = generate_password_hash(password)
        diseases_str = ",".join(diseases) if diseases else ""

        cursor.execute(
            """
        INSERT INTO users(username,email,password,verified,diseases,age_group)
        VALUES(%s,%s,%s,TRUE,%s,%s)
        """,
            (username, email, hashed, diseases_str, age_group),
        )

        conn.commit()

        return redirect("/login")

    return render_template("register.html", db_offline=db_offline)


# ---------------------------------------------------
# User profile
# ---------------------------------------------------
@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    if conn is None:
        return render_template(
            "profile.html",
            username=session.get("username", "Demo User"),
            email="demo@example.com",
            age_group=session.get("age_group", "adult"),
            diseases=",".join(session.get("diseases", [])),
        )

    user_id = session["user_id"]

    cursor.execute(
        """
        SELECT username, email, age_group, diseases
        FROM users
        WHERE id=%s
    """,
        (user_id,),
    )

    user = cursor.fetchone()

    return render_template(
        "profile.html",
        username=user[0],
        email=user[1],
        age_group=user[2],
        diseases=user[3],
    )


@app.route("/update_profile", methods=["POST"])
def update_profile():

    if "user_id" not in session:
        return redirect("/login")

    age_group = request.form["age_group"]
    diseases = request.form.getlist("diseases")

    if conn is None:
        session["age_group"] = age_group
        session["diseases"] = diseases
        return redirect("/profile")

    user_id = session["user_id"]
    diseases_str = ",".join(diseases)

    cursor.execute(
        """
        UPDATE users
        SET age_group=%s, diseases=%s
        WHERE id=%s
    """,
        (age_group, diseases_str, user_id),
    )

    conn.commit()

    return redirect("/profile")


# ---------------------------------------------------
# Data bar graphs
# ---------------------------------------------------
@app.route("/aqi-data")
def get_aqi_data():
    mode = request.args.get("mode")
    date = request.args.get("date")

    if conn is None:
        import random
        data = []
        if mode == "day":
            for h in range(24):
                val = 145.0 + 25.0 * np.sin((h - 6) * np.pi / 12) + random.uniform(-6, 6)
                data.append([h, round(max(10, val), 2)])
        elif mode == "week":
            from datetime import timedelta
            for i in range(7):
                d = datetime.today() - timedelta(days=6-i)
                val = 150.0 + 15.0 * np.sin(i) + random.uniform(-10, 10)
                data.append([d.strftime("%Y-%m-%d"), round(max(10, val), 2)])
        return jsonify(data)

    cur = conn.cursor()

    if mode == "day":
        query = """
            SELECT 
                EXTRACT(HOUR FROM recorded_at)::int AS hour,
                AVG(predicted_aqi) AS avg_aqi
            FROM hourly_aqi_data
            WHERE recorded_at >= %s::date
            AND recorded_at < %s::date + INTERVAL '1 day'
            GROUP BY hour
            ORDER BY hour;
        """
        cur.execute(query, (date, date))
        rows = cur.fetchall()

        # RETURN ARRAY FORMAT (IMPORTANT)
        data = [[int(r[0]), float(r[1])] for r in rows]

    elif mode == "week":
        query = """
            SELECT 
                DATE(recorded_at),
                AVG(predicted_aqi)
            FROM hourly_aqi_data
            WHERE recorded_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY 1
            ORDER BY 1;
        """
        cur.execute(query)
        rows = cur.fetchall()

        # ARRAY FORMAT
        data = [[str(r[0]), float(r[1])] for r in rows]

    cur.close()
    return jsonify(data)


# ---------------------------------------------------
# Calender
# ---------------------------------------------------
@app.route("/aqi-calendar")
def aqi_calendar():
    year = request.args.get("year", 2026)

    if conn is None:
        from datetime import timedelta
        import random
        result = {}
        try:
            start_date = datetime(int(year), 1, 1)
        except ValueError:
            start_date = datetime(2026, 1, 1)
        for i in range(365):
            d = start_date + timedelta(days=i)
            month = d.month
            if month in [11, 12, 1, 2]:
                base_aqi = 280.0
            elif month in [7, 8, 9]:
                base_aqi = 85.0
            else:
                base_aqi = 155.0
            val = base_aqi + random.uniform(-35, 35)
            result[d.strftime("%Y-%m-%d")] = round(max(10, min(500, val)), 2)
        return jsonify(result)

    cur = conn.cursor()
    query = """
        SELECT DATE(recorded_at), AVG(predicted_aqi)
        FROM hourly_aqi_data
        WHERE EXTRACT(YEAR FROM recorded_at) = %s
        GROUP BY 1
        ORDER BY 1;
    """
    cur.execute(query, (year,))
    data = cur.fetchall()
    cur.close()

    # Convert to dictionary
    result = {str(row[0]): float(row[1]) for row in data}

    return jsonify(result)


# Start background scheduler
# In production, to prevent multiple worker processes from launching duplicate schedulers,
# you can disable it by setting DISABLE_SCHEDULER=True in your environment variables.
if os.environ.get("DISABLE_SCHEDULER", "False").lower() not in ("true", "1", "yes"):
    try:
        start_scheduler(app, model, cursor, mail, get_delhi_pollutants, get_health_advice)
    except Exception as scheduler_err:
        print("Failed to start scheduler:", scheduler_err)

if __name__ == "__main__":
    app.run(debug=True)
