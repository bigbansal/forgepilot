# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, report them privately:

1. **Email:** manch@bigbansal.dev
2. **Subject:** `[SECURITY] <brief description>`
3. Include:
   - Steps to reproduce
   - Impact assessment
   - Affected component (backend, frontend, sandbox, etc.)

We aim to acknowledge reports within **48 hours** and provide an initial assessment within **5 business days**.

## Security Best Practices for Contributors

- **Never commit API keys or secrets.** Use `.env` files (already in `.gitignore`).
- **Never hardcode credentials** in source code, Dockerfiles, or config files.
- Generate strong secrets: `openssl rand -hex 32`
- Review dependencies for known vulnerabilities before adding them.
- Sandbox execution is isolated via Docker — do not weaken container permissions.

## Known Considerations

- **psycopg** is LGPL-3.0 licensed — used as a library dependency (not modified/redistributed).
- Dev-default passwords in `docker-compose.yml` (`manch_secret`) are for local development only. **Change them in production.**
- The sandbox runtime mounts `/var/run/docker.sock` for container orchestration — **restrict access in production environments.**

## Before Making The Repo Public

- Follow `docs/public-release-checklist.md` end-to-end.
- If any secret was committed historically, rotate it and rewrite git history before publication.
- Enable GitHub Secret Scanning + Push Protection on the repository.
