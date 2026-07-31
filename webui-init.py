"""
Run once after Open WebUI initializes its DB to seed the config and model presets.
Skips if config already has tool_server connections configured.
Usage: python /app/backend/webui-init.py
"""

import json
import os
import sqlite3
import time

DB_PATH = "/app/backend/data/webui.db"

# Overridable so CI can seed the preset against a small, fast model.
BASE_MODEL = os.environ.get("NORTHWIND_BASE_MODEL", "llama3:latest")

CONFIG = {
    "version": 0,
    "ui": {"enable_signup": False},
    "openai": {
        "enable": False,
        "api_base_urls": ["https://api.openai.com/v1"],
        "api_keys": [""],
        "api_configs": {"0": {"enable": True}},
    },
    "ollama": {
        "enable": True,
        "base_urls": ["http://host.docker.internal:11434"],
        "api_configs": {
            "0": {
                "enable": True,
                "tags": [],
                "prefix_id": "",
                "model_ids": [],
                "connection_type": "local",
                "auth_type": "bearer",
                "key": "",
            }
        },
    },
    "direct": {"enable": True},
    "models": {"base_models_cache": True},
    "tool_server": {
        "connections": [
            {
                "url": "http://mcp:8000/mcp",
                "path": "openapi.json",
                "type": "mcp",
                "auth_type": "bearer",
                "headers": None,
                "key": "",
                "config": {
                    "enable": True,
                    "function_name_filter_list": "",
                    "access_grants": [],
                },
                "info": {
                    "id": "1",
                    "name": "postgres-mcp",
                    "description": "Northwind PostgreSQL MCP",
                },
                "spec_type": "url",
                "spec": "",
            }
        ]
    },
}


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


def seed_config(conn):
    row = conn.execute("SELECT data FROM config WHERE id=1").fetchone()
    if row:
        existing = json.loads(row[0])
        connections = existing.get("tool_server", {}).get("connections", [])
        if connections:
            print("Config already has tool_server connections — skipping config seed.")
            return
        existing.update(CONFIG)
        conn.execute("UPDATE config SET data=? WHERE id=1", (json.dumps(existing),))
    else:
        conn.execute(
            "INSERT INTO config (id, data, version) VALUES (1, ?, 0)", (json.dumps(CONFIG),)
        )
    conn.commit()
    print("Config seeded successfully.")


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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        seed_config(conn)
        seed_model_preset(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
