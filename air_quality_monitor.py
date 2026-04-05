"""
Air Quality Monitor
-------------------
Fetches the latest PM2.5 measurements for a given city from the OpenAQ API,
calculates the US EPA Air Quality Index (AQI), and sends an email notification
when the air quality is "Unhealthy" or worse (AQI >= 101).

Required environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CITY            City name to monitor (default: "London")
AQI_THRESHOLD   AQI value above which a notification is sent (default: 100)
SMTP_SERVER     SMTP server hostname (e.g. smtp.gmail.com)
SMTP_PORT       SMTP server port (default: 587)
SMTP_USERNAME   Sender email address / SMTP login
SMTP_PASSWORD   SMTP password or app-specific password
NOTIFY_EMAIL    Recipient email address for notifications
"""

import os
import smtplib
import sys
from email.mime.text import MIMEText

import requests

# ---------------------------------------------------------------------------
# AQI calculation helpers (US EPA standard, PM2.5 parameter)
# ---------------------------------------------------------------------------

# (C_low, C_high, I_low, I_high)
_PM25_BREAKPOINTS = [
    (0.0, 12.0, 0, 50),
    (12.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
]

_AQI_CATEGORIES = [
    (0, 50, "Good"),
    (51, 100, "Moderate"),
    (101, 150, "Unhealthy for Sensitive Groups"),
    (151, 200, "Unhealthy"),
    (201, 300, "Very Unhealthy"),
    (301, 500, "Hazardous"),
]


def pm25_to_aqi(concentration: float) -> int:
    """Convert a PM2.5 concentration (μg/m³) to a US EPA AQI value.

    Uses the piecewise linear formula from the EPA technical document:
    AQI = (I_high - I_low) / (C_high - C_low) * (C - C_low) + I_low
    where C is the truncated concentration and (C_low, C_high, I_low, I_high)
    are the breakpoint pair that brackets C.
    """
    concentration = round(concentration, 1)
    for c_low, c_high, i_low, i_high in _PM25_BREAKPOINTS:
        if c_low <= concentration <= c_high:
            # EPA piecewise linear interpolation
            aqi = (i_high - i_low) / (c_high - c_low) * (concentration - c_low) + i_low
            return round(aqi)
    # Above highest breakpoint – clamp to 500
    return 500


def aqi_category(aqi: int) -> str:
    """Return the human-readable AQI category string."""
    for low, high, label in _AQI_CATEGORIES:
        if low <= aqi <= high:
            return label
    return "Hazardous"


# ---------------------------------------------------------------------------
# OpenAQ API helpers
# ---------------------------------------------------------------------------

OPENAQ_BASE = "https://api.openaq.io/v2"


def fetch_latest_pm25(city: str) -> tuple[float, str, str]:
    """
    Return (pm25_value, location_name, timestamp) for the most recent PM2.5
    reading in *city* from the OpenAQ v2 API.

    When multiple monitoring stations report data for the city, the station
    with the most recent ``lastUpdated`` timestamp is selected.  Ties are
    broken by iteration order (i.e. the first match is kept).

    Raises RuntimeError if no data is found.
    """
    url = f"{OPENAQ_BASE}/latest"
    params = {"city": city, "parameter": "pm25", "limit": 10}
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    results = data.get("results", [])
    if not results:
        raise RuntimeError(f"No PM2.5 data found for city: {city!r}")

    # Pick the result with the most recent measurement
    best = None
    best_ts = ""
    for result in results:
        for measurement in result.get("measurements", []):
            if measurement.get("parameter") == "pm25":
                ts = measurement.get("lastUpdated", "")
                if best is None or ts > best_ts:
                    best = (measurement["value"], result["location"], ts)
                    best_ts = ts

    if best is None:
        raise RuntimeError(f"No PM2.5 measurements found for city: {city!r}")

    return best


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------


def send_email_notification(
    smtp_server: str,
    smtp_port: int,
    username: str,
    password: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """Send a plain-text email via SMTP with STARTTLS."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = recipient

    with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(username, [recipient], msg.as_string())


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def main() -> int:
    city = os.environ.get("CITY", "London")
    aqi_threshold = int(os.environ.get("AQI_THRESHOLD", "100"))

    print(f"Checking air quality for: {city}")

    # Fetch data
    try:
        pm25_value, location, timestamp = fetch_latest_pm25(city)
    except (RuntimeError, requests.RequestException) as exc:
        print(f"ERROR: Could not fetch air quality data — {exc}", file=sys.stderr)
        return 1

    aqi = pm25_to_aqi(pm25_value)
    category = aqi_category(aqi)

    print(f"Location  : {location}")
    print(f"Timestamp : {timestamp}")
    print(f"PM2.5     : {pm25_value} μg/m³")
    print(f"AQI       : {aqi} ({category})")

    if aqi <= aqi_threshold:
        print("Air quality is acceptable. No notification sent.")
        return 0

    # Air quality is bad — notify
    print(f"AQI {aqi} exceeds threshold {aqi_threshold}. Sending notification…")

    smtp_server = os.environ.get("SMTP_SERVER", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    notify_email = os.environ.get("NOTIFY_EMAIL", "")

    if not all([smtp_server, smtp_username, smtp_password, notify_email]):
        print(
            "WARNING: SMTP credentials not fully configured — skipping email.\n"
            "Set SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, and NOTIFY_EMAIL "
            "to enable email notifications.",
            file=sys.stderr,
        )
        return 0

    subject = f"⚠️ Air Quality Alert: {category} in {city} (AQI {aqi})"
    body = (
        f"Air Quality Alert\n"
        f"=================\n\n"
        f"City      : {city}\n"
        f"Location  : {location}\n"
        f"Timestamp : {timestamp}\n\n"
        f"PM2.5     : {pm25_value} μg/m³\n"
        f"AQI       : {aqi}\n"
        f"Category  : {category}\n\n"
        f"The air quality index has exceeded your alert threshold of {aqi_threshold}.\n"
        f"Please take appropriate precautions.\n"
    )

    try:
        send_email_notification(
            smtp_server, smtp_port, smtp_username, smtp_password, notify_email, subject, body
        )
        print(f"Notification sent to {notify_email}.")
    except smtplib.SMTPException as exc:
        print(f"ERROR: Failed to send notification — {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
