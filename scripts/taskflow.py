#!/usr/bin/env python3
"""TaskFlow developer tooling: reproduce the CI quality gates locally.

Usage: python scripts/taskflow.py <command>

  prerequisites  check required tools (python, docker)
  test           run the pytest suites of every microservice (+ frontend if possible)
  lint           run Ruff (lint + format check) on every microservice (+ frontend ESLint/Prettier)
  verify         policy, test then lint, stops at the first failure (exit code 1) -- same gates as CI
  supply-chain-policy
                 fail on a remote GitHub action not pinned to a full commit SHA, or on a
                 FROM / third-party image without a sha256 digest
  images         build every Docker image (docker compose build)
  up / down      start / stop the full stack
  smoke          end-to-end scenario through the API gateway (stack must be running)
  load [N] [C]   N requests (default 200), C at a time (default 20), through the gateway
                 to WorkspaceService and TaskService; prints the HTTP status counts
                 (traffic for Kiali, circuit breaker and fault injection demos)

Python checks use the current interpreter (activate the virtualenv first).
Frontend checks run inside a node:24 container, so no local Node.js is required.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ["user-service", "workspace-service", "task-service", "analytics-service"]
FRONTEND = ROOT / "frontend"
NODE_IMAGE = "node:24-alpine"
NODE_MODULES_VOLUME = "taskflow-frontend-node-modules"
GATEWAY = "http://localhost:8080"


class CheckFailed(Exception):
    pass


def run(title: str, cmd: list[str], cwd: Path = ROOT) -> None:
    print(f"\n==> {title}\n    $ {' '.join(cmd)}", flush=True)
    if subprocess.run(cmd, check=False, cwd=cwd).returncode != 0:
        raise CheckFailed(title)


def docker_available() -> bool:
    return shutil.which("docker") is not None and (
        subprocess.run(["docker", "info"], check=False, capture_output=True).returncode == 0
    )


def node(title: str, script: str) -> None:
    """Run an npm command for the frontend inside a Node 24 container."""
    run(
        title,
        [
            "docker", "run", "--rm",
            "-v", f"{FRONTEND}:/work",
            "-v", f"{NODE_MODULES_VOLUME}:/work/node_modules",
            "-w", "/work",
            "-e", "NG_CLI_ANALYTICS=false",
            NODE_IMAGE, "sh", "-c", f"npm ci --no-audit --no-fund --silent && {script}",
        ],
    )  # fmt: skip


# ---------------------------------------------------------------- commands
def cmd_prerequisites() -> None:
    print(f"python  : {sys.version.split()[0]}")
    for tool in ("docker", "git"):
        print(f"{tool:8}: {'ok' if shutil.which(tool) else 'MISSING'}")
    print(f"docker daemon: {'running' if docker_available() else 'NOT RUNNING'}")


def cmd_test() -> None:
    for service in SERVICES:
        run(f"Python tests ({service})", [sys.executable, "-m", "pytest", "-q"], ROOT / "services" / service)
    if docker_available():
        node("Frontend tests", "npx ng test --watch=false")
    else:
        print("\n(!) Docker not running: frontend tests skipped")


def cmd_lint() -> None:
    for service in SERVICES:
        cwd = ROOT / "services" / service
        run(f"Python quality ({service}) - ruff check", [sys.executable, "-m", "ruff", "check", "."], cwd)
        run(f"Python quality ({service}) - ruff format", [sys.executable, "-m", "ruff", "format", "--check", "."], cwd)
    if docker_available():
        node("Frontend quality", "npx ng lint && npm run format:check")
    else:
        print("\n(!) Docker not running: frontend quality skipped")


# ---------------------------------------------------------------- supply chain
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^\s'\"#]+)")
FROM = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
IMAGE = re.compile(r"^\s*(?:-\s*)?image:\s*['\"]?([^\s'\"#]+)")
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
LOCAL_IMAGES = ("taskflow/",)  # built from this repository, deployed by tag


def policy_violations() -> list[str]:
    """Mutable references that let someone swap what CI runs or what images contain."""
    problems: list[str] = []

    def where(path: Path, number: int) -> str:
        return f"{path.relative_to(ROOT).as_posix()}:{number}"

    for path in sorted((ROOT / ".github").rglob("*.y*ml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = USES.match(line)
            if not match or match[1].startswith("./"):
                continue
            ref = match[1]
            if ref.startswith("docker://"):
                if not DIGEST.search(ref):
                    problems.append(f"{where(path, number)}: {ref} has no sha256 digest")
            elif not SHA.match(ref.rpartition("@")[2]):
                problems.append(f"{where(path, number)}: {ref} is not pinned to a full commit SHA")

    dockerfiles = [p for p in ROOT.rglob("Dockerfile*") if "node_modules" not in p.parts]
    for path in sorted(dockerfiles):
        stages: set[str] = set()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = FROM.match(line)
            if not match:
                continue
            image, stage = match[1], match[2]
            if image.lower() not in stages and image != "scratch" and not DIGEST.search(image):
                problems.append(f"{where(path, number)}: FROM {image} has no sha256 digest")
            if stage:
                stages.add(stage.lower())

    manifests = [ROOT / "docker-compose.yml", *sorted((ROOT / "k8s").rglob("*.yaml"))]
    for path in manifests:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = IMAGE.match(line)
            if match and not match[1].startswith(LOCAL_IMAGES) and not DIGEST.search(match[1]):
                problems.append(f"{where(path, number)}: image {match[1]} has no sha256 digest")
    return problems


def cmd_supply_chain_policy() -> None:
    print("\n==> Supply chain policy (pinned actions and image digests)")
    problems = policy_violations()
    for problem in problems:
        print(f"  [KO] {problem}")
    if problems:
        raise CheckFailed(f"supply-chain-policy: {len(problems)} mutable reference(s)")
    print("  [OK] every remote action is pinned to a commit SHA, every image to a digest")


def cmd_verify() -> None:
    cmd_supply_chain_policy()
    cmd_test()
    cmd_lint()
    print("\nAll quality gates passed.")


def cmd_images() -> None:
    run("Docker images", ["docker", "compose", "build"])
    subprocess.run(["docker", "image", "ls", "taskflow/*"], check=False)


def cmd_up() -> None:
    run("Start stack", ["docker", "compose", "up", "-d", "--build", "--wait"])
    print(f"\nTaskFlow is available on {GATEWAY}  (RabbitMQ UI: http://localhost:15672)")


def cmd_down() -> None:
    run("Stop stack", ["docker", "compose", "down"])


# ---------------------------------------------------------------- smoke test
def api(method: str, path: str, body: dict | None = None, token: str | None = None):
    request = urllib.request.Request(
        GATEWAY + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} | ({"Authorization": f"Bearer {token}"} if token else {}),
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            is_json = "json" in response.headers.get("Content-Type", "")
            return response.status, (json.loads(raw) if raw and is_json else raw.decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def expect(label: str, condition: bool, detail: object = "") -> None:
    print(f"  [{'OK' if condition else 'KO'}] {label}")
    if not condition:
        raise CheckFailed(f"smoke: {label} {detail}")


def eventually(fetch, predicate, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        if predicate(value) or time.monotonic() > deadline:
            return value
        time.sleep(0.5)


def cmd_smoke() -> None:
    suffix = uuid.uuid4().hex[:8]
    alice, bob = f"alice-{suffix}@example.com", f"bob-{suffix}@example.com"
    print(f"Smoke test against {GATEWAY}")

    status, _ = api("GET", "/gateway/health")
    expect("gateway is up", status == 200)

    for email, name in ((alice, "Alice"), (bob, "Bob")):
        status, _ = api("POST", "/api/auth/register", {"email": email, "full_name": name, "password": "secret123"})
        expect(f"UserService registers {name}", status == 201, status)
    _, login = api("POST", "/api/auth/login", {"email": alice, "password": "secret123"})
    token = login["access_token"]
    expect("UserService issues a JWT", bool(token))

    status, workspace = api("POST", "/api/workspaces", {"name": "Smoke", "description": ""}, token)
    expect("WorkspaceService creates a workspace", status == 201, workspace)
    wid = workspace["id"]

    status, member = api("POST", f"/api/workspaces/{wid}/members", {"email": bob}, token)
    expect("WorkspaceService -> UserService (REST): member resolved by email", status == 201, member)

    status, task = api(
        "POST", "/api/tasks",
        {"workspace_id": wid, "title": "Smoke task", "assignee_id": member["user_id"], "priority": "high"},
        token,
    )  # fmt: skip
    expect("TaskService -> WorkspaceService (REST): membership checked", status == 201, task)
    status, task = api("PATCH", f"/api/tasks/{task['id']}", {"status": "done"}, token)
    expect("TaskService updates status", status == 200 and task["completed_at"] is not None, task)

    stats = eventually(
        lambda: api("GET", f"/api/analytics/workspaces/{wid}", token=token)[1],
        lambda s: isinstance(s, dict) and s.get("by_status", {}).get("done") == 1,
    )
    expect("AnalyticsService consumed task events (RabbitMQ)", stats["by_status"]["done"] == 1, stats)

    status, _ = api("DELETE", f"/api/workspaces/{wid}", token=token)
    expect("WorkspaceService deletes the workspace", status == 204)
    remaining = eventually(lambda: api("GET", "/api/tasks/mine", token=token)[1], lambda tasks: tasks == [])
    expect("TaskService purged tasks on workspace.deleted (RabbitMQ)", remaining == [], remaining)

    status, html = api("GET", "/workspaces")
    expect("Gateway serves the Angular frontend (SPA fallback)", status == 200 and "<app-root" in html)
    print("\nSmoke test passed.")


# ---------------------------------------------------------------- load test
def status_of(method: str, path: str, token: str) -> int:
    """HTTP status only; Envoy error bodies (circuit breaker, faults) are plain text."""
    request = urllib.request.Request(GATEWAY + path, method=method, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError):
        return 0


def cmd_load(total: int = 200, concurrency: int = 20) -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"load-{suffix}@example.com"
    print(f"Load test against {GATEWAY}: {total} requests, {concurrency} concurrent")
    status, _ = api("POST", "/api/auth/register", {"email": email, "full_name": "Load", "password": "secret123"})
    expect("UserService registers the load user", status == 201, status)
    _, login = api("POST", "/api/auth/login", {"email": email, "password": "secret123"})
    token = login["access_token"]
    status, workspace = api("POST", "/api/workspaces", {"name": f"Load {suffix}", "description": ""}, token)
    expect("WorkspaceService creates the load workspace", status == 201, workspace)
    wid = workspace["id"]

    # Even requests hit WorkspaceService; odd ones go TaskService -> WorkspaceService.
    paths = [f"/api/workspaces/{wid}" if i % 2 == 0 else f"/api/tasks?workspace_id={wid}" for i in range(total)]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        codes = Counter(pool.map(lambda path: status_of("GET", path, token), paths))
    elapsed = time.monotonic() - started

    print(f"\n{total} requests in {elapsed:.1f}s")
    for code, count in sorted(codes.items()):
        label = "no response" if code == 0 else str(code)
        print(f"  {label:>11}: {count}")
    api("DELETE", f"/api/workspaces/{wid}", token=token)


COMMANDS = {
    "prerequisites": cmd_prerequisites,
    "test": cmd_test,
    "lint": cmd_lint,
    "verify": cmd_verify,
    "images": cmd_images,
    "up": cmd_up,
    "down": cmd_down,
    "smoke": cmd_smoke,
    "load": cmd_load,
    "supply-chain-policy": cmd_supply_chain_policy,
}


def main() -> int:
    command, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if command not in COMMANDS or (args and command != "load") or len(args) > 2 or not all(a.isdigit() for a in args):
        print(__doc__)
        return 2
    try:
        COMMANDS[command](*(int(a) for a in args))
    except CheckFailed as failure:
        print(f"\nFAILED: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
