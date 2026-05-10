#!/usr/bin/env bash
#
# Render a stack template to a destination directory for inspection.
#
# Usage:
#   ./scripts/render-stack.sh <stack-dir> <dest-dir> <appName> [<description>]
#
# Useful for testing templates without invoking the full agent. Walks
# <stack-dir> recursively, treats every ``*.j2`` file as a Jinja2 template
# rendered with the ``appName``/``description`` variables, and copies all
# other files verbatim. The output mirrors the input tree under <dest-dir>.
#
# Variables passed to Jinja2:
#   appName       — the app name (DNS label).
#   description   — free-text description (optional, defaults to "").
#
# Exit codes:
#   0  Success.
#   2  Usage error.
#   3  Pre-flight failure (missing python3 / jinja2 / source dir).

set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
    cat >&2 <<'EOF'
Usage: render-stack.sh <stack-dir> <dest-dir> <appName> [<description>]

Examples:
  ./scripts/render-stack.sh cnoe-stacks/nodejs-template /tmp/out demo-app
  ./scripts/render-stack.sh cnoe-stacks/nodejs-template /tmp/out demo-app "demo description"
EOF
    exit 2
fi

STACK_DIR="$1"
DEST_DIR="$2"
APP_NAME="$3"
DESCRIPTION="${4:-}"

if [[ ! -d "$STACK_DIR" ]]; then
    echo "ERROR: <stack-dir> not found or not a directory: $STACK_DIR" >&2
    exit 3
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required but not on PATH." >&2
    exit 3
fi

mkdir -p "$DEST_DIR"

STACK_DIR_ABS="$(cd "$STACK_DIR" && pwd)"
DEST_DIR_ABS="$(cd "$DEST_DIR" && pwd)"

export STACK_DIR_ABS DEST_DIR_ABS APP_NAME DESCRIPTION

python3 - <<'PY'
import os
import sys
from pathlib import Path

try:
    from jinja2 import Environment, StrictUndefined
except ImportError:
    print("ERROR: jinja2 not installed. Install with: pip install jinja2", file=sys.stderr)
    sys.exit(3)

stack = Path(os.environ["STACK_DIR_ABS"])
dest = Path(os.environ["DEST_DIR_ABS"])
app_name = os.environ["APP_NAME"]
context = {
    "appName": app_name,
    "description": os.environ.get("DESCRIPTION", ""),
    "namespace": app_name,
    "host": f"{app_name}.cnoe.localtest.me",
    "replicas": 2,
    # ``app.yaml`` references the GitOps repo URL; supply a placeholder so
    # rendering succeeds in inspection mode.
    "gitopsRepoUrl": f"https://github.com/example/{app_name}-gitops.git",
    "image": "ghcr.io/cnoe-io/nodejs-hello:latest",
}

env = Environment(
    keep_trailing_newline=True,
    autoescape=False,
    undefined=StrictUndefined,
)

count = 0
for src_path in sorted(stack.rglob("*")):
    if src_path.is_dir():
        continue
    rel = src_path.relative_to(stack)
    out_path = dest / rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = src_path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        out_path.write_bytes(raw)
    else:
        try:
            out_path.write_text(env.from_string(text).render(**context))
        except Exception as exc:
            print(f"ERROR: rendering {rel}: {exc}", file=sys.stderr)
            sys.exit(3)
    count += 1

print(f"Rendered {count} files from {stack} into {dest}")
PY
