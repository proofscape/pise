Page A
======

.. pfsc::

    from test.moo.bar.results import Pf


This is Page A.

Let's try an inline :pfsc-chart:`proof1: chart widget <Pf>`.
With these, you can only specify the label, an optional name, and the ``view``
field.

.. pfsc-qna:: ultimateQuestion
    :question:
        What is the answer?
    :answer:
        42


.. _pageA-subsec:

Subsection
----------

This is a subsection.

It contains an inline equation: $\exp^{i \pi} + 1 = 0$, and,
$$\sum_{n=0}^\infty \frac{(-1)^n}{2n + 1}
= \frac{\pi}{4}$$
a block one, both delimited by dollar signs.

We also use the built-in rST math role :math:`28 = 1 + 2 + 4 + 7 + 14`,
and math directive:

.. math::

    \phi =
       \frac{-1 + \sqrt{5}}{2}

Its page should contain a mathjax script tag.

Here is some inline math using VerTeX: $an = an-1 + an-2@$.
Now a math block directive using VerTeX:

.. math::

    sin squ (x) + cos squ (x) = 1@

One problem with the VerTeX "@" character is that we have to watch out for rST
matching an email address, which it then turns into a `mailto` link.

A good rule is to always put the "@" at the end of the math mode, not the start.
*Most* of the time, that will be sufficient.
However, it is still possible to match an email address, if the closing
dollar sign is followed immediately by any char in the class ``[_~*/=+a-zA-Z0-9]``.
If that should be necessary for some reason, there is an easy solution, which is
just to preceded the "@" by a space, or double it, as in "@@".

For example, these are fine:

$$sin(x)@$$

Here's a sentence that ends with a letter: $ell@$.

But this will be a problem:

$bbZ@$-linear combination

You can solve the problem like this:

$bbZ @$-linear combination

or like this:

$bbZ@@$-linear combination

As for putting the "@" at the start of the math mode, this is just a bad idea,
since there are too many ways for it to fail. (Except that, if you would always
put a space after it, you'd always be fine.) For example,

$@ell pie$.

We can fix that by putting a space after the opening "@":

$@ ell pie$.

Or we can just move the "@" to the end:

$ell pie@$.
