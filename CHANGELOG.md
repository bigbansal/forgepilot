# Changelog

All notable changes to Manch will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Multi-agent orchestration** — route tasks to Gemini CLI, Codex CLI, or Claude Code
- **Skill system** — builtin skills, custom skill creation, and marketplace
- **SKILL.md routing** — agentskills.io-compliant skill injection before CLI runs
- **Local skill sync** — skills auto-sync to `~/.codex/skills/` and `~/.gemini/skills/`
- **Repo management** — register, list, update, and delete repositories
- **Repo cloning** — clone registered repos or any URL into sandboxes
- **Chat interface** — real-time chat with streaming agent output
- **Slash commands** — `/create-skill`, `/sync-skills`, `/list-skills`, `/help`
- **Command palette** — type `/` in chat for keyboard-navigable command list
- **Approval queue** — risk-based approval workflow for high-risk operations
- **Audit logging** — track all significant actions
- **Session management** — sandbox sessions with terminal streaming
- **Task state machine** — CREATED → RUNNING → COMPLETED lifecycle
- **Docker Compose stack** — one-command startup with `./startup.sh`
- **OpenSandbox integration** — Docker-based isolated execution environments

## [0.1.0] — 2026-04-06

### Added
- Initial project scaffold
- FastAPI backend with PostgreSQL, Redis, RabbitMQ
- Angular 19 frontend with standalone components and signals
- MIT License
