set -xe
rm -rf .venv
PYTHON_MAJOR_MINOR=$1
echo "exit()" | sh venv python$PYTHON_MAJOR_MINOR
./venv pip install --quiet poetry
./venv make init
./venv make check
# Publish if there is a tag on the current commit
set +x
git tag -l --points-at $(git show -q --format=%H) | grep v && ./venv poetry config http-basic.pypi __token__ $(cat ~/.pypi-token) || true
set -x
git tag -l --points-at $(git show -q --format=%H) | grep v && ./venv poetry build --format wheel || true
git tag -l --points-at $(git show -q --format=%H) | grep v && ./venv poetry publish || true
