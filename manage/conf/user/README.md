# `pfsc-manage conf/user`

You can use this directory to store multiple, alternative `user_conf` modules, and
keep them out of version control.

Specifically, `*.py` files in this directory are ignored by git.

Expected usage pattern is to define several modules here, such as:
    
    user_conf_A.py
    user_conf_B.py
    user_conf_C.py

and then make `conf/user_conf.py` a symlink to one or another of these modules.
