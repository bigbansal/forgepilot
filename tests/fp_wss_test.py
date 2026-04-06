import sys
sys.path.insert(0, '/app/src')
from manch_backend.services.sandbox import OpenSandboxAdapter
from manch_backend.config import settings
import base64

key = settings.openai_api_key
print("Key prefix:", key[:10])
sandbox = OpenSandboxAdapter()
sid = sandbox.create_session()

# Test with the EXACT OpenAI-Beta header that codex-cli sends
py_code = r"""
import socket, ssl, base64, os

key = os.environ.get('OPENAI_API_KEY', '')
print('key_len:', len(key))

ctx = ssl.create_default_context()
try:
    s = socket.create_connection(('api.openai.com', 443), timeout=10)
    ss = ctx.wrap_socket(s, server_hostname='api.openai.com')
    wk = base64.b64encode(b'abcdefghijklmnop').decode()
    req = (
        'GET /v1/responses HTTP/1.1\r\n'
        'Host: api.openai.com\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        'Sec-WebSocket-Key: ' + wk + '\r\n'
        'Sec-WebSocket-Version: 13\r\n'
        'Authorization: Bearer ' + key + '\r\n'
        'OpenAI-Beta: responses_websockets=2026-02-06\r\n'
        '\r\n'
    )
    ss.sendall(req.encode())
    resp = b''
    while b'\r\n\r\n' not in resp:
        chunk = ss.recv(4096)
        if not chunk:
            break
        resp += chunk
    first_line = resp.decode('utf-8', errors='replace').split('\r\n')[0]
    print('WSS_WITH_BETA_HEADER:', first_line)
    ss.close()
except Exception as e:
    print('WSS_EXCEPTION:', e)
"""

b64 = base64.b64encode(py_code.encode()).decode()
write_cmd = f"echo '{b64}' | base64 -d > /tmp/wss_beta_test.py"
sandbox.run_command(sid, write_cmd, keep_alive=True)

result = sandbox.run_command(sid, f"OPENAI_API_KEY={key} python3 /tmp/wss_beta_test.py", keep_alive=False)
print("STDOUT:", result.stdout or "(empty)")
print("STDERR:", (result.stderr or "")[:200])
