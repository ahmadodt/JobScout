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


st.set_page_config(page_title="JobScout", layout="wide")


@st.cache_resource
def get_store() -> JobStore:
    connection = connect()
    init_db(connection)
    return JobStore(connection)


@st.cache_data
def get_personal_connections(last_modified: float | None) -> dict:
    return load_personal_connections()


def get_connections_file_mtime() -> float | None:
    if not DEFAULT_CONNECTIONS_PATH.exists():
        return None
    return DEFAULT_CONNECTIONS_PATH.stat().st_mtime


store = get_store()
personal_connections = get_personal_connections(get_connections_file_mtime())
filter_values = store.get_filter_values()

st.title("JobScout")

with st.sidebar:
    st.header("Filters")
    source = st.selectbox("Source", ["All", *filter_values["source"]])
    status = st.selectbox("Status", ["All", *filter_values["status"]])
    company = st.selectbox("Company", ["All", *filter_values["company"]])
    keyword = st.text_input("Keyword")

jobs = store.list_jobs(
    source=None if source == "All" else source,
    status=None if status == "All" else status,
    company=None if company == "All" else company,
    keyword=keyword.strip() or None,
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
            st.write(f"{job['company']} · {job['location']} · {job['source']}")
        with status_col:
            st.write(f"Status: `{job['status']}`")

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
