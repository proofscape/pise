Page E
======

External Links
--------------

This is an external hyperlink to Proofscape_.

This is `another one <https://proofscape.org>`_.


Examp Widgets
-------------

.. pfsc-param:: eg1_k:
    :ptype: "NumberField"
    :tex: "k"
    :init: "cyc(7)"
    :args: {
        gen: "zeta",
        foo: [
                1, 2, 3, 4
            ],
        bar: false,
        }

.. pfsc-disp:: eg1_disp1:
    :import: {
        k: eg1_k
        }
    :export: ["B"]

    # BEGIN EDIT
    # You can choose the printing format for the elements of the basis.
    fmt = 'alg'
    # END EDIT
    B = k.integral_basis(fmt=fmt)
    html = "An integral basis for $k$:\n\n"
    html += r"$\{" + ','.join([latex(b, order='old') for b in B]) + r"\}$"
    return html



.. _Proofscape: https://proofscape.org
