# How to make a release

This project publishes several proudcts, including docker images, and an npm
package. It does not currently make use of the GitHub releases API.
This guide tells you how to make a release.

## Starting a release branch

Starting a release branch is a way of drawing a line, and saying that no
further commits to the `main` branch will make it into the next released
version. You can start the branch some time before you intend to publish,
and accept pull requests against it, for last-minute additions to the next
version.

Step 1. To begin with, you should be on the `main` branch.
Now make a release branch, of the form `releases/VERSION`. For example,
if releasing version `0.26.0`,

    $ git checkout -b releases/0.26.0

Step 2. Edit `client/package.json`, and remove the `-dev` tag on the version number.
Then do an `npm install` so the `package-lock.json` updates accordingly:

    $ cd client
    $ npm install

Commit these changes, and push:

    $ git add .
    $ git commit -m "Set release version"
    $ git push origin releases/0.26.0

Step 3. Go back to the `main` branch

    $ git checkout main

and bump the dev version number. For example, if the release branch is
`releases/0.26.0`, then

* Go into `client/package.json` and change the version to `0.27.0-dev`.
* In `CHANGELOG.md`, make an entry with heading `## 0.27.0 (------)`.

and again update `package-lock.json`:

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
* Ensure that `CHANGELOG.md` has a complete entry for the release you're about
  to make, except for the date.

Now set the date for the `CHANGELOG.md` entry, commit it with a simple
message stating the version number, and push.

    $ git add CHANGELOG.md
    $ git commit -m "Version 0.26.0"
    $ git push origin releases/0.26.0

Finally, add a tag, which must be of the form
`vMAJOR.MINOR.PATCH(-LABEL)` (`LABEL` part optional), and push the tag to
GitHub. For example,

    $ git tag v0.26.0
    $ git push origin v0.26.0

When you push the version tag you will trigger a workflow in GitHub Actions
which, if all tests pass, will result in publication of all products (docker
images, npm packages, etc.) However, this workflow will not run until it has
been approved by a project maintainer.
