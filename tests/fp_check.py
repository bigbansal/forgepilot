import sys
sys.path.insert(0, '/app/src')
from manch_backend.services.sandbox import OpenSandboxAdapter
sandbox = OpenSandboxAdapter()
sid = sandbox.create_session()

r1 = sandbox.run_command(sid, "echo PATH=$PATH", keep_alive=True)
print("PATH:", (r1.stdout or r1.stderr or "(none)").strip())

r2 = sandbox.run_command(sid, "echo ENV_KEYS=$(env | grep -c =)", keep_alive=True)
print("Env count:", (r2.stdout or r2.stderr or "(none)").strip())

# What does codex-cli see for bwrap
r3 = sandbox.run_command(sid, "PATH=/usr/local/bin:/usr/bin:/bin codex-cli --version 2>&1 | tail -3", keep_alive=False)
print("codex-cli with full PATH:", (r3.stdout or r3.stderr or "(none)").strip()[:300])
