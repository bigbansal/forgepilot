# ForgePilot

OpenClaw-like AI engineering platform with stronger governance, explicit approvals, and sandboxed execution.

## Current Stack

- Frontend: Angular 19
- Backend: Python + FastAPI
- Infra: PostgreSQL, Redis, RabbitMQ
- Runtime: Alibaba OpenSandbox server + Docker sandbox runtime image

## What is already scaffolded

- Multi-agent definitions in `.github/agents`
- FastAPI backend in `forgepilot-backend`
- Angular frontend shell in `forgepilot-frontend`
- Docker compose for full local stack

## MVP Endpoints

- `GET /api/v1/health`
- `POST /api/v1/tasks`
- `POST /api/v1/tasks/{task_id}/start`
- `GET /api/v1/tasks`
- `GET /api/v1/sessions`
- `GET /api/v1/agents`
- `GET /api/v1/events/stream`

## Run locally (quick start)

```bash
./startup.sh
```

Then open:

- Frontend: `http://localhost:4200`
- Backend docs: `http://localhost:8080/docs`
- RabbitMQ UI: `http://localhost:15672` (user: `forgepilot`, pass: `forgepilot_secret`)
- OpenSandbox mock: `http://localhost:3000/health`
- OpenSandbox server: `http://localhost:3000/health`

To stop all services:

```bash
docker compose down
```

## Manual run (without Docker)

Backend:

```bash
cd forgepilot-backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn forgepilot_backend.main:app --reload --host 0.0.0.0 --port 8080
```

Frontend:

```bash
cd forgepilot-frontend
npm install
npm start
```

Run a task with runner selection:

```bash
curl -X POST http://localhost:8080/api/v1/tasks/{task_id}/start \
	-H "Content-Type: application/json" \
	-d '{"runner":"gemini-cli"}'
```

Supported runner values:

- `opensandbox` (default)
- `gemini-cli`
- `codex-cli`

Notes:

- `gemini-cli` and `codex-cli` execute inside the OpenSandbox session.
- This stack uses Alibaba OpenSandbox server (`opensandbox-server`) with Docker runtime.
- Sandbox command execution uses image `forgepilot/sandbox-runtime:local` (built from `opensandbox-runtime/Dockerfile`) which includes both CLIs.
- Configure provider credentials in `forgepilot-backend/.env` (`FORGEPILOT_GEMINI_API_KEY`, `FORGEPILOT_OPENAI_API_KEY`).

## Next build milestone

- Replace in-memory state with PostgreSQL persistence
- Add Temporal/Celery workflow workers
- Harden OpenSandbox isolation and command policy enforcement
- Add SSE live task streaming
- Add approval queue and policy enforcement API
