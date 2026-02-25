#!/usr/bin/env bash
#
# setup_bindingtester.sh — Clone FDB source and register `found` as a tester
#
# Expected to be run via `poetry run` so that the virtualenv is active
# and `fdb` (foundationdb) is already installed as a project dependency.
#
set -euo pipefail

FDB_BRANCH="release-7.3"
FDB_DIR="fdb-source"

# Locate the pip-installed fdb package (has fdboptions.py that the source tree lacks)
FDB_SITE_DIR=$(python -c "import fdb, os; print(os.path.dirname(fdb.__file__))")
echo "Installed fdb package: $FDB_SITE_DIR"

# Clone FDB source if not already present
if [ ! -d "$FDB_DIR" ]; then
    echo "Cloning FoundationDB $FDB_BRANCH..."
    git clone --depth 1 --branch "$FDB_BRANCH" \
        https://github.com/apple/foundationdb.git "$FDB_DIR"
fi

# The bindingtester adds fdb-source/bindings/python to sys.path, which
# shadows the pip-installed fdb package.  That source-tree copy is missing
# fdboptions.py and apiversion constants, so we patch it.
FDB_SRC_PYTHON="$FDB_DIR/bindings/python/fdb"

# Copy fdboptions.py from the installed package
cp "$FDB_SITE_DIR/fdboptions.py" "$FDB_SRC_PYTHON/fdboptions.py"
echo "Copied fdboptions.py into source tree"

# Append API version constants that the source-tree apiversion.py lacks
if ! grep -q "LATEST_API_VERSION" "$FDB_SRC_PYTHON/apiversion.py" 2>/dev/null; then
    echo "LATEST_API_VERSION = 730" >> "$FDB_SRC_PYTHON/apiversion.py"
    echo "FDB_VERSION = '7.3.69'" >> "$FDB_SRC_PYTHON/apiversion.py"
    echo "Patched apiversion.py"
fi

# Fix Python 3.14+ compatibility: random.randint() no longer accepts float args
TEST_UTIL="$FDB_DIR/bindings/bindingtester/tests/test_util.py"
if grep -q '1e[0-9]' "$TEST_UTIL" 2>/dev/null; then
    sed -i 's/1e3/1000/g; s/1e8/10**8/g' "$TEST_UTIL"
    echo "Patched test_util.py (float literals in randint calls)"
fi

# Patch known_testers.py to register `found`
KNOWN_TESTERS="$FDB_DIR/bindings/bindingtester/known_testers.py"
if ! grep -q "'found'" "$KNOWN_TESTERS"; then
    echo "Registering 'found' testers..."
    cat >> "$KNOWN_TESTERS" <<'PYEOF'

# found — asyncio Python binding (POSIX threads variant)
testers['found'] = Tester('found', 'python found/tester_pthread.py', 2040, 23, 730, types=ALL_TYPES)
# found — asyncio Python binding (asyncio tasks variant)
testers['found_aio'] = Tester('found_aio', 'python found/tester_aio.py', 2040, 23, 730, types=ALL_TYPES)
PYEOF
fi

echo "Setup complete."
