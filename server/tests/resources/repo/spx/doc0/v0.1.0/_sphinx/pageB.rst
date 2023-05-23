Page B
======

This is Page B.

There are no widgets on this page.
So there should be no ``<script>`` tag defining a ``pfsc_widget_data``.

.. code-block:: proofscape

    from gh.foo.bar import spam as eggs

    # This is a comment.
    deduc Thm {
        supp P {
            sy="$P$"
        }
        asrt C {
            en='$C$'
        }
        meson = "
        Suppose P. Then C.
        "
    }

    deduc Pf of Thm.C {
        asrt A {
            fr="""$A$"""
        }
        asrt B {
            de='''$B$'''
        }
        meson='
        From Thm.P get A. Then B, hence Thm.C.
        '
    }

.. code-block:: meson

    A, so B, therefore C.X by D.Y.Z and E.
    Hence F, using G, so H.

.. code-block:: meson-grammar
    :caption: Meson production rules

    MesonScript ::= roam? initialSentence sentence*
    initialSentence ::= assertion | supposition
    sentence ::= conclusion | (roam|flow)? initialSentence
    conclusion ::= inf assertion method?
    assertion ::= nodes reason*
    reason ::= sup nodes
    method ::= how nodes
    supposition ::= modal nodes
    nodes ::= name (conj name)*
