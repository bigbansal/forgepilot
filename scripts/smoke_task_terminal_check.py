#!/usr/bin/env python3
import json
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError

BASE_URL = 'http://localhost:8080/api/v1'
TERMINAL_STATUSES = {'COMPLETED', 'FAILED', 'CANCELLED'}

# Dedicated smoke-test credentials (deterministic so it's idempotent)
SMOKE_EMAIL = 'smoke@forgepilot.dev'
SMOKE_PASSWORD = 'smoke_pw_12345'


def request_json(
    method: str,
    path: str,
    payload: dict | None = None,
    token: str | None = None,
) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'

    req = urllib.request.Request(f'{BASE_URL}{path}', data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def get_access_token() -> str:
    """Register smoke user (ignoring 409 conflict) then log in and return access token."""
    try:
        request_json('POST', '/auth/register', {
            'email': SMOKE_EMAIL,
            'password': SMOKE_PASSWORD,
            'full_name': 'Smoke Test',
        })
        print('smoke user registered')
    except HTTPError as exc:
        if exc.code == 409:
            print('smoke user already exists — skipping registration')
        else:
            raise

    tokens = request_json('POST', '/auth/login', {
        'email': SMOKE_EMAIL,
        'password': SMOKE_PASSWORD,
    })
    token: str = tokens['access_token']
    print(f'authenticated as {SMOKE_EMAIL}')
    return token


def main() -> int:
    prompt = 'Run a quick smoke command'
    max_wait_seconds = 220
    poll_interval_seconds = 5

    try:
        token = get_access_token()

        conversation = request_json('POST', '/conversations', {'title': 'Smoke Terminal Check'}, token=token)
        conversation_id = conversation['id']

        send = request_json(
            'POST',
            f'/conversations/{conversation_id}/messages',
            {'content': prompt, 'runner': 'opensandbox'},
            token=token,
        )
        task_id = send['task']['id']

        print(f'conversation_id={conversation_id}')
        print(f'task_id={task_id}')

        polls = max_wait_seconds // poll_interval_seconds
        for index in range(1, polls + 1):
            task = request_json('GET', f'/tasks/{task_id}', token=token)
            status = task.get('status', 'UNKNOWN')
            print(f'poll={index} status={status}')

            if status in TERMINAL_STATUSES:
                conversation_now = request_json('GET', f'/conversations/{conversation_id}', token=token)
                assistant_messages = [
                    message
                    for message in conversation_now.get('messages', [])
                    if message.get('role') == 'assistant'
                ]

                print(f'terminal_status={status}')
                print(f'assistant_message_count={len(assistant_messages)}')

                if status == 'FAILED' and not assistant_messages:
                    print('ERROR: FAILED task has no persisted assistant message')
                    return 2

                return 0

            time.sleep(poll_interval_seconds)

        print('ERROR: task did not reach terminal status within timeout')
        return 3

    except HTTPError as exc:
        print(f'HTTP error: {exc.code} {exc.reason}')
        return 10
    except URLError as exc:
        print(f'Connection error: {exc.reason}')
        return 11
    except Exception as exc:  # noqa: BLE001
        print(f'Unexpected error: {exc}')
        return 12


if __name__ == '__main__':
    sys.exit(main())
