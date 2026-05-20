from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import numpy as np
from flask_mail import Message


def start_scheduler(app, model, cursor, mail, get_delhi_pollutants, get_health_advice):

    def send_daily_aqi_emails():

        with app.app_context():

            print("Running AQI Email Scheduler...")

            pollutants = get_delhi_pollutants()

            if not pollutants or not model or not cursor:
                print("Model, database cursor or pollutant data missing")
                return

            today = datetime.today()

            # -------------------------
            # AQI Prediction
            # -------------------------
            try:
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

            except Exception as e:
                print("AQI Prediction Error:", e)
                return

            # -------------------------
            # Fetch ALL users
            # -------------------------
            cursor.execute("""
                SELECT username, email, diseases, age_group
                FROM users
            """)
            users = cursor.fetchall()

            print(f"Total users found: {len(users)}")

            if not users:
                print("No users in database")
                return

            # -------------------------
            # Send Email to Each User
            # -------------------------
            for user in users:

                username = user[0]
                email = user[1]
                diseases = user[2].split(",") if user[2] else []
                age_group = user[3]

                combined = diseases.copy()
                if age_group:
                    combined.append(age_group)

                health = get_health_advice(predicted_aqi, combined)

                # -------------------------
                # PROFESSIONAL EMAIL TEXT
                # -------------------------
                subject = "Delhi AQI Daily Health Advisory"

                body = f"""
Dear {username},

Here is your personalized Air Quality update for Delhi for today:

AQI Level   : {predicted_aqi}
Category    : {health['category']}
Risk Level  : {health['risk_level']}


Health Advisory:
{health['message']}

Recommended Actions:
"""

                # Required actions
                for action in health["required_actions"]:
                    body += f"\n✔ {action}"

                # Optional actions
                if health["optional_actions"]:
                    body += "\n\nAdditional Suggestions:"
                    for action in health["optional_actions"]:
                        body += f"\n• {action}"

                body += f"""

Important Note:
This advisory is tailored based on your age group and existing health conditions.

Air pollution can significantly impact your health. Please follow the above
recommendations to stay safe and reduce exposure.


Stay informed. Stay protected.

Warm regards,  
Delhi AQI Monitoring System  
Protecting Your Health, Every Day
"""

                try:
                    msg = Message(
                        subject=subject,
                        sender=app.config["MAIL_USERNAME"],
                        recipients=[email],
                    )

                    msg.body = body
                    mail.send(msg)

                    print(f"Email sent to {email}")

                except Exception as e:
                    print(f"Error sending to {email}: {e}")

    # -------------------------
    # Scheduler Setup
    # -------------------------
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # TEST MODE (runs every 1 minute)
    # scheduler.add_job(
    #     func=send_daily_aqi_emails,
    #     trigger="interval",
    #     minutes=1
    # )

    # PRODUCTION MODE (10:00 AM daily)
    #
    scheduler.add_job(func=send_daily_aqi_emails, trigger="cron", hour=10, minute=0)

    scheduler.start()

    print("Scheduler Started...")
