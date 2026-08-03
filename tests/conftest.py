import os

import psycopg2
import pytest

# The end-to-end module imports requests and pytest-playwright, which only the
# [e2e] extra installs. pytest imports every test module before applying `-m`,
# so without this the unit job dies at collection instead of deselecting them.
collect_ignore = []
try:
    import playwright  # noqa: F401
    import requests  # noqa: F401
except ImportError:
    collect_ignore.append("step_defs/test_webui_integration.py")


@pytest.fixture
def db_url():
    return os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/northwind")


@pytest.fixture
def real_conn(db_url):
    conn = psycopg2.connect(db_url)
    yield conn
    if not conn.closed:
        conn.close()
