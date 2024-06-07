# Contributing

Welcome! Thank you for your interest in contributing to this project.

If you have found a bug, or if you have a great idea for a new feature, please
start by searching open (and even closed) issues, to see if it has already been
noted. If you don't find what you're looking for, please go ahead and open
a new issue.

If there is an issue that you want to work on, it is usually best to have some
discussion before you begin coding. This way you can find out if someone is
already working on it, or if ideas about the issue have changed since the last
time it was discussed.


## Pull Requests

This project [keeps a changelog](https://keepachangelog.com/), which is meant
to record changes of interest to users of the software. Therefore, before opening
a PR, please follow the steps below.

1. Does your PR make any changes of interest to *users*? If the changes are of
   interest only to developers, then STOP. You don't need to record a news
   fragment.

2. Are you changing *again* something that has already been changed one or more
   times (by you or anyone else) in this release cycle? If so, then you probably
   need to edit an *existing* news fragment file in the `changelog.d` directory,
   and maybe even delete it, if none of its changes survives. But don't describe
   any *new* changes from your PR in this file.
   
   You *also* need to generate a *new* news fragment file, to describe new changes
   from your PR. Continue to Step 3.

3. If you've made it to this step, then you need to generate one or more
   news fragment files. You should generate one for each *category* to which
   your changes belong (i.e. improvements, bug fixes, etc.).

### Generating a news fragment file

1. Be at the root level of the repo, and make sure the Python virtual environment
   is installed and active. (The installation steps only need to be performed once.)

   ```
   $ python -m venv venv
   $ . venv/bin/activate
   (venv) $ pip install -U pip
   (venv) $ pip install -r requirements.txt
   ```

2. Use `branchnews` to generate a news fragment file.

   ```
   (venv) $ branchnews create
   ```
   
   * **If your PR is addressing a specific, numbered issue at GitHub:** Enter the issue
     number in response to the first prompt.
   * **Otherwise:** make a blank response to the first prompt, and instead enter your
     GitHub username at the second prompt.
   
   When you are asked to choose the *type* of news, you may find the following guidelines
   helpful:

   * **Breaking Changes:** Usually this means you're making it so that old
     Proofscape projects won't compile anymore.
   * **Improvements:** You improved things, or added new features, in a
     backwards-compatible way.
   * **Bug Fixes:** You fixed one or more bugs.
   * **deprecated:** An old feature has been deprecated.
   * **removed:** A deprecated feature has been removed.
   * **security:** Special category to highlight security-relevant fixes.

3. Edit the generated file, replacing the auto-generated contents with an entry 
   describing your changes. Tips:

   * The file will be found in the `changelog.d` directory.
   * You can use markdown. Please observe the rules:
     - If only declaring one change, do *not* use a bullet point.
     - If declaring multiple changes, then do use bullet points, but first put a
       title line (no bullet).
   * Use present tense. (E.g. "Repair context menus" not "Repaired context menus")
   * Try to keep the entry brief.
   * Remember that this is for human consumption, and intended more for *users* of the
     software, than for developers.

4. Commit the file to version control. A simple commit message like `Add news fragment` will do.


## Code of Conduct

Please note that all participants of this project are expected to follow the
Code of Conduct. By participating in this project you agree to abide by its
terms. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).


## Legal

Contributions are gladly accepted from their original author. By submitting
any copyrighted material via pull request, email, or other means, you agree to
license the material under the project’s open source license and warrant that
you have the legal authority to do so. See [LICENSE](LICENSE).
