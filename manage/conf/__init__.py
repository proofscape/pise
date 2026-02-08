"""
Definitions in this conf.py module will be equal to those of the base_conf.py
module, overridden by any definitions made in a user_conf.py module (if it exists).
"""

from conf.base_conf import *

try:
    from conf.user_conf import *
except ModuleNotFoundError:
    pass
