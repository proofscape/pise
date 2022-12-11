# Upgrade Procedure

When you want to upgrade any of the software packages on which this project
depends, or add a new dependency, there are certain important steps to be
taken.

This document is a work in progress. At the moment, only a couple of points
have been noted. As we conduct upgrades going forward, we should update this
doc based on experience.

## In general

Check the license of the upgraded package. Is it still compatible?

If Apache, is there a `NOTICE` file? Has it been updated?
Check both the distributed package, and the GitHub repo.
Make any necessary changes in `manage/topics/pfsc/notice.py`.


## Special cases

### Pyodide

After running

    pfsc get pyodide -v M.m.p

enter the newly downloaded Pyodide version directory under
`PFSC_ROOT/src/pyodide/vM.m.p` and determine the version numbers
of the following bundled packages:

* `mpmath`
* `Jinja2`
* `MarkupSafe`

Then update these version numbers as necessary in `client/other-versions.json`.

You can also check <https://pyodide.org/en/stable/usage/packages-in-pyodide.html>.


### Supervisor

The `supervisor` python package is used in the OCA.
Its version number is set in `SUPERVISOR_VERSION` in `manage/conf.py`.
