"""End-to-end WebSocket streaming test for Manch runners."""
import asyncio
import json
import sys
import httpx
import websockets

BASE = "http://localhost:8080/api/v1"
WS_BASE = "ws://localhost:8080/api/v1"
EMAIL = "ws-test@manch.test"
PASSWORD = "TestPass123!"

async def get_token():
    async with httpx.AsyncClient() as c:
        # Try login first
        r = await c.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code == 200:
            return r.json()["access_token"]
        # Register
        r = await c.post(f"{BASE}/auth/register", json={"email": EMAIL, "password": PASSWORD, "full_name": "WS Test"})
        r.raise_for_status()
        return r.json()["access_token"]

async def test_runner(runner: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as c:
        # Create conversation
        r = await c.post(f"{BASE}/conversations", headers=headers, json={})
        r.raise_for_status()
        conv_id = r.json()["id"]

        # Send message (triggers task + background runner)
        r = await c.post(
            f"{BASE}/conversations/{conv_id}/messages",
            headers=headers,
            json={"content": "say the single word hello", "runner": runner},
        )
        r.raise_for_status()
        data = r.json()
        task_id = data.get("task", {}).get("id")
        print(f"  [{runner}] task_id={task_id}")

    if not task_id:
        print(f"  [{runner}] ERROR: no task_id found")
        return

    # Connect WebSocket and subscribe
    events = []
    try:
        async with websockets.connect(f"{WS_BASE}/events/ws?token={token}") as ws:
            await ws.send(json.dumps({"action": "subscribe", "task_id": task_id}))
            deadline = asyncio.get_event_loop().time() + 120  # 2 min timeout
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    ev = json.loads(raw)
                    etype = ev.get("type", "")
                    if etype == "heartbeat":
                        continue
                    events.append(etype)
                    payload = ev.get("payload", {})
                    print(f"  [{runner}] event={etype} payload_keys={list(payload.keys())[:5]}")
                    # Show output chunks
                    if "output" in payload:
                        print(f"  [{runner}] output={repr(payload['output'][:200])}")
                    if etype in ("task.completed", "task.failed", "task.error", "task_completed", "task_failed"):
                        break
                except asyncio.TimeoutError:
                    print(f"  [{runner}] waiting...")
    except Exception as e:
        print(f"  [{runner}] WS error: {e}")
        return

    if any(e in ("task_completed", "task.completed") for e in events):
        print(f"  [{runner}] PASSED")
    elif any(e in ("task_failed", "task.failed") for e in events):
        print(f"  [{runner}] task_failed")
    else:
        print(f"  [{runner}] FAIL no completion. Got: {events}")


async def main():
    print("Getting auth token...")
    token = await get_token()
    print(f"Token: {token[:20]}...\n")

    for runner in ["codex-cli", "gemini-cli", "claude-code"]:
        print(f"\n--- Testing {runner} ---")
        await test_runner(runner, token)

asyncio.run(main())
