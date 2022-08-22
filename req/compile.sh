#!/usr/bin/env sh

# Run this script any time you update any of the *.in files.

pip-compile --generate-hashes requirements.in
pip-compile --generate-hashes test-requirements.in
pip-compile --generate-hashes dev-requirements.in
