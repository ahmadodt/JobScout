# JobScout

JobScout is a small personal job-search dashboard. It collects jobs from configurable sources, deduplicates them, stores them in SQLite, and displays them in Streamlit.

This first version intentionally keeps the scope small: no LLM scoring, embeddings, login handling, or scheduling.

## Setup

```bash
pip install -r requirements.txt
```

## Run Collection

```bash
python run_collection.py
```

The default `config.yaml` enables the mock collector, which returns 10 fake AI/LLM-related jobs. Jobs are stored in `jobscout.sqlite3`.

## Start Streamlit

```bash
streamlit run ui/app.py
```

The dashboard shows jobs newest first and supports filters for source, status, company, and keyword. Use the buttons on each job to mark it as relevant, ignored, or applied.

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
