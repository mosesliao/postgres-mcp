# Northwind PostgreSQL MCP Server

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A read-only MCP (Model Context Protocol) server that connects AI models to the [Northwind](https://github.com/pthom/northwind_psql) sample PostgreSQL database. Ask natural language questions and the model will query the database on your behalf.

---

## What is this?

This project lets an AI model act as a data analyst over the Northwind database — a classic sample dataset covering customers, orders, products, employees, and suppliers. The model can list tables, inspect schemas, run SQL queries, and generate charts, all through a secure read-only connection.

---

## Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop |
| Node.js (for Claude Code only) | 18+ | https://nodejs.org |
| Python (for Claude Code / Desktop only) | 3.11+ | https://www.python.org/downloads |

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd postgres_mcp
```

### 2. Set up your environment file

```bash
cp .env.example .env
```

Edit `.env` and fill in your Anthropic API key:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/northwind
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Start all services

Docker Desktop must be running (look for the whale icon in your system tray).

```bash
docker compose up -d
```

On first run this will:
- Pull the `postgres:16` and `open-webui` images
- Download `northwind.sql` from GitHub and initialise the database
- Start the MCP server and Open WebUI

Verify everything is ready:
```bash
docker compose ps
```
All services should show `running` and `db` should show `healthy`.

---

## Connecting to a model

### Option A — Open WebUI + Ollama (browser-based, no API key needed)

Open WebUI gives you a browser chat interface powered by a local Ollama model. No API key or cloud service required.

**1. Make sure Ollama is running** with at least one model pulled:

```bash
ollama pull llama3
ollama serve
```

**2. Start all services:**

```bash
docker compose up -d
```

**3. Seed the Open WebUI config** (first time only — sets up the MCP connection automatically):

```bash
docker exec postgres_mcp-open-webui-1 python3 /app/backend/webui-init.py
```

**4. Open the UI:**

Go to [http://openwebui.localhost](http://openwebui.localhost) and create an admin account on first launch.

**5. Verify connections:**

- Go to **Admin Settings → Connections** — Ollama should show as connected at `http://host.docker.internal:11434`
- Go to **Settings → Tools** — `postgres-mcp` should be listed and connected at `http://mcp:8000/mcp`

**6. Enable chart generation (Jupyter code execution):**

Go to **Admin Settings → Code Execution** and configure:

- **Enable Code Execution** → on
- **Code Execution Engine** → `Jupyter (Legacy)`
- **Jupyter URL** → `http://jupyter:8888`
- **Jupyter Auth** → `Token`
- **Token** → `open-webui`

Save. The model can now execute Python and return real matplotlib chart images inline.

You can now pick any Ollama model and chat — it will query the Northwind database through the MCP tools.

> **Tip:** Models that generate better charts: `qwen2.5-coder:7b`, `deepseek-coder-v2`, `phi4`. Pull with `ollama pull <model>`.

---

### Option B — Claude Code CLI

Install Claude Code if you have not already:
```bash
npm install -g @anthropic-ai/claude-code
```

Start the database:
```bash
docker compose up -d db
```

Register the MCP server:
```bash
claude mcp add postgres-northwind \
  --env DATABASE_URL=postgresql://postgres:postgres@localhost:5432/northwind \
  python /full/path/to/postgres_mcp/server.py
```

Replace `/full/path/to/postgres_mcp` with the actual path on your machine.

Verify it was registered:
```bash
claude mcp list
```

Start Claude Code and try it out:
```bash
claude
```
Then ask: *"List the tables in my database"*

---

### Option C — Claude Desktop

Open your Claude Desktop config file:

- **Windows**: `C:\Users\<username>\AppData\Roaming\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add the following inside `"mcpServers"`:

```json
{
  "mcpServers": {
    "postgres-northwind": {
      "command": "python",
      "args": ["C:\\full\\path\\to\\postgres_mcp\\server.py"],
      "env": {
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/northwind"
      }
    }
  }
}
```

Start the database first:
```bash
docker compose up -d db
```

Restart Claude Desktop. The MCP tools will appear automatically in new conversations.

---

## Available tools

Once connected, the model has access to these tools:

| Tool | Description |
|------|-------------|
| `list_tables` | Lists all tables in the database |
| `describe_table` | Shows columns, types, and primary keys for a table |
| `sample_table` | Returns the first N rows of a table (max 100) |
| `query` | Runs any SELECT or WITH query (results capped at 500 rows) |
| `get_schema` | Full schema overview — all tables and columns in one call |

### Example prompts

- *"List all tables in the Northwind database"*
- *"How many customers are there, and which countries do they come from?"*
- *"Show me the top 10 best-selling products"*
- *"Show monthly revenue for 1997 as a pie chart using matplotlib"*

![Monthly Revenue](img/monthly-revenue-pie-chart.png)

- *"Who are our top 20 customers by total spend? Show a horizontal bar chart."*

![Top 20 Customers](img/top20_customers.png)

---

## Security

All database access is **read-only**, enforced at two levels:

1. **Application level** — the `query` tool rejects any SQL that does not start with `SELECT` or `WITH`
2. **Database level** — every connection is opened with `readonly=True`, so PostgreSQL itself will reject any write attempt even if the application check were bypassed

Table and column names supplied by users are validated against a strict identifier pattern before being used in queries, preventing SQL injection.

---

## Stopping

```bash
docker compose down
```

To also delete stored data (resets the database and Open WebUI config):
```bash
docker compose down -v
```

> After `down -v`, re-run the webui-init step on next startup to restore the MCP connection config.

---

## Troubleshooting

**`docker compose up` fails with "cannot find the file specified"**
Docker Desktop is not running. Open it from the Start menu and wait for the whale icon in the system tray.

**Open WebUI shows "Trouble accessing Ollama"**
Ollama is not running. Start it with `ollama serve` in a terminal.

**Open WebUI MCP connection fails**
The tool URL must use the Docker service name, not `localhost`:
```
http://mcp:8000/mcp
```
Using `localhost` inside Docker will not work — `mcp` is the correct hostname.

**`pip install -e .` fails with a hatchling error**
```bash
pip install hatchling
pip install -e .
```

**Port 5432 is already in use**
Another PostgreSQL instance is running locally. Change the port in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"
```
Then update `DATABASE_URL` in `.env` to use port `5433`.

**`psycopg2` installation fails on Windows**
Use the binary build:
```bash
pip install psycopg2-binary
```

---

## License

This project is released under the [MIT License](LICENSE). You are free to use, modify, and distribute it for personal or commercial purposes.
