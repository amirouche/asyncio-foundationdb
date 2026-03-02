#!/usr/bin/env bash
#
# run_bindingtester.sh — Run the FDB binding tester against `found`
#
# Usage: scripts/run_bindingtester.sh [iterations]
#
set -euo pipefail

ITERATIONS="${1:-1}"
FDB_DIR="fdb-source"
TESTER="$FDB_DIR/bindings/bindingtester/bindingtester.py"

if [ ! -f "$TESTER" ]; then
    echo "Error: $TESTER not found. Run scripts/setup_bindingtester.sh first."
    exit 1
fi

# Ensure the project root is on PYTHONPATH so subprocesses spawned by bindingtester
# (e.g. `python found/tester_pthread.py`) can import `found` via plain path lookup,
# bypassing the setuptools editable-install finder which breaks in deep subprocess chains.
export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$(pwd)"

for i in $(seq 1 "$ITERATIONS"); do
    echo "=== Iteration $i / $ITERATIONS ==="

    for TESTER_NAME in found found_aio; do
        echo "--- Scripted tests ($TESTER_NAME) ---"
        python "$TESTER" --test-name scripted "$TESTER_NAME"

        echo "--- API tests (comparison with python) ($TESTER_NAME) ---"
        python "$TESTER" --num-ops 1000 --api-version 730 --test-name api --compare python "$TESTER_NAME"

        echo "--- API tests (concurrency 5) ($TESTER_NAME) ---"
        python "$TESTER" --num-ops 1000 --api-version 730 --test-name api --concurrency 5 "$TESTER_NAME"
    done

    echo "=== Iteration $i complete ==="
done

echo "All $ITERATIONS iterations passed."
