"""Transparent reverse-proxy to the most-recent active sandbox.

Exposes ``/preview/{port}`` and ``/preview/{port}/{path}`` so the user
can access sandbox services via a clean URL like
``http://localhost:8080/preview/9000`` without seeing any sandbox IDs.

HTML responses are rewritten so that ``<base href="/">`` points at the
preview prefix, ensuring relative asset paths (JS, CSS, images) load
correctly through the proxy.
"""

from __future__ import annotations

import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import select

from manch_backend.config import settings
from manch_backend.core.deps import AuthContext, get_user_from_token
from manch_backend.db.models import PortMappingRecord, SessionRecord, UserRecord
from manch_backend.db.session import SessionLocal
from manch_backend.models import TaskStatus

router = APIRouter()

# Shared async HTTP client — reused across requests for connection pooling.
_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

# Regex to match <base href="..."> in HTML
_BASE_HREF_RE = re.compile(
    rb'(<base\s+href=["\'])([^"\']*?)(["\'])',
    re.IGNORECASE,
)


def get_preview_user(request: Request, token: str | None = Query(None)) -> AuthContext:
    """Authenticate preview requests via bearer header or query token.

    Query token support allows links opened directly in the browser to work
    from the authenticated frontend session.
    """
    auth_header = request.headers.get("authorization")
    scheme, credentials = get_authorization_scheme_param(auth_header)
    raw_token = credentials if scheme.lower() == "bearer" and credentials else token
    if not raw_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return get_user_from_token(raw_token)


def _resolve_sandbox_session_id(
    port: int | None = None,
    task_id: str | None = None,
) -> str:
    """Return the ``sandbox_session_id`` that owns *port*.

    Resolution order:
    1. Exact port mapping from the ``port_mappings`` table (fastest).
    2. Most-recent RUNNING/COMPLETED session (fallback).
    """
    with SessionLocal() as db:
        # 1. Port-based lookup — preferred
        if port is not None:
            mapping = db.execute(
                select(PortMappingRecord)
                .where(PortMappingRecord.port == port)
                .order_by(PortMappingRecord.created_at.desc())
            ).scalars().first()
            if mapping:
                return mapping.sandbox_session_id

        # 2. Fallback — most-recent session
        query = (
            select(SessionRecord)
            .where(
                SessionRecord.status.in_([
                    TaskStatus.RUNNING.value,
                    TaskStatus.COMPLETED.value,
                ])
            )
            .order_by(SessionRecord.created_at.desc())
        )
        if task_id:
            query = query.where(SessionRecord.task_id == task_id)
        session = db.execute(query).scalars().first()
        if not session:
            raise HTTPException(status_code=404, detail="No active sandbox session found")
        return session.sandbox_session_id


async def _proxy(port: int, path: str, request: Request) -> Response:
    """Forward the incoming request to the OpenSandbox proxy endpoint."""
    sandbox_id = _resolve_sandbox_session_id(
        port=port,
        task_id=request.query_params.get("task_id"),
    )

    # Build the upstream URL
    base = settings.opensandbox_base_url.rstrip("/")
    upstream_url = f"{base}/sandboxes/{sandbox_id}/proxy/{port}"
    if path:
        upstream_url += f"/{path}"

    # Forward query params (minus our own helpers)
    params = dict(request.query_params)
    params.pop("task_id", None)
    params.pop("token", None)

    # Forward body for non-GET methods
    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

    # Forward a subset of headers (avoid hop-by-hop headers)
    forward_headers = {}
    for key in ("content-type", "accept", "authorization", "cookie", "user-agent"):
        if key in request.headers:
            forward_headers[key] = request.headers[key]

    try:
        upstream_resp = await _client.request(
            method=request.method,
            url=upstream_url,
            params=params or None,
            content=body,
            headers=forward_headers,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(
            status_code=502,
            detail=f"Cannot reach sandbox service on port {port}. "
                   "The sandbox may have expired or the server is not running. "
                   "Please create a new task to restart the application.",
        )

    # OpenSandbox returns JSON errors when the sandbox container is gone.
    # Detect those and return a friendly message instead of the raw error.
    if upstream_resp.status_code >= 400:
        ct = upstream_resp.headers.get("content-type", "")
        if "json" in ct:
            try:
                body_json = upstream_resp.json()
                msg = body_json.get("message", "") or body_json.get("detail", "")
                if "connect" in msg.lower() or "sandbox" in msg.lower() or "not found" in msg.lower():
                    raise HTTPException(
                        status_code=502,
                        detail=f"The sandbox for port {port} is no longer available. "
                               "It may have expired after the 30-minute timeout. "
                               "Please create a new task to restart the application.",
                    )
            except HTTPException:
                raise
            except Exception:
                pass  # Fall through to normal response passthrough

    # Build response — pass through status, headers, and body
    excluded_headers = {"transfer-encoding", "content-encoding", "content-length"}
    resp_headers = {
        k: v for k, v in upstream_resp.headers.items()
        if k.lower() not in excluded_headers
    }

    content = upstream_resp.content
    content_type = upstream_resp.headers.get("content-type", "")

    # Rewrite <base href="/"> in HTML so relative asset paths resolve
    # through the preview proxy prefix instead of the site root.
    if "html" in content_type:
        preview_prefix = f"{settings.api_prefix}/preview/{port}/".encode()
        content = _BASE_HREF_RE.sub(
            rb"\g<1>" + preview_prefix + rb"\3",
            content,
        )

    return Response(
        content=content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        media_type=content_type or None,
    )


# ── Route definitions ─────────────────────────────────


@router.get("/{port}")
async def preview_root(port: int, request: Request, _user: UserRecord = Depends(get_preview_user)) -> Response:
    return await _proxy(port, "", request)


@router.get("/{port}/{full_path:path}")
async def preview_path_get(port: int, full_path: str, request: Request, _user: UserRecord = Depends(get_preview_user)) -> Response:
    return await _proxy(port, full_path, request)


@router.post("/{port}/{full_path:path}")
async def preview_path_post(port: int, full_path: str, request: Request, _user: UserRecord = Depends(get_preview_user)) -> Response:
    return await _proxy(port, full_path, request)


@router.put("/{port}/{full_path:path}")
async def preview_path_put(port: int, full_path: str, request: Request, _user: UserRecord = Depends(get_preview_user)) -> Response:
    return await _proxy(port, full_path, request)


@router.patch("/{port}/{full_path:path}")
async def preview_path_patch(port: int, full_path: str, request: Request, _user: UserRecord = Depends(get_preview_user)) -> Response:
    return await _proxy(port, full_path, request)


@router.delete("/{port}/{full_path:path}")
async def preview_path_delete(port: int, full_path: str, request: Request, _user: UserRecord = Depends(get_preview_user)) -> Response:
    return await _proxy(port, full_path, request)
