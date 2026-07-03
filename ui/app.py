from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.db import connect, init_db
from services.job_store import JobStore
from services.personal_connections import (
    DEFAULT_CONNECTIONS_PATH,
    find_company_connections,
    load_personal_connections,
)
from services.watchlist import CompanyWatchlist


st.set_page_config(page_title="JobScout", layout="wide")


@st.cache_resource
def get_connection():
    connection = connect()
    init_db(connection)
    return connection


@st.cache_data
def get_personal_connections(last_modified: float | None) -> dict:
    return load_personal_connections()


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
                    st.write(f"Score: {job['score']}/10")
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


connection = get_connection()
store = JobStore(connection)
watchlist = CompanyWatchlist(connection)
personal_connections = get_personal_connections(get_connections_file_mtime())

st.title("JobScout")

with st.sidebar:
    view = st.radio("View", ["Jobs", "Watchlist"])

if view == "Jobs":
    render_jobs_view(store, personal_connections)
else:
    render_watchlist_view(watchlist)
