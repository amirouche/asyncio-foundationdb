#!/bin/sh

set -xe

# Inspired from the great https://gitlab.com/python-devs/ci-images/
# Thanks Barry Warsaw.

# Needs:
# sudo apt-get update; sudo apt-get install make build-essential libssl-dev zlib1g-dev \
    # libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    # libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

PYTHON_VERSION_MAJOR_MINOR="$1"
PYTHON_VERSION=""

case $PYTHON_VERSION_MAJOR_MINOR in
    3.7) PYTHON_VERSION="3.7.12";;
    3.8) PYTHON_VERSION="3.8.12";;
    3.9) PYTHON_VERSION="3.9.9";;
    3.10) PYTHON_VERSION="3.10.1";;
esac

URL="https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz"

cd /tmp

wget -q $URL
tar -xzf Python-$PYTHON_VERSION.tgz
cd Python-$PYTHON_VERSION
./configure --prefix="$HOME/.local/"
make -j "$(nproc)"
make altinstall
rm -rf Python-$PYTHON_VERSION.tgz Python-$PYTHON_VERSION
