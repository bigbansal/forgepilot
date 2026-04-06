import sys
sys.path.insert(0, '/app/src')
from manch_backend.services.sandbox import OpenSandboxAdapter
from manch_backend.config import settings
import base64

key = settings.openai_api_key
print("Key prefix:", key[:10])
sandbox = OpenSandboxAdapter()
sid = sandbox.create_session()

py_code = r"""
import socket, ssl, base64, os

key = os.environ.get('OPENAI_API_KEY', '')
print('key_len:', len(key))

def wss_test(include_deflate):
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
            'Authorization: Bearer ' + key,
            'OpenAI-Beta: responses_websockets=2026-02-06',
        ]
        if include_deflate:
            headers.append('Sec-WebSocket-Extensions: permessage-deflate; client_no_context_takeover; server_no_context_takeover')
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
        label = 'WITH_DEFLATE' if include_deflate else 'WITHOUT_DEFLATE'
        print(label + ': ' + first_line)
        ss.close()
    except Exception as e:
        label = 'WITH_DEFLATE' if include_deflate else 'WITHOUT_DEFLATE'
        print('Exception (' + label + '):', e)

wss_test(False)
wss_test(True)
"""

b64 = base64.b64encode(py_code.encode()).decode()
sandbox.run_command(sid, "echo '" + b64 + "' | base64 -d > /tmp/wss_deflate_test.py", keep_alive=True)
result = sandbox.run_command(sid, "OPENAI_API_KEY=" + key + " python3 /tmp/wss_deflate_test.py", keep_alive=False)
print("STDOUT:", result.stdout or "(empty)")
print("STDERR:", (result.stderr or "")[:200])
