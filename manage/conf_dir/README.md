# `pfsc-manage conf_dir`

You can use this directory to store multiple, alternative conf modules, and
keep them out of version control.

Specifically, `*.py` files in this directory are ignored by git.

Expected usage pattern is to define several modules here, such as:
    
    conf_A.py
    conf_B.py
    conf_C.py

and then make the `conf.py` at the top level of the project a symlink to one
or another of these modules.
