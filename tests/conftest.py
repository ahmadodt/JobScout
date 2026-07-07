from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.db import connect, init_db  # noqa: E402


@pytest.fixture()
def db_connection():
    connection = connect(":memory:")
    init_db(connection)
    yield connection
    connection.close()
