import sys
sys.path.insert(0, '/app/src')
from manch_backend.services.sandbox import OpenSandboxAdapter
from manch_backend.config import settings
import base64

key = settings.openai_api_key
print("Key prefix:", key[:10])
sandbox = OpenSandboxAdapter()
sid = sandbox.create_session()

# Test WSS WITHOUT auth header - see if we get 500 (same as codex-cli)
py_code = r"""
import socket, ssl, base64, os

key = os.environ.get('OPENAI_API_KEY', '')

def wss_test(include_auth, label):
    ctx = ssl.create_default_context()
    try:
        s = socket.create_connection(('api.openai.com', 443), timeout=10)
        ss = ctx.wrap_socket(s, server_hostname='api.openai.com')
        wk = base64.b64encode(b'abcdefghijklmnop').decode()
        headers = [
            'GET /v1/responses HTTP/1.1',
            'Host: api.openai.com',
            'Upgrade: websocket',
            'Connection: Upgrade',
            'Sec-WebSocket-Key: ' + wk,
            'Sec-WebSocket-Version: 13',
            'OpenAI-Beta: responses_websockets=2026-02-06',
        ]
        if include_auth:
            headers.append('Authorization: Bearer ' + key)
        req = '\r\n'.join(headers) + '\r\n\r\n'
        ss.sendall(req.encode())
        resp = b''
        for _ in range(100):
            chunk = ss.recv(4096)
            if not chunk:
                break
            resp += chunk
            if b'\r\n\r\n' in resp:
                break
        first_line = resp.decode('utf-8', errors='replace').split('\r\n')[0]
        print(label + ': ' + first_line)
        ss.close()
    except Exception as e:
        print('Exception (' + label + '):', e)

# Test REST POST without auth
import urllib.request, urllib.error, json
def rest_test(include_auth, label):
    data = json.dumps({'model': 'gpt-4.1', 'input': 'hi'}).encode()
    req = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    if include_auth:
        req.add_header('Authorization', 'Bearer ' + key)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(label + ': HTTP ' + str(r.status))
    except urllib.error.HTTPError as e:
        print(label + ': HTTP ' + str(e.code))

wss_test(True, 'WSS_WITH_AUTH')
wss_test(False, 'WSS_NO_AUTH')
rest_test(True, 'REST_WITH_AUTH')
rest_test(False, 'REST_NO_AUTH')
"""

b64 = base64.b64encode(py_code.encode()).decode()
sandbox.run_command(sid, "echo '" + b64 + "' | base64 -d > /tmp/auth_test.py", keep_alive=True)
result = sandbox.run_command(sid, "OPENAI_API_KEY=" + key + " python3 /tmp/auth_test.py", keep_alive=False)
print("STDOUT:", result.stdout or "(empty)")
print("STDERR:", (result.stderr or "")[:200])
