"""
Definitions in this conf.py module will be equal to those of the base_conf.py
module, overridden by any definitions made in a user_conf.py module (if it exists).
"""

from conf.base_conf import *
print('pise/manage base_conf loaded')

try:
    from conf.user_conf import *
except ModuleNotFoundError:
    print("pise/manage found no user_conf")
else:
    print("pise/manage user_conf loaded")
