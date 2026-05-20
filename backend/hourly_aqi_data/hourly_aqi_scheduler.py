import schedule
import time
import subprocess
from datetime import datetime


def run_aqi_script():
    print(f"[{datetime.now()}] Running AQI script...")
    try:
        subprocess.run(["python", "store_hourly_aqi.py"], check=True)
        print(f"[{datetime.now()}] AQI data stored successfully\n")
    except subprocess.CalledProcessError as e:
        print(f"[{datetime.now()}] Error running script: {e}\n")


# Run once immediately (optional but recommended)
run_aqi_script()

# Schedule to run every hour at minute 00
schedule.every().hour.at(":00").do(run_aqi_script)

print("Hourly AQI scheduler started...")

while True:
    schedule.run_pending()
    time.sleep(5)  # check every 5 seconds
