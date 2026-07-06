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

Jobs are stored in `jobscout.sqlite3`. Collection skips jobs whose posting date is older than `collection.lookback_days` (default 30) in `config.yaml`; jobs without a posting date are always kept. The mock collector (10 fake jobs for testing) is disabled by default.

## Run Scheduler

```bash
python run_scheduler.py
```

The scheduler keeps running until stopped with Ctrl+C. It runs collection and scoring daily at the times set in `config.yaml` (`schedule.collection_time` / `schedule.scoring_time`, defaults 08:00 and 08:30), logging each run to `logs/scheduler.log`. Restart the scheduler after changing the times.

## Scoring

AI scoring with Claude is controlled by `scoring.ai_enabled` in `config.yaml` (default `false`). When disabled, `python run_scoring.py` is a no-op. When enabled, it requires the `ANTHROPIC_API_KEY` environment variable and scores only jobs that have no score yet; jobs whose scoring fails stay unscored and are retried on the next run.

You can also score jobs manually in the dashboard: open the "Manual score" section on a job card, pick a 1-10 score and an optional note. Manually scored jobs are never overwritten by AI scoring. All of the settings above (schedule times, AI toggle, lookback window, stale-job days) can be edited on the dashboard's Settings page, which also shows which environment variables are missing.

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

## Cleanup Jobs

```bash
python run_cleanup.py
```

This prints a duplicate and stale-job report, asks for confirmation, deletes duplicate jobs, and archives stale unreviewed jobs as ignored.

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
