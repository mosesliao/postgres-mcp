FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir "mcp[cli]>=1.0.0,<2.0.0" psycopg2-binary python-dotenv
COPY server.py .
CMD ["python", "server.py"]
