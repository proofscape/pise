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
to record changes of interest to users of the software. Therefore every PR
should include a *news fragment file* (see below), unless its changes are
of interest only to developers, not users.

To generate a news fragment file, follow the steps below.

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

   * **added:** improvements, new features
   * **changed:** breaking changes
   * **fixed:** bug fixes
   * **deprecated:** an old feature has been deprecated
   * **removed:** a deprecated feature has been removed
   * **security:** security fixes

3. Edit the generated file, replacing the auto-generated contents with an entry 
   describing your changes. Tips:

   * The file will be found in the `changelog.d` directory.
   * You can use markdown.
   * Try to keep the entry brief.
   * Remember that this is for human consumption, and intended more for *users* of the
     software, than for developers.

4. Commit the file to version control. A simple commit message like `Add news file` will do.


## Code of Conduct

Please note that all participants of this project are expected to follow the
Code of Conduct. By participating in this project you agree to abide by its
terms. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).


## Legal

Contributions are gladly accepted from their original author. By submitting
any copyrighted material via pull request, email, or other means, you agree to
license the material under the project’s open source license and warrant that
you have the legal authority to do so. See [LICENSE](LICENSE).
