-- Create hourly AQI data table
CREATE TABLE IF NOT EXISTS hourly_aqi_data (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pm2_5 FLOAT,
    pm10 FLOAT,
    no FLOAT,
    no2 FLOAT,
    nox FLOAT,
    nh3 FLOAT,
    co FLOAT,
    so2 FLOAT,
    o3 FLOAT,
    benzene FLOAT,
    toluene FLOAT,
    pm_ratio FLOAT,
    nox_total FLOAT,
    year INT,
    month INT,
    day INT,
    day_of_week INT,
    week_of_year INT,
    predicted_aqi FLOAT
);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password TEXT NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    diseases TEXT,
    age_group TEXT
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_email ON users(email);