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

This chart widget has an error, because the ``viewOpts`` field uses
improper indentation. (The closing brace needs to be further indented.)

.. pfsc-chart::
    :view: Thm.C
    :viewOpts: {
        transition: false,
    }
