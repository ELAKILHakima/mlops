# mlops

## Air Quality Monitor

Automatically checks the air quality for a city every hour and sends you an
email notification when the US EPA Air Quality Index (AQI) exceeds a
configurable threshold.

### How it works

1. `air_quality_monitor.py` queries the [OpenAQ v2 API](https://docs.openaq.org/)
   for the latest PM2.5 reading in the configured city.
2. It converts the PM2.5 concentration to an AQI value using the US EPA formula.
3. If the AQI exceeds the threshold (default **100 – Moderate/Unhealthy
   boundary**), an email alert is sent via SMTP.
4. The `.github/workflows/air_quality_monitor.yml` workflow runs the script
   on a schedule (every hour) and supports manual triggers.

### Setup

#### 1. Configure the city and threshold (repository variables)

Go to **Settings → Secrets and variables → Actions → Variables** and add:

| Variable | Description | Default |
|---|---|---|
| `CITY` | City name to monitor | `London` |
| `AQI_THRESHOLD` | AQI value that triggers a notification | `100` |

#### 2. Configure email notifications (repository secrets)

Go to **Settings → Secrets and variables → Actions → Secrets** and add:

| Secret | Description |
|---|---|
| `SMTP_SERVER` | SMTP hostname, e.g. `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port, e.g. `587` |
| `SMTP_USERNAME` | Sender email address / SMTP login |
| `SMTP_PASSWORD` | SMTP password or app-specific password |
| `NOTIFY_EMAIL` | Recipient email address |

> **Gmail users:** Enable 2-Step Verification and create an
> [App Password](https://support.google.com/accounts/answer/185833) to use as
> `SMTP_PASSWORD`.

#### 3. Run manually

Trigger the workflow at any time from **Actions → Air Quality Monitor →
Run workflow**, optionally specifying a different city.

### AQI categories

| AQI | Category |
|---|---|
| 0 – 50 | Good |
| 51 – 100 | Moderate |
| 101 – 150 | Unhealthy for Sensitive Groups |
| 151 – 200 | Unhealthy |
| 201 – 300 | Very Unhealthy |
| 301 – 500 | Hazardous |
