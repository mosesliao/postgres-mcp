import os
import pytest
import psycopg2


@pytest.fixture
def db_url():
    return os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/northwind")


@pytest.fixture
def real_conn(db_url):
    conn = psycopg2.connect(db_url)
    yield conn
    if not conn.closed:
        conn.close()
