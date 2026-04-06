# Manch Backend

FastAPI backend for Manch orchestration.

## Run locally

```bash
cd manch-backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn manch_backend.main:app --reload --host 0.0.0.0 --port 8080
```

## Key endpoints

- `GET /api/v1/health`
- `POST /api/v1/tasks`
- `POST /api/v1/tasks/{task_id}/start`
- `GET /api/v1/tasks`
- `GET /api/v1/sessions`
- `GET /api/v1/agents`
- `GET /api/v1/events/stream` (SSE)
