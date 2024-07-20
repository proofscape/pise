# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
#                                                                             #
#   Licensed under the Apache License, Version 2.0 (the "License");           #
#   you may not use this file except in compliance with the License.          #
#   You may obtain a copy of the License at                                   #
#                                                                             #
#       http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                             #
#   Unless required by applicable law or agreed to in writing, software       #
#   distributed under the License is distributed on an "AS IS" BASIS,         #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#   See the License for the specific language governing permissions and       #
#   limitations under the License.                                            #
# --------------------------------------------------------------------------- #

import re

import sphinx.util.logging

from pfsc.constants import PFSC_SPHINX_CRIT_ERR_MARKER


# Catch cases in which the option block of a pfsc- directive is malformed.
# If these are allowed to be mere warnings, then your Proofscape repo can build, and yet
# you may have Sphinx pages in which some of your widgets simply don't appear at all!
INVALID_OPT_BLOCK_RE = re.compile('Error in "pfsc-\\w+" directive:\ninvalid option block\\.')


def should_elevate(record):
    """
    Return a boolean saying whether the given warning record is one that should
    be elevated to a build-halting error.
    """
    # Our custom directives and roles will start their messages with the value
    # of the `PFSC_SPHINX_CRIT_ERR_MARKER` constant if they want to halt the build.
    if record.msg.find(PFSC_SPHINX_CRIT_ERR_MARKER) >= 0:
        return True

    # Below we catch special built-in Sphinx/docutils warnings that are serious enough
    # that the build should stop.
    if INVALID_OPT_BLOCK_RE.search(record.msg):
        return True

    return False


class ProofscapeWarningIsErrorFilter(sphinx.util.logging.WarningIsErrorFilter):
    """
    It can be tricky to halt the Sphinx build, with a helpful error message describing
    the location (filename and line number) where the error occurred. This class gives
    us a way to do that.

    Sphinx & docutils offer nice, built-in mechanisms for producing a *warning* with the
    location, but warnings do not halt the build.

    Alternatively, when you form your Sphinx app, you can set `warningiserror=True`, but
    then *every* warning stops the build, which is far too much:

        Example 1: "document not in toctree" warning halts build!

        Example 2: If you rename a directory in your Proofscape repo at the CLI, after having
        built at least once, then you will get a "toctree contains reference to nonexisting
        document" error, and you will not be able to build, even if building clean, no matter
        what you do.

    So `warningiserror=True` is much too strong, and we need a different solution.

    Here we subclass Sphinx's `WarningIsErrorFilter` class, which is the one responsible
    for turning warnings into errors when `warningiserror=True`. For this to make any
    difference, however, we have to monkey patch it into place, *replacing* the built-in
    class with this one, before we form our `Sphinx` instance. The patch is performed at
    the bottom of this module, so importing this into our Sphinx extension is enough.

    When we form our `Sphinx` instance, we set ``warningiserror=False`; however, our
    custom filter checks the warning message for special cases that we have determined
    (see `should_elevate()` function) should be raised as build-halting exceptions.
    """

    def filter(self, record):
        if should_elevate(record):
            # Since we're about to cause an exception to be raised, it doesn't matter
            # if we permanently alter the Sphinx app's `warningiserror` setting.
            # That app instance is not going to do anything more anyway.
            self.app.warningiserror = True
            # Ensure we don't get skipped:
            record.skip_warningsiserror = False
        return super().filter(record)


# Monkey patch it into place:
sphinx.util.logging.WarningIsErrorFilter = ProofscapeWarningIsErrorFilter
