# Manch

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![Angular 19](https://img.shields.io/badge/Angular-19-DD0031.svg)](https://angular.dev)

**Multi-agent AI engineering platform** with governance, explicit approvals, and sandboxed execution.

Manch orchestrates multiple AI coding agents (Gemini CLI, Codex CLI, Claude Code) through a unified interface, running them safely inside Docker sandboxes with policy-based approval workflows.

## Key Features

- **Multi-Agent Routing** — Send tasks to Gemini CLI, Codex CLI, or Claude Code
- **Sandboxed Execution** — All agent work runs inside isolated Docker containers via OpenSandbox
- **Skill System** — Extensible skills with marketplace, custom creation, and agentskills.io-compliant SKILL.md injection
- **Repo Cloning** — Clone any git repo into a sandbox from the UI or API
- **Approval Workflow** — Risk-based approval queue for high-risk operations
- **Real-time Streaming** — Live agent output via WebSocket/SSE
- **Chat Interface** — Slash commands with command palette
- **Audit Logging** — Track all significant actions across the platform

## Architecture

```
Angular 19 UI  ─────►  FastAPI Backend  ─────►  OpenSandbox (Docker)
(Chat, Repos,          (Orchestrator,            (Gemini CLI,
 Skills, Dash)          Skills, Agents)           Codex CLI,
                        Policy, Events)           Claude Code)
                             │
                  PostgreSQL / Redis / RabbitMQ
```

## Quick Start

### Prerequisites

- **Docker Desktop** with Docker Compose v2
- AI provider key(s): OpenAI, Google Gemini, and/or Anthropic

### Setup

```bash
git clone https://github.com/bigbansal/manch.git
cd manch
cp .env.example .env
cp manch-backend/.env.example manch-backend/.env
# Optional: edit root .env to override docker-compose credentials/ports
# Edit manch-backend/.env and add at least one AI provider API key
./startup.sh
```

### Access

| Service        | URL                                 |
|----------------|-------------------------------------|
| Frontend       | http://localhost:4401               |
| Backend API    | http://localhost:8212/docs          |
| Backend Health | http://localhost:8212/api/v1/health |
| RabbitMQ UI    | http://localhost:15899              |
| OpenSandbox    | http://localhost:3201/health        |
| PostgreSQL     | localhost:5545                      |

### Stop

```bash
docker compose down
```

## API Endpoints

| Method | Endpoint                    | Description                |
|--------|-----------------------------|----------------------------|
| GET    | /api/v1/health              | Health check               |
| POST   | /api/v1/tasks               | Create a task              |
| POST   | /api/v1/tasks/{id}/start    | Start task execution       |
| GET    | /api/v1/tasks               | List tasks                 |
| GET    | /api/v1/sessions            | List sandbox sessions      |
| GET    | /api/v1/agents              | List available agents      |
| GET    | /api/v1/events/stream       | SSE event stream           |
| GET    | /api/v1/repos               | List repositories          |
| POST   | /api/v1/repos               | Register a repository      |
| POST   | /api/v1/repos/{id}/clone    | Clone a registered repo    |
| POST   | /api/v1/repos/clone         | Quick-clone any git URL    |
| GET    | /api/v1/skills              | List skills                |
| POST   | /api/v1/skills/create       | Create a custom skill      |

## Manual Development

**Backend:**

```bash
cd manch-backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn manch_backend.main:app --reload --host 0.0.0.0 --port 8080
```

**Frontend:**

```bash
cd manch-frontend
npm install --legacy-peer-deps
ng serve --port 4401
```

## Runners

Manch supports three AI agent runners, all executing inside OpenSandbox:

| Runner      | CLI                        | Provider  |
|-------------|----------------------------|-----------|
| gemini-cli  | @google/gemini             | Google    |
| codex-cli   | @openai/codex              | OpenAI    |
| claude-code | @anthropic-ai/claude-code  | Anthropic |

## Tech Stack

| Layer    | Technology                                   |
|----------|----------------------------------------------|
| Frontend | Angular 19, Signals, Monaco Editor, xterm.js |
| Backend  | Python 3.12, FastAPI, SQLAlchemy, Pydantic   |
| Database | PostgreSQL 16                                |
| Cache    | Redis 7                                      |
| Queue    | RabbitMQ 3.13                                |
| Sandbox  | Alibaba OpenSandbox + Docker runtime         |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, code style, and PR guidelines.

## Security

Report vulnerabilities privately. See [SECURITY.md](SECURITY.md).

Before making your fork/repo public, run through [docs/public-release-checklist.md](docs/public-release-checklist.md).

## License

[MIT](LICENSE) — Copyright (c) 2026 bigbansal
