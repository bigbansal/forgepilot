"""Quick test of OpenSandbox commands.run() API."""
from opensandbox import SandboxSync
from opensandbox.config.connection_sync import ConnectionConfigSync
from datetime import timedelta

cc = ConnectionConfigSync(
    domain="opensandbox:8080",
    protocol="http",
    request_timeout=timedelta(seconds=30),
    use_server_proxy=True,
)

print("Creating sandbox...")
s = SandboxSync.create(
    image="manch/sandbox-runtime:local",
    entrypoint=["tail", "-f", "/dev/null"],
    timeout=timedelta(seconds=60),
    ready_timeout=timedelta(seconds=60),
    connection_config=cc,
)
print(f"Sandbox ID: {s.id}")

try:
    print("\nRunning: echo hello world")
    result = s.commands.run("echo hello world")
    print(f"  type  : {type(result)}")
    print(f"  id    : {result.id}")
    print(f"  result: {result.result}")
    print(f"  error : {result.error}")

    # Try to get text output
    for i, r in enumerate(result.result):
        print(f"  result[{i}] type={type(r)} value={r}")
        for attr in ["output", "text", "data", "stdout", "content", "value"]:
            if hasattr(r, attr):
                print(f"    .{attr} = {getattr(r, attr)}")
        if hasattr(r, "__dict__"):
            print(f"    __dict__ = {r.__dict__}")

    print("\nRunning: ls /")
    result2 = s.commands.run("ls /")
    print(f"  result: {result2.result}")
    print(f"  error : {result2.error}")
    for i, r in enumerate(result2.result):
        if hasattr(r, "__dict__"):
            print(f"  result[{i}].__dict__ = {r.__dict__}")

finally:
    print("\nKilling sandbox...")
    s.kill()
    s.close()
    print("Done.")
