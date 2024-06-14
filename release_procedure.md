# How to make a release

This project publishes several products, including docker images, and an npm
package. It does not currently make use of the GitHub releases API.
This guide tells you how to make a release.

## Starting a release branch

Starting a release branch is a way of drawing a line, and saying that no
further commits to the `main` branch will make it into the next released
version. You can start the branch some time before you intend to publish,
and accept pull requests against it, for last-minute additions to the next
version.

Step 1. To begin with, you should be on the `main` branch.
Now make and checkout a release branch, of the form `releases/VERSION`.
For example, if releasing version `0.26.0`,

    $ git checkout -b releases/0.26.0

Edit `client/package.json`, setting the version number, and 
then do an `npm install` so the `package-lock.json` updates accordingly:

    $ cd client
    $ npm install

Commit these changes, and push to remote:

    $ git add .
    $ git commit -m "Set release version"
    $ git push origin releases/0.26.0

Step 2. Go back to the `main` branch

    $ git checkout main

and bump the dev version number. For example, if the release branch is
`releases/0.26.0`, then go into `client/package.json` and change the version
to `0.27.0-dev`. Then once again update `package-lock.json`:

    $ cd client
    $ npm install

Finally, commit and push:

    $ git add .
    $ git commit -m "Bump dev version"
    $ git push origin main


## Publishing

When you are ready to publish, begin by checking the following items:

* You should be on the release branch.
* All the changes you want to make it into the release should be committed.
* Every change that merits an entry in the changelog should have a news fragment
  file in the `changelog.d` directory. (These should have been added along with
  each PR!)

Step 1. Use `branchnews` to rename news fragment files, and then commit the changes.

    (venv) $ branchnews rename
    (venv) $ git commit -m "Rename branchnews files"

Step 2. Use `towncrier` to build the changelog, commit the changes with
a message stating the version number, and push.

    (venv) $ towncrier build --version=v0.26.0
    (venv) $ git commit -m "Version 0.26.0"
    (venv) $ git push origin releases/0.26.0

Step 3. Pushing a version tag to GitHub (next step) will initiate a "pub prep"
test run, which carries out more tests than are ordinarily carried out for PRs.
In order to avoid having to move the tag in the event of unexpected errors, it
is good to do a manual run in full "pub prep" mode, before pushing the tag.

In order to do this, go to the Actions tab for the repo at GitHub, select
the `pise-build-and-test` workflow, and manually initiate a run. In the
"Run workflow" dropdown box, be sure to:

* Select the release branch
* Check the box to "Do extra steps in preparation for publication"
* Enter the correct version tag for the release
* Set debug level to 2

After the run completes, you can inspect the uploaded artifacts if you want.
In any case, delete them before proceeding.

Step 4. Add a tag, which must be of the form
`vMAJOR.MINOR.PATCH(-LABEL)` (`LABEL` part optional), and push the tag to
GitHub. For example,

    $ git tag v0.26.0
    $ git push origin v0.26.0

When you push the version tag you will trigger a workflow in GitHub Actions
that works toward publication. It begins with jobs that build and test all the
products. The actual publication job, however, will not run until it has been
approved by a project maintainer.

Step 5. Approve the publication job, and confirm availability of the published
products at Docker Hub and npm, after it completes.

Step 6. Return to the `main` branch, and merge the release branch.
Use the `--no-ff` switch here, for rare cases in which you may not have made
any changes on `main` (such as bumping the dev version, as described above).

    $ git checkout main
    $ git merge --no-ff releases/0.26.0

If you did bump the dev version on `main` as described above, then
there should be merge conflicts in the `package.json` and `package-lock.json`
files under the `client` dir, regarding the version number. We want to keep the
version from the `main` branch:

    $ git checkout --ours client/package*.json
    $ git add client/package*.json

Complete the merge, and finally push to `main` one more time.
