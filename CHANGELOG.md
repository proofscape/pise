## next (------)

## 0.29.0 (240101)

Breaking Changes:

* `pdf` widgets are now `doc` widgets
  ([#36](https://github.com/proofscape/pise/pull/36)).
* Underscores in `owner` and `repo` libpath segments translate to hyphens in remote URLs
  ([#48](https://github.com/proofscape/pise/pull/48)).
* Require colon after name in Sphinx widgets that do not accept a label
  ([#51](https://github.com/proofscape/pise/pull/51)).

Improvements:

* Update management docs
  ([#34](https://github.com/proofscape/pise/pull/34)).
* Improve context menus for highlights in doc panels, correcting the offset,
  and increasing readability of the options
  ([#39](https://github.com/proofscape/pise/pull/39)).
* Improve the selection combiner dialog, in overall layout and copy functionality
  ([#43](https://github.com/proofscape/pise/pull/43)).
* Improve the template box in the selection combiner dialog
  ([#47](https://github.com/proofscape/pise/pull/47)).

Bug Fixes:

* Make Sphinx doc widgets properly accept libpaths for `sel` field
  ([#37](https://github.com/proofscape/pise/pull/37)).
* Support forward references for doc label clones
  ([#38](https://github.com/proofscape/pise/pull/38)).
* Resolve issues with internal links in Sphinx panels, ensuring location
  updates are not reset by panel splits or rebuilds
  ([#41](https://github.com/proofscape/pise/pull/41)).
* Make Sphinx panels become the active tab, upon internal click
  ([#42](https://github.com/proofscape/pise/pull/42)).
* Repair load-and-nav operation for PDF panels
  ([#44](https://github.com/proofscape/pise/pull/44)).
* Make doc panels enter enrichments mode before auto-navigating to highlights
  ([#45](https://github.com/proofscape/pise/pull/45)).
* Debug issue with extra rewrites on Sphinx rebuilds, wherein certain unchanged
  pages were becoming broken (due to losing required Proofscape data object)
  ([#46](https://github.com/proofscape/pise/pull/46)).
* Repair issues with the linking dialog, in the case that the only existing
  link is a tree-link
  ([#49](https://github.com/proofscape/pise/pull/49)).
* Repair issues with the linking dialog, when adding new tree-links
  ([#50](https://github.com/proofscape/pise/pull/50)).

Upgrades:

* `urllib3 2.0.4 --> 2.0.7`
* `Werkzeug 2.3.7 --> 2.3.8`


## 0.28.0 (230830)

This version introduces major changes to the build system, the most
visible of which is that you can now write `rst` files alongside `pfsc`
files, in order to build Sphinx pages.

Sphinx pages provide an alternative to the old annotation pages (which are
also still supported). They use the Furo theme, and have sidebar tables of contents,
and are linked to each other using all the standard ref mechanisms as in any
Sphinx project.

Certain built-in extensions are provided, including various directives and roles
for Proofscape widgets, allowing you to include many of the same widget types (chart,
pdf, etc.) in Sphinx pages as in annotation pages. There is also a `.. pfsc::` directive,
under which you can write arbitrary `pfsc` module syntax, and thus make imports, define
deductions, etc.

Internally, `rst` files are regarded as defining first-class Proofscape modules,
just as do `pfsc` files. Their libpath mirrors their filesystem path. They always
define one special object, called `_page`, which represents the Sphinx page they define.
This `_page` object *contains* any widgets defined using widget roles and directives,
and sits *alongside* anything defined under any `.. pfsc::` directives. Imports
between and among `rst` and `pfsc` files are supported in all directions.

Breaking Changes:

* The build process now exhibits `make`-like behavior, wherein all and only
  those parts of a given repo are rebuilt that have changed since the last build.
  Accordingly, building at the CLI now requires a repopath (not an arbitrary
  modpath), no longer accepts an `-r` ("recursive") switch, and you can no longer
  request to build a single module in isolation.

* No more programmatic generation of widget names *in source modules*.
  The names are still generated wherever missing, and written into the built
  products, but no longer into the source code. The generated names now begin
  with an underscore.

Upgrades:

* `Eventlet 0.33.1 --> 0.33.3`

## 0.27.0 (230828)

Breaking Changes:

* Doc refs can no longer be defined under `pdf` field in nodes; instead,
  must now use `doc` field
  ([#21](https://github.com/proofscape/pise/pull/21)).
* New pdf widget syntax: `selection` becomes `sel`; `sel: true` is new default
  ([#21](https://github.com/proofscape/pise/pull/21)).

Improvements:

* Improve output of `pfsc.blueprints.cli.auto_deps_build()`.
* Support editable sections in display widgets
  ([#13](https://github.com/proofscape/pise/pull/13)).
* When nodes define both latex and docref labels, the latter now only serves
  to navigate a linked doc; it contributes to the label only when no latex
  label is defined
  ([#18](https://github.com/proofscape/pise/pull/18)).
* In addition to the old navigation links `N --> C` (notes to charts), we now
  support `D --> T` (doc to tree) as well as `N <--> D <--> C`
  ([#21](https://github.com/proofscape/pise/pull/21)).
* Navigation links are editable via drag-and-drop, and via tab context menu
  ([#21](https://github.com/proofscape/pise/pull/21)).
* When defining a docref `doc#code` for a node, may omit the `doc#` part
  if a `docInfo` field is defined in the surrounding deduc
  ([#21](https://github.com/proofscape/pise/pull/21)).
* New pdf widget syntax: added `doc` field; `sel` may point to a node libpath,
  to clone its doc ref
  ([#21](https://github.com/proofscape/pise/pull/21)).
* Add `z` command to combiner code syntax
  ([#21](https://github.com/proofscape/pise/pull/21)).
* Add `clone` command to pfsc module syntax
  ([#22](https://github.com/proofscape/pise/pull/22)).

Bug Fixes:

* Widget group control mappings across windows used to be able to create an
  inconsistent state after the primary window was reloaded. Now such mappings
  are properly saved and restored
  ([#16](https://github.com/proofscape/pise/pull/16)).
* Manual sorting of tabs is now properly recorded in the saved state
  ([#17](https://github.com/proofscape/pise/pull/17)).
* Stopped build from crashing if a whole module was (accidentally) named in a
  meson script
  ([#19](https://github.com/proofscape/pise/pull/19)).
* Debugged issue with closing theory map panels
  ([#24](https://github.com/proofscape/pise/pull/24)).
* Repaired static dir in OCA image
  ([#29](https://github.com/proofscape/pise/pull/29)).
* Repaired issue with pages with examp widgets being closed before Pyodide
  finished loading
  ([#31](https://github.com/proofscape/pise/pull/31)).

Upgrades:

* `Flask 2.1.2 --> 2.3.2`
* `Flask-Login 0.6.1 --> 0.6.2`
* `Flask-SocketIO 5.1.2 --> 5.3.5`
* `Requests 2.25.1 --> 2.31.0`
* `Werkzeug 2.1.2 --> 2.3.7`
* `pfsc-examp 0.22.8 --> 0.23.0`

## 0.26.1 (221216)

Improvements:

* Add `--auto-deps` option to `flask pfsc build` command. Also improve
  error handling in this command
  ([#12](https://github.com/proofscape/pise/pull/12)).

Bug Fixes:

* Repair image name in `admin.sh` script generated by `pfsc deploy generate`
  when `--official` switch is used.

## 0.26.0 (221211)

Breaking Changes:

* (Re)combined `pfsc-server`, `pfsc-ise`, and `pfsc-manage` into one `pise`
  repository. These projects were taken at their latest versions, `0.25.1`,
  `25.4`, and `0.25.1` respectively.

## 0.25.1 (221122)

Improvements:

* Record more useful information in the manifest. For MODULE nodes, we now
  provide both `isTerminal` and `hasSubmodules`
  ([#6](https://github.com/proofscape/pfsc-server/pull/6)).
* Add `PFSC_DEFAULT_TRUSTED_LIBPATHS` config var.
* Support env-var-based startup for `pfsc-server` docker containers (command- 
  based is still supported).

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
