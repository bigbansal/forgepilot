#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ── Notification helpers ──────────────────────────────────────────────────────
BLUE="\033[1;34m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

info() { echo -e "${BLUE}[INFO]${RESET} $*"; }
ok() { echo -e "${GREEN}[OK]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*"; }

step() {
  local step_no="$1"
  local title="$2"
  echo
  echo -e "${BLUE}==> Step ${step_no}: ${title}${RESET}"
}

AUTO_KILL_PORTS="${FORGEPILOT_AUTO_KILL_PORTS:-true}"
KILL_LOCAL_PORT_PROCESSES="${FORGEPILOT_KILL_LOCAL_PORT_PROCESSES:-false}"
REQUIRED_PORTS=(
  "4200:Frontend"
  "8080:Backend API"
  "3000:OpenSandbox"
  "5432:PostgreSQL"
  "6379:Redis"
  "5672:RabbitMQ AMQP"
  "15672:RabbitMQ UI"
)

port_in_use() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

show_port_owners() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN || true
  fi
}

free_port() {
  local port="$1"

  local docker_ids
  docker_ids="$(docker ps --filter "publish=${port}" --format '{{.ID}}' || true)"
  if [[ -n "${docker_ids}" ]]; then
    warn "Port ${port} is used by running Docker container(s). Stopping them..."
    echo "${docker_ids}" | xargs -I{} docker stop {} >/dev/null || true
  fi

  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
    if [[ -n "${pids}" ]]; then
      if [[ "${KILL_LOCAL_PORT_PROCESSES}" == "true" ]]; then
        warn "Killing local process(es) on port ${port}: ${pids}"
        echo "${pids}" | xargs -I{} kill -TERM {} 2>/dev/null || true
        sleep 1

        local remaining
        remaining="$(lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
        if [[ -n "${remaining}" ]]; then
          warn "Force killing stubborn process(es) on port ${port}: ${remaining}"
          echo "${remaining}" | xargs -I{} kill -KILL {} 2>/dev/null || true
        fi
      fi
    fi
  fi
}

check_and_handle_ports() {
  local conflicts=0
  for entry in "${REQUIRED_PORTS[@]}"; do
    local port
    local label
    port="${entry%%:*}"
    label="${entry#*:}"

    if port_in_use "$port"; then
      conflicts=1
      warn "Port ${port} (${label}) is already in use"
      show_port_owners "$port"

      if [[ "${AUTO_KILL_PORTS}" == "true" ]]; then
        free_port "$port"

        if port_in_use "$port"; then
          error "Port ${port} (${label}) is still in use after Docker cleanup."
          warn "A local process is still listening on this port."
          warn "To auto-kill local processes, run: FORGEPILOT_KILL_LOCAL_PORT_PROCESSES=true ./startup.sh"
          warn "Or manually stop that process and retry."
          exit 1
        fi
      else
        error "Set FORGEPILOT_AUTO_KILL_PORTS=true to auto-resolve, or free port ${port} manually."
        exit 1
      fi
    fi
  done

  if [[ "$conflicts" -eq 0 ]]; then
    ok "All required ports are available"
  else
    ok "Port conflicts handled"
  fi
}

info "ForgePilot startup initiated"
info "Project root: $ROOT_DIR"
info "Auto-kill Docker port conflicts: ${AUTO_KILL_PORTS}"
info "Auto-kill local port listeners: ${KILL_LOCAL_PORT_PROCESSES}"

if ! command -v docker >/dev/null 2>&1; then
  error "Docker CLI not found. Install Docker Desktop first."
  exit 1
fi

ok "Docker CLI detected"

step "1/6" "Checking Docker daemon"

if ! docker info >/dev/null 2>&1; then
  error "Docker daemon is not running."
  warn "Start Docker Desktop, wait for Engine running, then re-run ./startup.sh"
  warn "Quick check command: docker info"
  exit 1
fi

ok "Docker daemon is running"

step "2/6" "Validating docker compose configuration"
if docker compose config >/dev/null; then
  ok "docker-compose configuration is valid"
else
  error "docker-compose configuration validation failed"
  exit 1
fi

step "3/6" "Checking and resolving port conflicts"
check_and_handle_ports

step "4/6" "Building and starting services"
info "This may take longer on first run while images are built"
docker compose up -d --build
ok "Containers started"

step "5/6" "Current container status"
docker compose ps

step "6/6" "Health check hints"
info "Give services ~10-30 seconds on first startup, then check:"
echo "  - curl http://localhost:3000/health"
echo "  - curl http://localhost:8080/api/v1/health"

echo
ok "ForgePilot startup complete"
echo "Frontend      : http://localhost:4200"
echo "Backend Docs  : http://localhost:8080/docs"
echo "Backend Health: http://localhost:8080/api/v1/health"
echo "Event Stream  : http://localhost:8080/api/v1/events/stream"
echo "OpenSandbox   : http://localhost:3000/health"
echo "RabbitMQ UI   : http://localhost:15672 (forgepilot / forgepilot_secret)"
echo
info "To stop services: docker compose down"
