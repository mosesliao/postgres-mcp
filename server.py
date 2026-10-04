import os
import re
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("postgres-northwind", host=os.environ.get("MCP_HOST", "127.0.0.1"))

_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _check_identifier(name: str) -> None:
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")


@contextmanager
def _cursor():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Enforce read-only at the transaction level
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


@mcp.tool()
def list_tables() -> list[str]:
    """List all user tables in the public schema."""
    with _cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return [row["table_name"] for row in cur.fetchall()]


@mcp.tool()
def describe_table(table_name: str) -> list[dict[str, Any]]:
    """
    Return column metadata for a table: name, data type, nullable, default,
    and whether it is part of the primary key.
    """
    _check_identifier(table_name)
    with _cursor() as cur:
        cur.execute(
            """
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema   = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_name      = %s
                  AND tc.table_schema    = 'public'
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_name   = %s
              AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """,
            (table_name, table_name),
        )
        rows = cur.fetchall()
    if not rows:
        raise ValueError(f"Table {table_name!r} not found in public schema")
    return [dict(r) for r in rows]


@mcp.tool()
def sample_table(table_name: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return the first N rows of a table (default 5, max 100)."""
    _check_identifier(table_name)
    limit = max(1, min(limit, 100))
    with _cursor() as cur:
        # Table names cannot be parameterised; _check_identifier above rejects
        # anything outside a strict identifier pattern.
        cur.execute(f'SELECT * FROM public."{table_name}" LIMIT %s', (limit,))  # noqa: S608
        return [dict(r) for r in cur.fetchall()]


@mcp.tool()
def query(sql: str) -> list[dict[str, Any]]:
    """
    Execute a read-only SQL query and return results as a list of row dicts.
    Only SELECT and WITH (CTE) statements are allowed.
    Results are capped at 500 rows.
    """
    normalised = sql.strip().lstrip(";").lstrip()
    first_word = normalised.split()[0].upper() if normalised else ""
    if first_word not in ("SELECT", "WITH"):
        raise ValueError("Only SELECT / WITH queries are permitted. " f"Got: {first_word!r}")
    with _cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchmany(500)
        return [dict(r) for r in rows]


@mcp.tool()
def get_schema() -> str:
    """
    Return a concise text summary of every table and its columns,
    useful for understanding the database structure at a glance.
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                CASE WHEN pk.column_name IS NOT NULL THEN 'PK' ELSE '' END AS key
            FROM information_schema.tables t
            JOIN information_schema.columns c
              ON c.table_name   = t.table_name
             AND c.table_schema = t.table_schema
            LEFT JOIN (
                SELECT kcu.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema    = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema    = 'public'
            ) pk ON pk.table_name  = c.table_name
                AND pk.column_name = c.column_name
            WHERE t.table_schema = 'public'
              AND t.table_type   = 'BASE TABLE'
            ORDER BY t.table_name, c.ordinal_position
        """)
        rows = cur.fetchall()

    lines: list[str] = []
    current_table = None
    for row in rows:
        if row["table_name"] != current_table:
            current_table = row["table_name"]
            lines.append(f"\nTable: {current_table}")
            lines.append("  " + "-" * 40)
        nullable = "" if row["is_nullable"] == "YES" else " NOT NULL"
        key = f" [{row['key']}]" if row["key"] else ""
        lines.append(f"  {row['column_name']:<30} {row['data_type']}{nullable}{key}")

    return "\n".join(lines)


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("sse", "streamable-http"):
        mcp.run(transport=transport)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
