import sys
sys.path.insert(0, '/app/src')
from manch_backend.services.sandbox import OpenSandboxAdapter

sandbox = OpenSandboxAdapter()
sid = sandbox.create_session()

# Check what env vars are available (especially OPENAI-related)
r = sandbox.run_command(sid, "env | grep -i 'openai\\|codex\\|api_key' | sort", keep_alive=False)
print("OPENAI env vars in sandbox:")
print(r.stdout or r.stderr or "(none)")
