Page D
======

.. pfsc::

    import test.spx.doc0
    from ..pageC import _page as pageC
    from test.spx.doc0.index import _page as doc0_index
    from ... import doc1, doc2 as docB

    anno Notes1 @@@ This is a very short annotation. @@@

This is a reference to :ref:`a section on another page <pageB-subsec>`.

Next let's have a *second* ``pfsc`` directive, so we can check that it simply
*adds to* the things defined in the first (doesn't *replace* them).

.. pfsc::

    deduc Thm {
        asrt C {
            sy="C"
        }
        meson = "C"
    }

The ``pfsc`` directive above should define a deduction ``Thm`` whose libpath
does *not* contain ``_page`` as penultimate segment. Entities defined under
``pfsc`` directives live at the *top* level of the module, alongside the
``SphinxPage`` called ``_page``.
