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

for i in $(seq 1 "$ITERATIONS"); do
    echo "=== Iteration $i / $ITERATIONS ==="

    echo "--- Scripted tests ---"
    python "$TESTER" --test-name scripted found

    echo "--- API tests (comparison with python) ---"
    python "$TESTER" --num-ops 1000 --api-version 730 --test-name api --compare python found

    echo "--- API tests (concurrency 5) ---"
    python "$TESTER" --num-ops 1000 --api-version 730 --test-name api --concurrency 5 found

    echo "=== Iteration $i complete ==="
done

echo "All $ITERATIONS iterations passed."
