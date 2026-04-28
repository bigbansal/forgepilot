# Public Release Checklist

Use this checklist before making the repository public.

## 1) Rotate and revoke credentials

- Revoke any API keys that were ever present in local files, screenshots, logs, or terminal history.
- Rotate provider keys (OpenAI, Gemini, Anthropic, etc.) and issue fresh keys.
- Rotate JWT/app secrets such as `MANCH_SECRET_KEY`.
- Rotate local/dev passwords if reused anywhere else.

## 2) Ensure secrets are not committed

- Confirm `.env`, `.env.*`, key files (`*.pem`, `*.key`) and `secrets/` are ignored by git.
- Run a local scan on tracked files:

```bash
git ls-files | xargs grep -nE 'sk-(proj|live|test)-|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY|xox[baprs]-' || true
```

- If anything sensitive was committed in any branch/tag, rewrite history before publishing.

## 3) Rewrite git history if needed

If a secret was committed, deleting the file now is not enough.

```bash
pip install git-filter-repo
git filter-repo --path manch-backend/.env --invert-paths
```

Then force-push protected branches/tags and rotate all affected credentials.

## 4) Use safe defaults for public code

- Keep demo/dev credentials only in templates (`.env.example`), never in tracked runtime files.
- Keep production values externalized through environment variables.
- Verify CORS, auth, and webhook tokens are configured explicitly in production.

## 5) Enable platform security controls (GitHub)

- Enable Secret scanning and Push protection.
- Enable Dependabot alerts and security updates.
- Require pull request reviews for default branch.
- Add branch protection and signed commit rules as needed.

## 6) Validate OSS readiness

- Confirm `LICENSE`, `README.md`, `SECURITY.md`, and `CONTRIBUTING.md` are accurate.
- Remove internal-only links, hostnames, and personal paths from docs.
- Verify no generated logs or local artifacts are tracked.

## 7) Final pre-public check

```bash
git status --short
git ls-files | wc -l
```

- Create a final review PR and merge only after passing CI secret scan.
