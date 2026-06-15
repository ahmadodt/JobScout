from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.db import connect, init_db
from services.job_store import JobStore


st.set_page_config(page_title="JobScout", layout="wide")


@st.cache_resource
def get_store() -> JobStore:
    connection = connect()
    init_db(connection)
    return JobStore(connection)


store = get_store()
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
