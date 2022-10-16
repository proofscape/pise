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
