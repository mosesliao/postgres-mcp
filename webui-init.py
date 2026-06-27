"""
Run once after Open WebUI initializes its DB to seed the config.
Skips if config already has tool_server connections configured.
Usage: python /app/backend/webui-init.py
"""
import sqlite3
import json

DB_PATH = "/app/backend/data/webui.db"

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


def main():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        row = conn.execute("SELECT data FROM config WHERE id=1").fetchone()
        if row:
            existing = json.loads(row[0])
            connections = existing.get("tool_server", {}).get("connections", [])
            if connections:
                print("Config already has tool_server connections — skipping.")
                return
            existing.update(CONFIG)
            conn.execute(
                "UPDATE config SET data=? WHERE id=1", (json.dumps(existing),)
            )
        else:
            conn.execute(
                "INSERT INTO config (id, data, version) VALUES (1, ?, 0)", (json.dumps(CONFIG),)
            )
        conn.commit()
        print("Config seeded successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
