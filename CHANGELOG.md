## 0.25.1 (------)

Improvements:

* Record more useful information in the manifest. For MODULE nodes, we now
  provide both `isTerminal` and `hasSubmodules`
  ([#6](https://github.com/proofscape/pfsc-server/pull/6)).

Bug Fixes:

* Prevent redundant edges from crashing the build process when factored through
  a method node
  ([#8](https://github.com/proofscape/pfsc-server/pull/8)).

Upgrades:

* `pytest==7.2.0` addresses a Dependabot alert re `py<=1.11.0`.
* `pytest-cov==4.0.0` while we're at it.

## 0.25.0 (221028)

Breaking Changes:

* In a move to no longer repeat ourselves with JS version numbers, we load JS
  assets in new ways ([#4](https://github.com/proofscape/pfsc-server/pull/4)).

Requires:

* `pfsc-ise >= 25.0`
* `pfsc-manage >= 0.25.0`

## 0.24.0 (221016)

Features:

* Add `pdfjsURL` to the served state. The URL includes a version number
  ([#3](https://github.com/proofscape/pfsc-server/pull/3)).

Breaking Changes:

* Serve native static assets under URLs including this project's version number
  ([#3](https://github.com/proofscape/pfsc-server/pull/3)).

Requires:

* `pfsc-manage >= 0.24.0`

## 0.23.5 (220920)

Features:

* Add `loginsPossible` to served state.


## 0.23.4 (220919)

Bug Fixes:

* Make demo repos usable when ALLOW_WIP is False
  ([#2](https://github.com/proofscape/pfsc-server/pull/2)).
