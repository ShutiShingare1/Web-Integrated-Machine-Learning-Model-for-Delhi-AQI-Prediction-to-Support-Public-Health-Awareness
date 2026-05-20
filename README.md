# Delhi AQI Forecasting Web Application

A Flask-based web application that predicts and displays the Air Quality Index (AQI) of Delhi, provides customized health advisories based on user profiles (age group, diseases like asthma, etc.), and sends daily alert emails to registered users using a background scheduler.

---

## Features

- **Real-time Pollutant Data**: Fetches hourly pollutant concentrations (`PM2.5`, `PM10`, `NO2`, `CO`, `SO2`, `O3`) from OpenWeather air pollution API.
- **ML Prediction**: Predicts AQI using a pre-trained machine learning model (`best_aqi_model.pkl`).
- **Health Advisories**: Generates tailored advice for users based on age group and existing health conditions.
- **Scheduled Email Alerts**: Sends daily emails at 10:00 AM with customized advisories using `APScheduler`.
- **Bar Charts & Calendars**: Displays historical forecasts and trends visually in the browser.

---

## Project Structure

```text
Delhi_AQI/
│
├── app.py                     # Main Flask web application entrypoint
├── Procfile                   # Process configuration for production (Render/Heroku)
├── requirements.txt           # Python application dependencies
├── .gitignore                 # Files excluded from git version control
│
├── backend/
│   ├── scheduler.py           # Background email scheduler script
│   ├── data/                  # CSV datasets (raw and processed data)
│   ├── hourly_aqi_data/
│   │   ├── store_hourly_aqi.py       # Script that fetches data and stores in DB
│   │   ├── hourly_aqi_scheduler.py   # Scheduler to run store_hourly_aqi.py hourly
│   │   └── hourly_aqi_data.sql       # PostgreSQL database schema
│   └── model/
│       └── best_aqi_model.pkl        # Pre-trained ML model (41.7 MB)
│
└── frontend/
    ├── templates/             # HTML templates (index, login, register, etc.)
    └── static/                # CSS, Javascript, and Image assets
```

---

## Environment Variables

To keep credentials secure in production, the application reads the following variables from the environment. They fall back to local development defaults if not set.

| Variable | Description | Example / Local Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL Connection URI | `postgresql://postgres:shweta27@localhost:5432/aqi_database` |
| `SECRET_KEY` | Flask Session Secret Key | `d2233757fccb64801cd4b00...` |
| `MAIL_SERVER` | SMTP Server Host | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP Server Port | `587` |
| `MAIL_USE_TLS` | Enable TLS | `True` |
| `MAIL_USERNAME` | Email Address for Alerts | `shwetagurram9@gmail.com` |
| `MAIL_PASSWORD` | App Password for Email | `ylsq azsa wboh izhu` |
| `DISABLE_SCHEDULER`| Set `True` to disable background scheduler | `False` |

---

## Setup & Local Development

### 1. Prerequisites
- **Python**: version 3.8 to 3.12 is recommended.
- **PostgreSQL**: Local running database service.

### 2. Database Initialization
Ensure you have a PostgreSQL database named `aqi_database` created, then run the SQL statements inside `backend/hourly_aqi_data/hourly_aqi_data.sql` to initialize the `hourly_aqi_data` and `users` tables.

### 3. Installation
Clone the repository and install all dependencies:
```bash
# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (CMD / PowerShell):
venv\Scripts\activate
# On Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Running the Web Application
```bash
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

### 5. Running the Hourly Data Aggregation Scheduler
To continuously query OpenWeather API and store predictions to database in local development:
```bash
python backend/hourly_aqi_data/hourly_aqi_scheduler.py
```

---

## Production Deployment

### 1. Render / Heroku
This project is pre-configured with a `Procfile` and environment variable overrides for easy deployment to cloud platforms like **Render** or **Heroku**:

1. Create a new **Web Service** pointing to your Git repository.
2. Select **Python** runtime environment.
3. Configure the environment variables in settings according to the table above.
4. Set the **Build Command** to:
   ```bash
   pip install -r requirements.txt
   ```
5. Set the **Start Command** to:
   ```bash
   gunicorn app:app
   ```

### 2. Note on Background Workers
By default, the web application runs the background email scheduler thread. If you scale to multiple web instances (workers > 1), multiple threads might start. Set `DISABLE_SCHEDULER=True` on your web processes if you want to isolate the scheduler thread or run it as a separate background task.
