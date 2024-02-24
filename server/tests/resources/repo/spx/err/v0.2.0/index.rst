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

This time we have an error in a chart widget written in *role* form.
The SUBTEXT is okay, but we put the ROLE_FIELD in parentheses, instead
of angle brackets:
:pfsc-chart:`label and (target)`
