sphinx-proofscape doc with errors
=================================

.. pfsc::

    deduc Thm {
        asrt C {
            sy="C"
        }
        meson = "C"
    }

    deduc Pf of Thm.C {
        asrt R {
            sy="R"
        }
        asrt S {
            sy="S"
        }
        meson = "R, so S, therefore Thm.C."
    }


This chart widget has an error, because the ``view`` field wants to list
a libpath and a multipath, but it fails to put quotation marks around this.

.. pfsc-chart::
    :view: Thm.C, Pf.{R,S}
