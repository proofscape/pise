from invoke import task


@task
def mtr(c, repo=''):
    """
    mtr = "make test repos"

    This generates the git repos under `lib/test`, that are used in the unit tests.

    Optionally, pass a repopath with or without the host segment, to generate just that
    one repo.

    Thus,

        $ inv mtr

    generates all test repos, while either of

        $ inv mtr --repo test.foo.bar
        $ inv mtr --repo foo.bar

    will generate just the test.foo.bar repo.

    I'm setting `pty=True` in this and other commands, because I want to recover
    the familiar behavior where we see the generated output *as the process works*,
    rather than having it all be buffered and suddenly dumped at the end.

    See:
        https://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
    """
    if repo.startswith('test.'):
        repo = repo[5:]
    c.run(f"python -m tests.util.make_repos {repo}", pty=True)


@task
def btr(c):
    """
    btr = "build test repos"

    After you have used the `mtr` command to generate the git repos under `lib/test`,
    this command builds each of them, as a Proofscape repo, generating output under
    the `build` dir.

    You have to run this before you can run the server's unit tests.
    But this step should be regarded as more than just a prerequisite for unit testing;
    it is, in itself, the first major test, because it carries out the entire build
    process on several Proofscape repos. If you are doing development work on the build
    system, you can expect the `btr` command to flush out many issues.
    """
    c.run("python -m tests.util.build_repos", pty=True)


@task
def unit(c):
    """
    Run the unit tests.

    You have to run `mtr` and `btr` (in that order) before you can run the unit tests.
    But those commands only have to be run once, unless the test repos are changed.
    """
    c.run("pytest tests", pty=True)
