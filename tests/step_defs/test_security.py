import psycopg2
import pytest
from pytest_bdd import given, parsers, scenario, then, when

import server

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@scenario("../features/security.feature", "A valid SELECT query is accepted")
def test_valid_select():
    pass


@scenario("../features/security.feature", "A valid WITH (CTE) query is accepted")
def test_valid_cte():
    pass


@scenario("../features/security.feature", "Leading whitespace does not bypass the keyword check")
def test_leading_whitespace():
    pass


@scenario("../features/security.feature", "A semicolon prefix does not bypass the keyword check")
def test_semicolon_prefix():
    pass


@scenario(
    "../features/security.feature",
    "A write operation hidden inside a CTE is rejected by the database session",
)
def test_cte_write_smuggling():
    pass


@scenario("../features/security.feature", "The database connection is opened in read-only mode")
def test_connection_readonly():
    pass


@scenario(
    "../features/security.feature",
    "A direct INSERT on a read-only session is rejected by PostgreSQL",
)
def test_direct_insert_rejected():
    pass


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO products (product_name) VALUES ('x')",
        "UPDATE products SET unit_price = 0",
        "DELETE FROM products WHERE product_id = 1",
        "DROP TABLE products",
        "TRUNCATE TABLE products",
        "ALTER TABLE products ADD COLUMN foo TEXT",
        "CREATE TABLE hacked (id INT)",
    ],
)
def test_write_sql_rejected(sql):
    with pytest.raises(ValueError, match="Only SELECT / WITH queries are permitted"):
        server.query(sql)


@pytest.mark.parametrize(
    "table_name",
    [
        "orders; DROP TABLE orders--",
        "1_invalid",
        "orders UNION SELECT 1--",
        "",
        "orders'--",
    ],
)
def test_malicious_table_name_describe(table_name):
    with pytest.raises(ValueError, match="Invalid identifier"):
        server.describe_table(table_name)


@pytest.mark.parametrize(
    "table_name",
    [
        "orders; DROP TABLE orders--",
        "products'--",
    ],
)
def test_malicious_table_name_sample(table_name):
    with pytest.raises(ValueError, match="Invalid identifier"):
        server.sample_table(table_name)


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


@given("the database session is read-only")
def db_session_readonly(ctx, db_url):
    conn = psycopg2.connect(db_url)
    conn.set_session(readonly=True, autocommit=False)
    ctx["conn"] = conn
    yield
    if not conn.closed:
        conn.close()


@given("a real database connection is established")
def real_db_connection(ctx, db_url):
    conn = psycopg2.connect(db_url)
    conn.set_session(readonly=True, autocommit=False)
    ctx["conn"] = conn
    yield
    if not conn.closed:
        conn.close()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('I call query with "{sql}"'))
def call_query(ctx, sql):
    sql = sql.replace("\\n", "\n")
    try:
        ctx["result"] = server.query(sql)
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


@when(parsers.parse('I call sample_table with "{table_name}"'))
def call_sample_table(ctx, table_name):
    try:
        ctx["result"] = server.sample_table(table_name)
        ctx["error"] = None
    except Exception as exc:
        ctx["error"] = exc
        ctx["result"] = None


@when(parsers.parse('I execute "{sql}" directly on the connection'))
def execute_directly(ctx, sql):
    conn = ctx["conn"]
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        ctx["error"] = None
    except Exception as exc:
        conn.rollback()
        ctx["error"] = exc


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("it should raise a ValueError")
def raises_value_error(ctx):
    assert isinstance(
        ctx["error"], ValueError
    ), f"Expected ValueError, got {type(ctx['error'])}: {ctx['error']}"


@then("it should not raise an error")
def no_error(ctx):
    assert ctx["error"] is None, f"Unexpected error: {ctx['error']}"


@then(parsers.parse('the error message should contain "{text}"'))
def error_message_contains(ctx, text):
    assert text in str(ctx["error"]), f"Expected {text!r} in error message, got: {ctx['error']}"


@then("the database should raise a read-only transaction error")
def db_readonly_error(ctx):
    err = ctx["error"]
    assert err is not None, "Expected a database error but none was raised"
    assert isinstance(err, psycopg2.Error), f"Expected psycopg2.Error, got {type(err)}"
    assert (
        "read-only" in str(err).lower() or "cannot execute" in str(err).lower()
    ), f"Expected read-only error, got: {err}"


@then("the session should have the read-only flag set to true")
def session_is_readonly(ctx):
    conn = ctx["conn"]
    with conn.cursor() as cur:
        cur.execute("SHOW transaction_read_only")
        value = cur.fetchone()[0]
    assert value == "on", f"Expected transaction_read_only=on, got {value!r}"
