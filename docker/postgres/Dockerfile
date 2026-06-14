FROM postgres:16
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://raw.githubusercontent.com/pthom/northwind_psql/master/northwind.sql \
    -o /docker-entrypoint-initdb.d/northwind.sql
