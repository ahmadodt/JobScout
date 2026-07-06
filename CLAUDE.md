# JobScout

JobScout collects job postings from company career pages, stores them in SQLite
(`jobscout.sqlite3`), scores them (AI via Claude or manually in the dashboard),
and shows them in a Streamlit UI (`ui/app.py`).

Configuration lives in `config.yaml`, loaded through `services/config.py`
(`load_config()` merges the file over `DEFAULTS`; `save_config()` writes it back).
Entry points: `run_collection.py`, `run_scoring.py`, `run_scheduler.py`,
`run_cleanup.py`.

## Commit Format

Prefix every commit subject with one of:

```
feat:     new feature or behavior
refactor: same behavior, cleaner structure
fix:      bug fix
test:     adding or updating tests
docs:     changes to documentation
```

Keep each commit focused on a single logical change.
