"""Verify task.log SSE events are emitted during task execution."""
import json
import time
import urllib.request
import threading

base = "http://localhost:8080/api/v1"

events = []
stop = threading.Event()


def stream_events():
    try:
        r = urllib.request.urlopen(f"{base}/events/stream", timeout=90)
        for line in r:
            if stop.is_set():
                break
            line = line.decode("utf-8").strip()
            if line.startswith("data:"):
                try:
                    ev = json.loads(line[5:].strip())
                    events.append(ev)
                    if ev.get("type") in ("task.log", "task.completed", "task.failed", "task.running"):
                        text = ev.get("payload", {}).get("text", "")[:60]
                        print(f"  SSE {ev['type']}: {text!r}", flush=True)
                except Exception:
                    pass
    except Exception as e:
        print(f"SSE stream error: {e}", flush=True)


t = threading.Thread(target=stream_events, daemon=True)
t.start()
time.sleep(1)


def api(method, path, payload=None):
    data = json.dumps(payload).encode() if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


conv = api("POST", "/conversations", {"title": "SSE Log Test"})
send = api("POST", f'/conversations/{conv["id"]}/messages', {
    "content": "print 2+2 in python",
    "runner": "opensandbox",
})
tid = send["task"]["id"]
print(f"task_id={tid}", flush=True)

for i in range(14):
    time.sleep(5)
    log_count = sum(1 for e in events if e.get("type") == "task.log")
    done = any(e.get("type") in ("task.completed", "task.failed") for e in events)
    print(f"poll={i+1} total_events={len(events)} task_log_events={log_count} done={done}", flush=True)
    if done:
        break

stop.set()
print(f"\nAll event types: {sorted(set(e.get('type') for e in events))}", flush=True)
sample_logs = [e["payload"].get("text", "") for e in events if e.get("type") == "task.log"][:5]
print(f"Sample task.log texts: {sample_logs}", flush=True)
