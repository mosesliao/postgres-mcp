# Northwind PostgreSQL MCP Server

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A read-only MCP (Model Context Protocol) server that connects Claude to the [Northwind](https://github.com/pthom/northwind_psql) sample PostgreSQL database. Ask Claude natural language questions and it will query the database on your behalf.

---

## What is this?

This project lets Claude act as a data analyst over the Northwind database — a classic sample dataset covering customers, orders, products, employees, and suppliers. Claude can list tables, inspect schemas, run SQL queries, and generate charts, all through a secure read-only connection.

---

## Prerequisites

Before you start, make sure you have the following installed:

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11+ | https://www.python.org/downloads |
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop |
| Node.js (for Claude Code) | 18+ | https://nodejs.org |

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd postgres_mcp
```

### 2. Start the database

Docker Desktop must be running (look for the whale icon in your system tray).

```bash
docker compose up -d
```

On first run this will:
- Pull the `postgres:16` image
- Download `northwind.sql` from GitHub (~2 minutes depending on your connection)
- Initialise the database automatically

Verify the database is ready:
```bash
docker compose ps
```
The `db` service should show `healthy`.

### 3. Set up your environment file

```bash
cp .env.example .env
```

The default `.env` connects to the Docker container:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/northwind
```

No changes needed unless you are using a different PostgreSQL instance.

### 4. Install Python dependencies

```bash
pip install -e .
```

> If you get a `hatchling` error, run `pip install hatchling` first, then retry.

Alternatively, install dependencies directly without the editable install:
```bash
pip install "mcp[cli]>=1.0.0" psycopg2-binary python-dotenv
```

---

## Connecting to Claude

### Option A — Open WebUI (no Claude Desktop required)

Open WebUI gives any user a browser-based chat interface connected to Claude and the Northwind MCP server. No local Python or Claude Desktop install needed.

**1. Add your Anthropic API key to `.env`:**

```bash
cp .env.example .env
```

Edit `.env` and fill in your key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

**2. Start all services:**

```bash
docker compose up -d
```

This starts three containers:
- `db` — Northwind PostgreSQL database
- `mcp` — MCP server in HTTP/SSE mode on port 8000
- `open-webui` — Web UI on port 3000

**3. Open the UI:**

Go to [http://localhost:3000](http://localhost:3000) and create an admin account on first launch.

**4. Connect Claude:**

- Go to **Settings → Admin Panel → Connections**
- Under **Direct Connections**, add a new connection:
  - Provider: **Anthropic**
  - API Key: your `ANTHROPIC_API_KEY`
- Save and select a Claude model (e.g. `claude-sonnet-4-5`)

**5. Connect the MCP server:**

- Go to **Settings → Tools**
- Add a new tool server with URL: `http://mcp:8000/sse`
- Save — the Northwind tools (`list_tables`, `query`, etc.) will appear automatically

You can now chat with Claude in the browser and it will query the Northwind database on your behalf.

---

### Option B — Claude Code CLI (recommended)

Install Claude Code if you have not already:
```bash
npm install -g @anthropic-ai/claude-code
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

### Option C — Claude Desktop (claude.ai)

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

Restart Claude Desktop. The MCP tools will appear automatically in new conversations.

---

## Available tools

Once connected, Claude has access to these tools:

| Tool | Description |
|------|-------------|
| `list_tables` | Lists all tables in the database |
| `describe_table` | Shows columns, types, and primary keys for a table |
| `sample_table` | Returns the first N rows of a table (max 100) |
| `query` | Runs any SELECT or WITH query (results capped at 500 rows) |
| `get_schema` | Full schema overview — all tables and columns in one call |

### Examples of claude prompts to generate reports from NorthWind DB

- *"Show me monthly revenue for 1997, as a bar chart. Include a trend line and highlight the top 3 months."*

![Monthly Revenue](img/monthly-revenue-bar-chart.png)

- *"Who are our top 20 customers by total spend? Show a horizontal bar chart and flag any who haven't ordered in 90+ days."*

![Top 20 Customers](img/top20_customers.png)

---

## Security

All database access is **read-only**, enforced at two levels:

1. **Application level** — the `query` tool rejects any SQL that does not start with `SELECT` or `WITH`
2. **Database level** — every connection is opened with `readonly=True`, so PostgreSQL itself will reject any write attempt even if the application check were bypassed

Table and column names supplied by users are validated against a strict identifier pattern before being used in queries, preventing SQL injection.

---

## Stopping the database

```bash
docker compose down
```

To also delete the stored data:
```bash
docker compose down -v
```

---

## Troubleshooting

**`docker compose up` fails with "cannot find the file specified"**
Docker Desktop is not running. Open it from the Start menu and wait for the whale icon to appear in the system tray before retrying.

**`pip install -e .` fails with a hatchling error**
```bash
pip install hatchling
pip install -e .
```

**Claude says the MCP server is not connected**
- Confirm the database is running: `docker compose ps`
- Confirm `server.py` path in your MCP config is the full absolute path
- Confirm `DATABASE_URL` matches your Docker setup

**`psycopg2` installation fails on Windows**
Use the binary build which has no system dependencies:
```bash
pip install psycopg2-binary
```

**Open WebUI can't reach the MCP server**
The tool URL must use the Docker service name, not `localhost`:
```
http://mcp:8000/sse
```
Using `localhost` won't work inside Docker — `mcp` is the correct hostname.

**Port 5432 is already in use**
Another PostgreSQL instance is running locally. Either stop it or change the port in `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"
```
Then update your `DATABASE_URL` to use port `5433`.

---

## License

This project is released under the [MIT License](LICENSE). You are free to use, modify, and distribute it for personal or commercial purposes, including connecting it to your own business database.
