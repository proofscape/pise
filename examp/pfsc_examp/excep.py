# --------------------------------------------------------------------------- #
#   Copyright (c) 2018-2023 Proofscape Contributors                           #
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


class ExampError(Exception):
    """Exception base class"""
    pass


class UnknownParameterType(ExampError):
    """Unknown parameter type."""
    pass


class MissingDependencyError(ExampError):
    """Dependency (param or display) could not be found"""
    pass


class MissingParameterError(MissingDependencyError):
    """Parameter could not be found"""
    pass


class MissingDisplayError(MissingDependencyError):
    """Display could not be found"""
    pass


class UnexpectedParamArgError(ExampError):
    """Parameter received an unexpected argument."""
    pass


class UnexpectedParamArgTypeError(ExampError):
    """Parameter received an argument of an unexpected type."""
    pass


class MissingParamArgError(ExampError):
    """Parameter is missing a required arg."""
    pass


class UnresolvedParamArgError(ExampError):
    """Parameter arg value was supplied but could not be resolved."""
    pass


class MissingParamArgType(ExampError):
    """No type was declared for a parameter arg"""
    pass


class MissingName(ExampError):
    """Parameter defn missing name arg."""
    pass


class MalformedExampImport(ExampError):
    """Import into a display was malformed."""
    pass


class MissingExport(ExampError):
    """Display does not define an expected export."""
    pass


class MalformedInput(ExampError):
    """
    Generic error where user passed input and it was malformed.

    NOTE: If the input was the raw value to a Parameter, then
    `MalformedParamRawValue` should be used instead.
    """
    pass


class MalformedParamRawValue(MalformedInput):
    """The raw value passed to a parameter's build method was malformed."""

    def __init__(self, message, param):
        super().__init__(message)
        self.param = param
