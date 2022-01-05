PYTHON_MAJOR_MINOR=$1
export PATH=$HOME/.local/bin:$PATH
rm -rf .venv
./python.sh $PYTHON_MAJOR_MINOR
echo "exit()" | sh venv
./venv pip install poetry python$PYTHON_MAJOR_MINOR
./venv make init
./venv make check
# Publish if there is tag on the current commit
set +x
git tag -l --points-at $(git show -q --format=%H) | grep v && ./venv poetry config http-basic.pypi __token__ $(cat ~/.pypi-token) || true
set -x
git tag -l --points-at $(git show -q --format=%H) | grep v && ./venv poetry build || true
git tag -l --points-at $(git show -q --format=%H) | grep v && ./venv poetry publish || true
