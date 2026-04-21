#!/usr/bin/env bash
# Entrypoint for the Claw Engine sandbox container.
# Runs a Python analysis script passed as the first argument.
set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Error: no analysis script provided." >&2
    echo "Usage: entrypoint.sh <script.py>" >&2
    exit 1
fi

exec python "$@"
