# JobScout

JobScout is a small personal job-search dashboard. It collects jobs from configurable sources, deduplicates them, stores them in SQLite, and displays them in Streamlit.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

BMW scraping uses Playwright because BMW's careers listings are rendered dynamically. The Chromium install command only needs to be run once per environment.

## Run Collection

```bash
python run_collection.py
```

The default `config.yaml` enables the mock collector, which returns 10 fake AI/LLM-related jobs. Jobs are stored in `jobscout.sqlite3`.

## Run Scheduler

```bash
python run_scheduler.py
```

The scheduler keeps running until stopped with Ctrl+C. It runs collection every day at 8:00 AM and scoring every day at 8:30 AM, logging each run to `logs/scheduler.log`.

## Email Notifications

Scheduled scoring sends a daily summary email after the scoring run completes. The email includes the number of new jobs collected, the number of jobs scored, and the top 5 highest scoring jobs.

Set these environment variables before starting the scheduler:

```bash
JOBSCOUT_EMAIL_FROM=your-email@gmail.com
JOBSCOUT_EMAIL_TO=recipient@example.com
JOBSCOUT_EMAIL_PASSWORD=your-gmail-app-password
```

Gmail SMTP is used by default through `smtp.gmail.com:587`. For Gmail accounts, use an app password rather than your normal account password. If any email variable is missing, JobScout skips sending the email and writes a warning to `logs/scheduler.log`.

## Export HTML Dashboard

```bash
python run_export.py
```

This writes a standalone HTML export to `exports/jobs_export.html` that can be opened directly in any browser without running Streamlit.

## Start Streamlit

```bash
streamlit run ui/app.py
```

The dashboard shows jobs newest first and supports filters for source, status, company, and keyword. Use the buttons on each job to mark it as relevant, ignored, or applied.

## Personal Connections

Private referral notes live in `personal_connections.json`. This file is ignored by git, so it stays local and should not be uploaded to GitHub.

Use `personal_connections.example.json` as the schema. Add companies, aliases, and connection names there; matching job cards will show a "Personal connections" note in the dashboard.

## Configuration

Collectors are controlled in `config.yaml`:

```yaml
database:
  path: jobscout.sqlite3

collectors:
  mock:
    enabled: true
```

## Adding Real Collectors

Add a new collector under `collectors/` that returns a list of `Job` objects from `collectors.base`. For simple pages, start with `requests` and `BeautifulSoup`. Add the collector to `AVAILABLE_COLLECTORS` in `run_collection.py`, then enable it in `config.yaml`.

Use Playwright later only for sites that require browser rendering.
