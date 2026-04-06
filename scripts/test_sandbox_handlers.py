"""Test ExecutionHandlersSync to capture command output."""
from opensandbox import SandboxSync
from opensandbox.config.connection_sync import ConnectionConfigSync
from opensandbox.models.execd_sync import ExecutionHandlersSync
from opensandbox.models.execd import RunCommandOpts
from datetime import timedelta
import inspect

# Inspect ExecutionHandlersSync
print("=== ExecutionHandlersSync ===")
print(inspect.signature(ExecutionHandlersSync.__init__))
for attr in ["model_fields", "__fields__", "__annotations__"]:
    val = getattr(ExecutionHandlersSync, attr, None)
    if val:
        print(f"  .{attr}: {val}")
        break

# Inspect RunCommandOpts
print("\n=== RunCommandOpts ===")
for attr in ["model_fields", "__fields__", "__annotations__"]:
    val = getattr(RunCommandOpts, attr, None)
    if val:
        print(f"  .{attr}: {val}")
        break

cc = ConnectionConfigSync(
    domain="opensandbox:8080",
    protocol="http",
    request_timeout=timedelta(seconds=30),
    use_server_proxy=True,
)

print("\nCreating sandbox...")
s = SandboxSync.create(
    image="manch/sandbox-runtime:local",
    entrypoint=["tail", "-f", "/dev/null"],
    timeout=timedelta(seconds=60),
    ready_timeout=timedelta(seconds=60),
    connection_config=cc,
)
print(f"Sandbox ID: {s.id}")

try:
    output_lines = []

    def on_stdout(data):
        print(f"  [stdout] {data!r}")
        output_lines.append(data)

    def on_stderr(data):
        print(f"  [stderr] {data!r}")

    def on_exit(code):
        print(f"  [exit] {code}")

    handlers = ExecutionHandlersSync(
        on_stdout=on_stdout,
        on_stderr=on_stderr,
        on_exit=on_exit,
    )

    print("\nRunning: echo hello world (with handlers)")
    result = s.commands.run("echo hello world", handlers=handlers)
    print(f"  result: {result}")
    print(f"  id    : {result.id}")
    print(f"  result.result: {result.result}")
    print(f"  error : {result.error}")
    print(f"  captured lines: {output_lines}")

finally:
    print("\nKilling sandbox...")
    s.kill()
    s.close()
    print("Done.")
