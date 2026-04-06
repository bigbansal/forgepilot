import sys
sys.path.insert(0, '/app/src')
from manch_backend.services.sandbox import OpenSandboxAdapter
from manch_backend.config import settings

key = settings.openai_api_key
print("Key prefix:", key[:10])
sandbox = OpenSandboxAdapter()
sid = sandbox.create_session()

# Run codex-cli with debug logging - just to see what URL it tries
cmd = ("RUST_LOG=tokio_tungstenite=debug,codex_api=debug "
       "codex-cli exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox "
       "-m gpt-4.1 'say hello'")
result = sandbox.run_command(sid, cmd, keep_alive=False)
print("STDOUT:", (result.stdout or "(empty)")[:500])
stderr = result.stderr or ""
# Look for interesting lines
for line in stderr.split('\n'):
    if any(x in line for x in ['wss', 'ws:', 'url', 'connect', 'websocket', 'header', 'ERROR', '500', '101']):
        print("LOG:", line[:200])
print("--- LAST 500 STDERR---")
print(stderr[-500:])
