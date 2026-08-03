"""
Seed the Northwind Analyst model preset into Open WebUI.

Connection settings (Ollama, the MCP tool server, Jupyter code execution) all
come from environment variables in docker-compose.yml, which Open WebUI reads
at request time. Model presets have no equivalent env var, so they are the one
thing that has to be written to the database.

Usage: python /app/backend/webui-init.py
"""

import json
import os
import sqlite3
import time

DB_PATH = "/app/backend/data/webui.db"

# Overridable so CI can seed the preset against a small, fast model.
BASE_MODEL = os.environ.get("NORTHWIND_BASE_MODEL", "llama3:latest")

SYSTEM_PROMPT = (
    "When the user asks for any chart, graph, plot, or data visualization, "
    "always generate Python code using matplotlib and execute it so the chart "
    "renders inline as an image. Never use Chart.js, SVG, or any other method. "
    "Always include clear axis labels, a title, and call plt.tight_layout() before showing."
)

MODEL_PRESET = {
    "id": "northwind-analyst",
    "base_model_id": BASE_MODEL,
    "name": "Northwind Analyst",
    # Open WebUI reads the system prompt from params["system"] when building the
    # request (see routers/ollama.py). meta["system"] alone is never applied.
    "params": json.dumps({"system": SYSTEM_PROMPT}),
    "meta": json.dumps(
        {
            "description": (
                "Northwind data analyst — queries PostgreSQL and generates matplotlib charts."
            ),
            "system": SYSTEM_PROMPT,
        }
    ),
}


def admin_user_id(conn):
    """Owner of the preset. Falls back to 'admin' if no user has signed up yet."""
    row = conn.execute(
        "SELECT id FROM user WHERE role='admin' ORDER BY created_at LIMIT 1"
    ).fetchone()
    return row[0] if row else "admin"


def seed_model_preset(conn):
    now = int(time.time())
    user_id = admin_user_id(conn)
    existing = conn.execute("SELECT id FROM model WHERE id=?", (MODEL_PRESET["id"],)).fetchone()
    if existing:
        # Repair in place so re-runs pick up prompt changes and fix older seeds
        # that stored the system prompt only under meta.
        conn.execute(
            """UPDATE model SET user_id=?, base_model_id=?, name=?, params=?, meta=?,
                                updated_at=?, is_active=1
               WHERE id=?""",
            (
                user_id,
                MODEL_PRESET["base_model_id"],
                MODEL_PRESET["name"],
                MODEL_PRESET["params"],
                MODEL_PRESET["meta"],
                now,
                MODEL_PRESET["id"],
            ),
        )
        conn.commit()
        print("Model preset 'Northwind Analyst' updated.")
        return
    conn.execute(
        """INSERT INTO model (id, user_id, base_model_id, name, params, meta,
                             updated_at, created_at, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            MODEL_PRESET["id"],
            user_id,
            MODEL_PRESET["base_model_id"],
            MODEL_PRESET["name"],
            MODEL_PRESET["params"],
            MODEL_PRESET["meta"],
            now,
            now,
        ),
    )
    conn.commit()
    print("Model preset 'Northwind Analyst' seeded successfully.")


def main():
    # WAL lets us write while Open WebUI holds the database open.
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        seed_model_preset(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
