#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv sync --frozen --group dev --group binary
uv run python scripts/build_binary.py "$@"
uv run python scripts/verify_binary.py
