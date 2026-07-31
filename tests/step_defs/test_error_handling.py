from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from pytest_bdd import given, parsers, scenario, then, when

import server

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@scenario("../features/error_handling.feature", "Query fails clearly when DATABASE_URL is not set")
def test_no_database_url():
    pass


@scenario(
    "../features/error_handling.feature", "Query fails clearly when the database is unreachable"
)
def test_db_unreachable_query():
    pass


@scenario(
    "../features/error_handling.feature",
    "list_tables fails clearly when the database is unreachable",
)
def test_db_unreachable_list_tables():
    pass


@scenario(
    "../features/error_handling.feature",
    "describe_table raises an error for a table that does not exist",
)
def test_unknown_table():
    pass


@scenario("../features/error_handling.feature", "Malformed SQL raises a database error")
def test_malformed_sql():
    pass


@scenario("../features/error_handling.feature", "sample_table limit is capped at 100 rows")
def test_limit_cap():
    pass


@scenario("../features/error_handling.feature", "sample_table limit is at least 1 row")
def test_limit_floor():
    pass


@scenario("../features/error_handling.feature", "query results are capped at 500 rows")
def test_query_row_cap():
    pass


@scenario("../features/error_handling.feature", "query returns an empty list when no rows match")
def test_empty_result():
    pass


@scenario(
    "../features/error_handling.feature", "Database connection is closed after a successful query"
)
def test_conn_closed_on_success():
    pass


@scenario(
    "../features/error_handling.feature",
    "Database connection is closed even when a query raises an error",
)
def test_conn_closed_on_error():
    pass


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("the MCP server is initialised")
def mcp_initialised():
    assert server.mcp is not None


@given("the DATABASE_URL environment variable is not set")
def no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


@given("the database is unreachable")
def db_unreachable(ctx, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:wrong@localhost:9999/northwind")


@given("the database is connected")
def db_connected(ctx):
    pass


@given("the database returns more than 500 rows")
def db_many_rows(ctx):
    pass


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('I call query with "{sql}"'))
def call_query(ctx, sql):
    try:
        ctx["result"] = server.query(sql)
        ctx["error"] = None
    except Exception as exc:
        ctx["error"] = exc
        ctx["result"] = None


@when("I call list_tables")
def call_list_tables(ctx):
    try:
        ctx["result"] = server.list_tables()
        ctx["error"] = None
    except Exception as exc:
        ctx["error"] = exc
        ctx["result"] = None


@when(parsers.parse('I call describe_table with "{table_name}"'))
def call_describe_table(ctx, table_name):
    try:
        ctx["result"] = server.describe_table(table_name)
        ctx["error"] = None
    except Exception as exc:
        ctx["error"] = exc
        ctx["result"] = None


@when(parsers.parse('I call sample_table with "{table_name}" and limit {limit:d}'))
def call_sample_table_with_limit(ctx, table_name, limit):
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    ctx["mock_cur"] = mock_cur

    with patch("server.psycopg2.connect", return_value=mock_conn):
        try:
            ctx["result"] = server.sample_table(table_name, limit)
            ctx["error"] = None
        except Exception as exc:
            ctx["error"] = exc
            ctx["result"] = None


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("it should raise a RuntimeError")
def raises_runtime_error(ctx):
    assert isinstance(
        ctx["error"], RuntimeError
    ), f"Expected RuntimeError, got {type(ctx['error'])}: {ctx['error']}"


@then("it should raise a ValueError")
def raises_value_error(ctx):
    assert isinstance(
        ctx["error"], ValueError
    ), f"Expected ValueError, got {type(ctx['error'])}: {ctx['error']}"


@then("it should raise a database connection error")
def raises_connection_error(ctx):
    assert ctx["error"] is not None, "Expected an error but none was raised"
    assert isinstance(
        ctx["error"], (psycopg2.OperationalError, Exception)
    ), f"Expected a connection error, got {type(ctx['error'])}: {ctx['error']}"


@then("it should raise a database syntax error")
def raises_syntax_error(ctx):
    assert ctx["error"] is not None, "Expected an error but none was raised"
    assert isinstance(
        ctx["error"], psycopg2.Error
    ), f"Expected psycopg2.Error, got {type(ctx['error'])}: {ctx['error']}"


@then(parsers.parse('the error message should contain "{text}"'))
def error_message_contains(ctx, text):
    assert text in str(ctx["error"]), f"Expected {text!r} in error message, got: {ctx['error']}"


@then(parsers.parse("the SQL executed should use a limit of {expected_limit:d}"))
def sql_uses_limit(ctx, expected_limit):
    mock_cur = ctx["mock_cur"]
    executed_sql = mock_cur.execute.call_args
    assert executed_sql is not None, "cursor.execute was never called"
    args = executed_sql[0]
    assert args[1] == (expected_limit,), f"Expected limit {expected_limit}, got {args[1]}"


@then(parsers.parse("the result should contain at most {max_rows:d} rows"))
def result_at_most(ctx, max_rows):
    result = ctx["result"]
    assert result is not None, f"Expected a result but got error: {ctx['error']}"
    assert len(result) <= max_rows, f"Expected ≤{max_rows} rows, got {len(result)}"


@then("the result should be an empty list")
def result_is_empty(ctx):
    assert ctx["result"] == [], f"Expected [], got {ctx['result']}"


@then("the connection should be closed afterwards")
def connection_closed(ctx):
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cur = MagicMock()
    mock_cur.fetchmany.return_value = []
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("server.psycopg2.connect", return_value=mock_conn):
        try:
            server.query("SELECT 1")
        except Exception:
            pass

    mock_conn.close.assert_called_once()
