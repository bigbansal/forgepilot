FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir opensandbox-server

COPY sandbox.toml /app/sandbox.toml

EXPOSE 8080

CMD ["opensandbox-server", "--config", "/app/sandbox.toml"]
