from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.db import connect, init_db
from services.config import load_config, resolve_db_path, save_config
from services.job_store import JobStore
from services.notifier import REQUIRED_ENV_VARS
from services.personal_connections import (
    DEFAULT_CONNECTIONS_PATH,
    PersonalConnectionsError,
    find_company_connections,
    load_personal_connections,
)
from services.watchlist import CompanyWatchlist


st.set_page_config(page_title="JobScout", layout="wide")

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@st.cache_resource
def get_connection(db_path: str):
    connection = connect(db_path)
    init_db(connection)
    return connection


@st.cache_data
def get_personal_connections(last_modified: float | None) -> tuple[dict, str | None]:
    try:
        return load_personal_connections(), None
    except PersonalConnectionsError as exc:
        return {}, str(exc)


def get_connections_file_mtime() -> float | None:
    if not DEFAULT_CONNECTIONS_PATH.exists():
        return None
    return DEFAULT_CONNECTIONS_PATH.stat().st_mtime


def render_jobs_view(store: JobStore, personal_connections: dict) -> None:
    filter_values = store.get_filter_values()

    with st.sidebar:
        st.header("Filters")
        source = st.selectbox("Source", ["All", *filter_values["source"]])
        status = st.selectbox("Status", ["All", *filter_values["status"]])
        company = st.selectbox("Company", ["All", *filter_values["company"]])
        keyword = st.text_input("Keyword")
        sort_label = st.selectbox("Sort by", ["Newest first", "Score"])
        min_score = st.slider("Minimum score", 1, 10, 1)

    jobs = store.list_jobs(
        source=None if source == "All" else source,
        status=None if status == "All" else status,
        company=None if company == "All" else company,
        keyword=keyword.strip() or None,
        sort_by="score" if sort_label == "Score" else "newest",
        min_score=min_score,
    )

    st.caption(f"{len(jobs)} jobs")

    if not jobs:
        st.info("No jobs found. Run `python run_collection.py` to collect mock jobs.")

    for job in jobs:
        with st.container(border=True):
            header, status_col = st.columns([4, 1])
            with header:
                st.subheader(job["title"])
                company_connections = find_company_connections(
                    job["company"], personal_connections
                )
                if company_connections:
                    if company_connections.connections:
                        connection_labels = []
                        for connection in company_connections.connections:
                            details = " - ".join(
                                detail
                                for detail in (
                                    connection.relationship,
                                    connection.notes,
                                )
                                if detail
                            )
                            label = connection.name
                            if details:
                                label = f"{label} ({details})"
                            connection_labels.append(label)
                        connection_text = ", ".join(connection_labels)
                        if company_connections.notes:
                            connection_text = (
                                f"{connection_text} | {company_connections.notes}"
                            )
                        st.info(f"Personal connections: {connection_text}")
                    elif company_connections.notes:
                        st.info(f"Personal connections: {company_connections.notes}")
                    else:
                        st.info(
                            "Personal connections: company is on your local list; "
                            "add contact names in `personal_connections.json`."
                        )
                st.write(f"{job['company']} - {job['location']} - {job['source']}")
            with status_col:
                st.write(f"Status: `{job['status']}`")
                if job["score"] is not None:
                    source_label = "manual" if job["score_source"] == "manual" else "AI"
                    st.write(f"Score: {job['score']}/10 ({source_label})")
                    if job["score_reason"]:
                        st.caption(job["score_reason"])

            st.write(job["description"])
            st.markdown(f"[Open job posting]({job['url']})")
            st.caption(
                f"Posted: {job['date_posted'] or 'Unknown'} | "
                f"Collected: {job['date_collected']}"
            )

            relevant, ignored, applied = st.columns(3)
            if relevant.button("Mark relevant", key=f"relevant-{job['id']}"):
                store.update_status(job["id"], "relevant")
                st.rerun()
            if ignored.button("Ignore", key=f"ignored-{job['id']}"):
                store.update_status(job["id"], "ignored")
                st.rerun()
            if applied.button("Mark applied", key=f"applied-{job['id']}"):
                store.update_status(job["id"], "applied")
                st.rerun()

            with st.expander("Manual score"):
                is_manual = job["score_source"] == "manual"
                default_score = job["score"] if is_manual and job["score"] else 5
                default_note = job["score_reason"] if is_manual else ""
                score_col, note_col = st.columns([1, 3])
                manual_score = score_col.number_input(
                    "Score (1-10)",
                    min_value=1,
                    max_value=10,
                    value=default_score,
                    key=f"manual-score-{job['id']}",
                )
                manual_note = note_col.text_input(
                    "Note (optional)",
                    value=default_note or "",
                    key=f"manual-note-{job['id']}",
                )
                if st.button("Save manual score", key=f"manual-save-{job['id']}"):
                    store.update_score(
                        job["id"],
                        int(manual_score),
                        manual_note.strip(),
                        source="manual",
                    )
                    st.rerun()


def render_watchlist_view(watchlist: CompanyWatchlist) -> None:
    st.subheader("Company Watchlist")

    with st.form("add-company-form", clear_on_submit=True):
        name = st.text_input("Company name")
        careers_url = st.text_input("Careers URL")
        submitted = st.form_submit_button("Add company")

    if submitted:
        try:
            watchlist.add_company(name, careers_url)
            st.success(f"Added {name.strip()} to the watchlist.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    companies = watchlist.list_companies()
    rows = []
    for company in companies:
        stats = watchlist.get_company_stats(company["name"])
        rows.append(
            {
                "Company": company["name"],
                "Careers URL": company["careers_url"] or "",
                "Total jobs found": stats["total_jobs"],
                "Latest job date": stats["latest_job_date"] or "",
                "Top score": stats["top_score"] if stats["top_score"] is not None else "",
            }
        )

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No companies on the watchlist yet.")

    for company in companies:
        columns = st.columns([4, 1])
        with columns[0]:
            st.write(company["name"])
        with columns[1]:
            if st.button("Remove", key=f"remove-watchlist-{company['id']}"):
                watchlist.remove_company(company["name"])
                st.rerun()


def render_settings_view(config: dict, store: JobStore) -> None:
    st.subheader("Settings")
    st.info(
        "Schedule and lookback changes take effect after restarting "
        "`python run_scheduler.py`."
    )

    with st.form("settings-form"):
        collection_time = st.text_input(
            "Daily collection time (HH:MM, 24h)",
            value=config["schedule"]["collection_time"],
        )
        scoring_time = st.text_input(
            "Daily scoring time (HH:MM, 24h)",
            value=config["schedule"]["scoring_time"],
        )
        ai_enabled = st.toggle(
            "Enable AI scoring (Claude)",
            value=bool(config["scoring"]["ai_enabled"]),
            help="When off, the scoring run does nothing and only manual scores are used.",
        )
        lookback_days = st.number_input(
            "Scrape lookback window (days)",
            min_value=1,
            max_value=365,
            value=int(config["collection"]["lookback_days"]),
            help="Collection skips jobs whose posting date is older than this. "
            "Jobs without a posting date are always kept.",
        )
        stale_days = st.number_input(
            "Archive unreviewed jobs after (days)",
            min_value=1,
            max_value=365,
            value=int(config["cleanup"]["stale_days"]),
        )
        submitted = st.form_submit_button("Save settings")

    if submitted:
        errors = []
        if not TIME_PATTERN.match(collection_time.strip()):
            errors.append("Collection time must be HH:MM (24h), e.g. 08:00")
        if not TIME_PATTERN.match(scoring_time.strip()):
            errors.append("Scoring time must be HH:MM (24h), e.g. 08:30")

        if errors:
            for error in errors:
                st.error(error)
        else:
            config["schedule"]["collection_time"] = collection_time.strip()
            config["schedule"]["scoring_time"] = scoring_time.strip()
            config["scoring"]["ai_enabled"] = bool(ai_enabled)
            config["collection"]["lookback_days"] = int(lookback_days)
            config["cleanup"]["stale_days"] = int(stale_days)
            save_config(config)
            st.success("Settings saved to config.yaml")

    st.divider()
    st.subheader("Environment status")

    if config["scoring"]["ai_enabled"]:
        if os.getenv("ANTHROPIC_API_KEY"):
            st.success("AI scoring: ANTHROPIC_API_KEY is set.")
        else:
            st.error(
                "AI scoring is enabled but ANTHROPIC_API_KEY is not set - "
                "scoring runs will fail until you set it."
            )
    else:
        st.caption("AI scoring is disabled; ANTHROPIC_API_KEY is not required.")

    missing_email_vars = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing_email_vars:
        st.warning(
            "Daily email summaries are disabled - missing environment variables: "
            + ", ".join(missing_email_vars)
        )
    else:
        st.success("Email notifications: all environment variables are set.")

    db_path = resolve_db_path(config)
    total_jobs = store.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    st.caption(f"Database: `{db_path}` - {total_jobs} jobs stored")


config = load_config()
connection = get_connection(str(resolve_db_path(config)))
store = JobStore(connection)
watchlist = CompanyWatchlist(connection)
personal_connections, connections_error = get_personal_connections(
    get_connections_file_mtime()
)

st.title("JobScout")

with st.sidebar:
    view = st.radio("View", ["Jobs", "Watchlist", "Settings"])
    if connections_error:
        st.warning(
            "personal_connections.json could not be read and was ignored: "
            f"{connections_error}"
        )

if view == "Jobs":
    render_jobs_view(store, personal_connections)
elif view == "Watchlist":
    render_watchlist_view(watchlist)
else:
    render_settings_view(config, store)
