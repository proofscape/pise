#!/usr/bin/env sh

# Execute from top level project directory.
# This is necessary since the *.local files use relative filesystem paths to
# point to sibling directories (which you are expected to have made available
# beside pfsc-server under PFSC_ROOT/src).

pip install --no-deps -r req/requirements.nodeps
pip install --no-deps -r req/requirements.txt
pip install -r req/requirements.local

pip install --no-deps -r req/test-requirements.txt
pip install -r req/test-requirements.hashless
