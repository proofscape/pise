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

from pfsc_examp.excep import UnknownParameterType
from .types import *


class ParamTypes:
    Integer = "Integer"
    Prime = "Prime"
    Divisor = "Divisor"
    PrimRes = "PrimRes"
    NumberField = "NumberField"
    PrimeIdeal = "PrimeIdeal"


PARAM_TYPE_TO_CLASS = {
    ParamTypes.Integer:     Integer_Param,
    ParamTypes.Prime:       Prime_Param,
    ParamTypes.Divisor:     Divisor_Param,
    ParamTypes.PrimRes:     PrimRes_Param,
    ParamTypes.NumberField: NumberField_Param,
    ParamTypes.PrimeIdeal:  PrimeIdeal_Param,
}


def make_param(parent, info):
    """
    Construct an instance of a Parameter subclass.

    @param parent: the parent object for the instance
    @param info: (dict) the info dict from a param widget definition

    @raises: UnknownParameterType if info['ptype'] is not a known parameter type name.
    @returns: a Parameter subclass instance
    """
    ptype = info.get('ptype')
    PClass = PARAM_TYPE_TO_CLASS.get(ptype)
    if not PClass:
        raise UnknownParameterType(ptype)
    return PClass(parent, **info)
