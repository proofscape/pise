Page C
======

This is Page C, and it lives inside the ``foo`` directory.
Widgets defined here should have the ``foo`` segment in their libpath.

.. pfsc-defns::
    :libpaths:
        Pf:  test.hist.lit.H.ilbert.ZB.Thm168.Pf
        Thm: test.hist.lit.H.ilbert.ZB.Thm168.Thm

Let's try another inline :pfsc-chart:`chart widget <Pf>`.

And confirm that the auto-generated numbers for these
:pfsc-chart:`chart widgets <Thm>` are properly incrementing.


Next we try defining chart widgets using the full directive form.
We still want the links they generate to be inline, so we're supposed
to use |w000: substitutions| for this.

Now we'll need a series of chart widgets, for unit tests.

|w001: one-line color definition|
|w002: color defn with repeated LHS, plus use of update|


.. |w000: substitutions| pfsc-chart::
    :view: Thm.A10, Pf.{A10,A20}
    :on_board: gh.foo.spam.H.ilbert.ZB.Thm168.X1
    :off_board: gh.foo.spam.H.ilbert.ZB.Thm168.X2
    :color:
        olB: Pf.{A10,A20}
        bgG: Thm.A10

.. |w001: one-line color definition| pfsc-chart::
    :view: Pf
    :color: olB: Pf.{A10,A20}

.. |w002: color defn with repeated LHS, plus use of update| pfsc-chart::
    :color: update
        bgG: Pf.{A10,A20}
        bgG: Thm.A10
