#!/bin/sh
export PYVER="${PYVER:-3.4}"
export PYTHON="python${PYVER}"
#export LANG=en_US.UTF-8

set -xe
#rm -r -- ./build || :
"${PYTHON}" ./setup.py build

cd -P "${PWD}/build/lib.linux-x86_64-${PYVER}"

"${PYTHON}" -m kernelconfig.__main__ "${@}"
