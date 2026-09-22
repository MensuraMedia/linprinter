#!/bin/bash
# run.sh - launch linprinter (system Python; dependencies are distro packages)
# Usage: ./run.sh [--test-printer] [--page preview] [--version]
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
exec python3 src/main.py "$@"
