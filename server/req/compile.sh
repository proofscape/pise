#!/usr/bin/env sh

# Run this script any time you update any of the *.in files.

pip-compile --generate-hashes requirements.in
# We're saying `--no-annotate` on the files that have `-c` constraints
# in them, since it seems pip-compile has begun to put *absolute* filesystem
# paths for the constraint files so named, in its annotations. I don't want
# the annotations to contain traces of the development machine where the
# work happened to be done.
pip-compile --generate-hashes --no-annotate test-requirements.in
pip-compile --generate-hashes --no-annotate dev-requirements.in
