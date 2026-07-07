from __future__ import annotations

from database.db import _ensure_dedupe_key_includes_location
from services.deduplicator import make_dedupe_key, normalize_text


def test_normalize_text():
    assert normalize_text("  Senior LLM-Engineer (m/w/d)! ") == "senior llm engineer m w d"


def test_dedupe_key_includes_location():
    key = make_dedupe_key("SAP", "AI Engineer", "Berlin, DE")
    assert key == "sap::ai engineer::berlin de"
    assert make_dedupe_key("SAP", "AI Engineer", "Munich") != key


def test_dedupe_key_without_location_still_works():
    assert make_dedupe_key("SAP", "AI Engineer") == "sap::ai engineer::"


def _insert_legacy(connection, company, title, location, key):
    connection.execute(
        """
        INSERT INTO jobs (title, company, location, source, url, description,
                          date_collected, dedupe_key)
        VALUES (?, ?, ?, 'test', 'https://x.example/1', '', '2026-01-01T00:00:00Z', ?)
        """,
        (title, company, location, key),
    )


def test_migration_rekeys_legacy_rows(db_connection):
    _insert_legacy(db_connection, "SAP", "AI Engineer", "Berlin", "sap::ai engineer")

    _ensure_dedupe_key_includes_location(db_connection)
    db_connection.commit()

    row = db_connection.execute("SELECT dedupe_key FROM jobs").fetchone()
    assert row["dedupe_key"] == "sap::ai engineer::berlin"


def test_migration_drops_true_duplicates(db_connection):
    # Legacy key and an already-migrated row that collide under the new scheme.
    _insert_legacy(db_connection, "SAP", "AI Engineer", "Berlin", "sap::ai engineer::berlin")
    _insert_legacy(db_connection, "SAP", "AI Engineer", "Berlin", "sap::ai engineer")

    _ensure_dedupe_key_includes_location(db_connection)
    db_connection.commit()

    rows = db_connection.execute("SELECT id, dedupe_key FROM jobs ORDER BY id").fetchall()
    assert len(rows) == 1
    assert rows[0]["dedupe_key"] == "sap::ai engineer::berlin"


def test_migration_is_idempotent(db_connection):
    _insert_legacy(db_connection, "SAP", "AI Engineer", "Berlin", "sap::ai engineer")
    _ensure_dedupe_key_includes_location(db_connection)
    _ensure_dedupe_key_includes_location(db_connection)
    db_connection.commit()

    rows = db_connection.execute("SELECT dedupe_key FROM jobs").fetchall()
    assert [row["dedupe_key"] for row in rows] == ["sap::ai engineer::berlin"]
