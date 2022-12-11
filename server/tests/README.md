# Running unit tests

Before you can run unit tests, you need to set up the testing framework.

## Deploy containers

For this you should be using the
[`pfsc-manage`](https://github.com/proofscape/pfsc-manage) project.
There, use the `pfsc deploy generate` command to generate a
testing deployment. Whichever graph database system (GDB) you select
for this deployment is the one against which all test repos will
be built, and unit tests run.

## Make, build, and index the test repos

From the `pfsc-server` project root:

    $ . venv/bin/activate
    (venv) $ python -m tests.util.make_repos
    (venv) $ python -m tests.util.build_repos

(The last step does both building and indexing.)

It's important to understand that the process of building and indexing
the test repos is, itself, a test. If you have been making changes to the
building and indexing code, this step might well fail. This will then entail
the first set of necessary repairs, before you can consider any other unit
tests.

## Run unit tests

From the `pfsc-server` project root:

    (venv) $ ./test_with_cov.sh

## Multiple GDBs

If you want to run tests against more than one GDB, you have to
repeat the entire process with a different deployment. (Except that
you do not have to rerun `tests.util.make_repos`.)
