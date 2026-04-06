# Contributing to Manch

Thanks for your interest in contributing! This guide covers how to set up the project, make changes, and submit them.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

### Prerequisites

- **Docker Desktop** (with Docker Compose v2)
- **Node.js 20+** (frontend development)
- **Python 3.11+** (backend development)
- **Git**

### Quick Setup

```bash
# Clone the repo
git clone https://github.com/bigbansal/manch.git
cd manch

# Copy environment file and add your API keys
cp manch-backend/.env.example manch-backend/.env
# Edit .env and add at least one AI provider key

# Start everything
./startup.sh
```

The startup script builds all images, starts containers, and checks port availability.

| Service        | URL                          |
|----------------|------------------------------|
| Frontend       | http://localhost:4401         |
| Backend API    | http://localhost:8212/docs    |
| RabbitMQ UI    | http://localhost:15899        |
| OpenSandbox    | http://localhost:3201/health  |

### Manual Development (without Docker)

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

## Making Changes

### Branch Naming

- `feat/<short-description>` — new features
- `fix/<short-description>` — bug fixes
- `docs/<short-description>` — documentation only
- `refactor/<short-description>` — code restructuring

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add repo clone endpoint
fix: correct sandbox env variable injection
docs: update README with architecture diagram
refactor: extract skill sync into dedicated service
```

### Code Style

**Python (backend):**
- Follow PEP 8
- Use type hints everywhere
- Add docstrings to public functions and classes
- Keep imports sorted (stdlib → third-party → local)

**TypeScript (frontend):**
- Follow Angular style guide
- Use standalone components
- Prefer signals over BehaviorSubjects for state
- Use `inject()` over constructor injection for new code

### Testing

- **Backend:** Place tests in `tests/` — run with `pytest`
- **Frontend:** Use Jasmine/Karma — run with `ng test`
- Add tests for new endpoints and services

## Submitting a Pull Request

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes with clear commit messages
4. Ensure the project builds: `docker compose build`
5. Open a Pull Request against `main`
6. Describe what changed and why in the PR description

### PR Checklist

- [ ] Code compiles without errors
- [ ] New endpoints have Pydantic request/response schemas
- [ ] Frontend changes tested visually
- [ ] No hardcoded secrets or API keys
- [ ] Updated relevant docstrings/comments

## Project Structure

```
manch/
├── manch-backend/        # Python FastAPI backend
│   ├── src/manch_backend/
│   │   ├── api/routes/        # REST endpoints
│   │   ├── services/          # Orchestrator, sandbox, events
│   │   ├── skills/            # Skill system (builtins + custom)
│   │   ├── agents/            # Agent pipeline (Maestro, engine)
│   │   ├── db/                # SQLAlchemy models, migrations
│   │   └── config.py          # App settings
│   └── alembic/               # DB migrations
├── manch-frontend/       # Angular 19 frontend
│   └── src/app/
│       ├── core/services/     # API services
│       ├── features/          # Feature modules (chat, repos, skills…)
│       └── shared/            # Shared components
├── opensandbox-server/        # OpenSandbox server (Docker orchestrator)
├── opensandbox-runtime/       # Sandbox Docker image (CLIs installed)
├── docker-compose.yml
├── startup.sh
└── README.md
```

## Questions?

Open a [GitHub Discussion](https://github.com/bigbansal/manch/discussions) or file an issue.
