from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT_DIR / "exports"
EXPORT_PATH = EXPORT_DIR / "jobs_export.html"


def export_jobs_html(connection: sqlite3.Connection, output_path: Path | None = None) -> tuple[int, Path]:
    path = output_path or EXPORT_PATH
    path.parent.mkdir(exist_ok=True)

    jobs = list(
        connection.execute(
            """
            SELECT title, company, location, date_posted, score, score_reason, url
            FROM jobs
            ORDER BY
                CASE WHEN score IS NULL THEN 1 ELSE 0 END,
                score DESC,
                COALESCE(date_posted, '') DESC,
                id DESC
            """
        ).fetchall()
    )

    path.write_text(_render_html(jobs), encoding="utf-8")
    return len(jobs), path


def _render_html(jobs: list[sqlite3.Row]) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards = "\n".join(_render_job_card(job) for job in jobs)
    if not cards:
        cards = '<p class="empty">No jobs found.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JobScout Export</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #101214;
      --panel: #171a1f;
      --panel-soft: #1d2229;
      --border: #2d3440;
      --text: #eef2f6;
      --muted: #a7b0bd;
      --accent: #73d2de;
      --score: #b9f18c;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}

    main {{
      width: min(1080px, calc(100% - 32px));
      margin: 0 auto;
      padding: 40px 0 56px;
    }}

    header {{
      margin-bottom: 28px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
    }}

    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      font-weight: 700;
      letter-spacing: 0;
    }}

    .summary {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .grid {{ display: grid; gap: 16px; }}

    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 10px;
    }}

    h2 {{
      margin: 0;
      font-size: 20px;
      font-weight: 650;
      letter-spacing: 0;
    }}

    .meta {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .score {{
      flex: 0 0 auto;
      color: var(--score);
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 14px;
      font-weight: 700;
      white-space: nowrap;
    }}

    .reason {{
      margin: 12px 0;
      color: var(--text);
      background: var(--panel-soft);
      border-left: 3px solid var(--accent);
      padding: 10px 12px;
      border-radius: 4px;
    }}

    a {{ color: var(--accent); text-decoration: none; font-weight: 650; }}
    a:hover {{ text-decoration: underline; }}

    .empty {{
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
      background: var(--panel);
    }}

    @media (max-width: 640px) {{
      main {{ width: min(100% - 24px, 1080px); padding-top: 28px; }}
      .card-header {{ display: block; }}
      .score {{ display: inline-block; margin-top: 10px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>JobScout Export</h1>
      <p class="summary">{len(jobs)} jobs exported on {html.escape(generated_at)}</p>
    </header>
    <section class="grid">
      {cards}
    </section>
  </main>
</body>
</html>
"""


def _render_job_card(job: sqlite3.Row) -> str:
    title = _escape(job["title"])
    company = _escape(job["company"])
    location = _escape(job["location"])
    date_posted = _escape(job["date_posted"] or "Unknown date")
    url = _escape(job["url"])
    score = job["score"]
    score_html = f'<div class="score">Score: {score}/10</div>' if score is not None else ""
    reason = job["score_reason"]
    reason_html = f'<p class="reason">{_escape(reason)}</p>' if reason else ""

    return f"""<article class="card">
  <div class="card-header">
    <div>
      <h2>{title}</h2>
      <p class="meta">{company} | {location} | Posted: {date_posted}</p>
    </div>
    {score_html}
  </div>
  {reason_html}
  <a href="{url}" target="_blank" rel="noopener noreferrer">Open job posting</a>
</article>"""


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)
