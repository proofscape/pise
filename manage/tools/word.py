# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2024 Proofscape Contributors                           #
#                                                                             #
#   Licensed under the Apache License, Version 2.0 (the "License");           #
#   you may not use this file except in compliance with the License.          #
#   You may obtain a copy of the License at                                   #
#                                                                             #
#       http://www.apache.org/licenses/LICENSE-2.0                            #
#                                                                             #
#   Unless required by applicable law or agreed to in writing, software       #
#   distributed under the License is distributed on an "AS IS" BASIS,         #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
#   See the License for the specific language governing permissions and       #
#   limitations under the License.                                            #
# --------------------------------------------------------------------------- #

import random


def random_math_name(dodge_prefixes=None):
    """
    Choose a random mathematician name.

    All names have unique three-letter prefixes.

    :param dodge_prefixes: optional list of strings. If provided, we will
      choose a name that is not a prefix of any of these strings.

    :return: string
    """
    dodge_prefixes = list(sorted(dodge_prefixes or []))
    d_ptr = 0
    n_ptr = 0
    reject = set()
    while d_ptr < len(dodge_prefixes) and n_ptr < len(mathematicians):
        d = dodge_prefixes[d_ptr]
        n = mathematicians[n_ptr]
        if n > d:
            d_ptr += 1
            continue
        if d.startswith(n):
            reject.add(n)
        n_ptr += 1
    if reject:
        names = list(set(mathematicians) - reject)
    else:
        names = mathematicians

    if not names:
        raise Exception('Ran out of names! Maybe you have too many deployment dirs!')

    name = random.choice(names)

    return name


mathematicians = """
abel
artin
babbage
bachmann
banach
berwick
bessel
betti
bezout
blaschke
bolzano
bonferroni
boole
borel
brouwer
burnside
byron
cantor
cartan
cassels
catalan
cauchy
cayley
cesaro
chebyshev
clebsch
conway
courant
coxeter
crelle
darboux
dedekind
dehn
delaunay
demorgan
diophantus
dirichlet
dodgson
eisenstein
erdos
euclid
euler
fano
fermat
fourier
fraenkel
frege
fricke
frobenius
fubini
fuchs
furtwaengler
galois
gauss
germain
gibbs
gordan
grassmann
hadamard
hamilton
hardy
hasse
hausdorff
heaviside
heine
hensel
hermite
hesse
heyting
hilbert
hoelder
hurwitz
ince
jacobi
jordan
klein
kneser
koch
kovalevskaya
kronecker
krull
kummer
kuratowski
kutta
lagrange
landau
laplace
lasker
laurent
lebesgue
lefschetz
legendre
lehmer
libri
lindemann
liouville
lissajous
littlewood
lobachevsky
lucas
lyapunov
mandelbrot
markov
maschke
mellin
minkowski
moebius
mordell
navier
neumann
nevanlinna
newton
nightingale
nikodym
noether
ore
ostrogradski
pascal
peano
peirce
pell
picard
poincare
polya
poussin
puiseux
pythagoras
raabe
ramanujan
riemann
roch
ruffini
runge
russell
schoenflies
schur
schwarz
serret
severi
shanks
siegel
skolem
steinitz
stieltjes
stokes
sturm
sylow
takagi
taussky
thue
tietze
toeplitz
urysohn
vandiver
veblen
venn
vietoris
vinogradov
voronoy
wantzel
weber
wedderburn
weierstrass
weyl
whitehead
wronski
zariski
zassenhaus
zermelo
zolotarev
""".split()


###########

def test00():
    assert mathematicians == list(sorted(mathematicians))


def test01():
    for k in range(10):
        print(random_math_name())


def test02():
    """
    Show that the `dodge_prefixes` feature works.
    """
    dodge = list(set(mathematicians) - {'venn'})
    name = random_math_name(dodge_prefixes=dodge)
    assert name == 'venn'


if __name__ == "__main__":
    test02()
