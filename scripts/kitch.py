#!/usr/bin/env python3
"""Cross-platform terminal setup and development runner for Kitch."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / "venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def fail(message: str) -> None:
    raise SystemExit(f"Kitch: {message}")


def require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        fail(f"{name} is required but was not found on PATH.")
    return path


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def setup() -> None:
    if sys.version_info < (3, 12):
        fail("Python 3.12 or newer is required.")
    npm = require_program("npm")
    require_program("node")
    if not VENV_PYTHON.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    run([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt"], BACKEND)
    run([npm, "install"], FRONTEND)
    env_file = BACKEND / ".env.local"
    if not env_file.exists():
        print("\nNext: copy backend/.env.local.example to backend/.env.local")
        print("and replace GOOGLE_API_KEY with your Gemini API key.")
    else:
        print("\nDependencies are ready. Run: python scripts/kitch.py start")


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_for_http(
    process: subprocess.Popen,
    url: str,
    label: str,
    timeout: float = 45.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            fail(f"the {label} exited before becoming ready.")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.4)
    fail(f"the {label} did not become ready within {int(timeout)} seconds.")


def child_process_options() -> dict[str, object]:
    """Keep each server and its descendants in one stoppable process group."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def stop_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except ProcessLookupError:
        return


def start() -> None:
    npm = require_program("npm")
    if not VENV_PYTHON.exists():
        fail("dependencies are not installed. Run: python scripts/kitch.py setup")
    env_file = BACKEND / ".env.local"
    values = read_env_file(env_file)
    key = values.get("GOOGLE_API_KEY", "")
    if not key or "replace-with" in key or "your-" in key:
        fail("set GOOGLE_API_KEY in backend/.env.local before starting Kitch.")
    for port in (8000, 3000):
        if not port_available(port):
            fail(f"port {port} is already in use.")

    # Explicit shell/deployment variables take precedence over the convenience
    # local env file, matching normal twelve-factor configuration behavior.
    environment = {**values, **os.environ}
    environment["NEXT_PUBLIC_API_BASE_URL"] = "http://localhost:8000"
    # Polling avoids native watcher exhaustion on macOS and container hosts
    # with restrictive kqueue/inotify limits. It affects local development only.
    environment.setdefault("WATCHPACK_POLLING", "true")
    backend = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND,
        env=environment,
        **child_process_options(),
    )
    frontend = None
    try:
        wait_for_http(
            backend,
            "http://localhost:8000/api/health/live",
            "backend",
        )
        frontend = subprocess.Popen(
            [npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000"],
            cwd=FRONTEND,
            env=environment,
            **child_process_options(),
        )
        wait_for_http(frontend, "http://localhost:3000", "frontend")
        print("\nKitch is running at http://localhost:3000")
        print("Press Ctrl+C to stop both servers.\n")
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(0.5)
        fail("one of the local Kitch servers stopped unexpectedly.")
    except KeyboardInterrupt:
        print("\nStopping Kitch…")
    finally:
        for process in (frontend, backend):
            if process is not None:
                stop_process_tree(process)
        for process in (frontend, backend):
            if process is not None:
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up and run Kitch locally.")
    parser.add_argument("command", choices=("setup", "start"))
    args = parser.parse_args()
    {"setup": setup, "start": start}[args.command]()


if __name__ == "__main__":
    main()
