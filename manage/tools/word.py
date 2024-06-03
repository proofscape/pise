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

import os
import random


def random_adj_and_name(dodge_prefixes=None):
    """
    Choose a random adjective and mathematician name.

    All adjectives have unique three-letter prefixes.

    :param dodge_prefixes: optional list of strings. If provided, we will
      choose an adjective that is not a prefix of any of these strings.

    :return: pair (adj, name)
    """
    dodge_prefixes = list(sorted(dodge_prefixes or []))
    d_ptr = 0
    a_ptr = 0
    reject = set()
    while d_ptr < len(dodge_prefixes) and a_ptr < len(adjectives):
        d = dodge_prefixes[d_ptr]
        a = adjectives[a_ptr]
        if a > d:
            d_ptr += 1
            continue
        if d.startswith(a):
            reject.add(a)
        a_ptr += 1
    if reject:
        adjs = list(set(adjectives) - reject)
    else:
        adjs = adjectives

    if not adjs:
        raise Exception('Ran out of adjectives! You have too many deployment dirs!')

    adj = random.choice(adjs)
    name = random.choice(mathematicians)

    return adj, name


adjectives = """
accomplished
adaptable
adept
adventurous
affable
agreeable
amazing
ambitious
amiable
amusing
approachable
articulate
awesome
blithesome
brave
brilliant
calm
capable
careful
charming
cheerful
confident
courageous
creative
dazzling
decisive
dependable
determined
devoted
diligent
diplomatic
discreet
dynamic
educated
efficient
elegant
enchanting
energetic
engaging
enlightened
enthusiastic
excellent
expert
exuberant
faithful
fantastic
fearless
flexible
focused
friendly
generous
gleaming
glittering
glowing
good
gregarious
helpful
hilarious
honest
humorous
imaginative
impartial
incredible
independent
inquisitive
insightful
intelligent
inventive
kind
knowledgeable
likable
loyal
magnificent
marvelous
mirthful
observant
optimistic
organized
outstanding
patient
persistent
philosophical
pioneering
placid
plucky
polite
powerful
practical
productive
quiet
rational
reliable
remarkable
resourceful
sensible
sincere
sociable
spectacular
splendid
stellar
straightforward
stupendous
super
sympathetic
thoughtful
tidy
trustworthy
understanding
unique
upbeat
versatile
vibrant
witty
wonderful
""".split()

mathematicians = """
abel
artin
babbage
bachmann
banach
bernays
berwick
bessel
betti
bezout
blaschke
bolyai
bolzano
bonferroni
boole
borchardt
borel
brouwer
burnside
byron
cantor
caratheodory
carmichael
cartan
casorati
cassels
catalan
cauchy
cayley
cesaro
chebotaryov
chebyshev
chevalley
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
frechet
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
laguerre
landau
laplace
lasker
laurent
lebesgue
lefschetz
legendre
lehmer
libri
lie
lindelof
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
pluecker
poincare
poinsot
poisson
polya
poussin
puiseux
pythagoras
raabe
ramanujan
ramchundra
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
sierpinski
skolem
steinitz
stieltjes
stokes
study
sturm
sylow
sylvester
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
    assert adjectives == list(sorted(adjectives))

def test01():
    for k in range(10):
        print(random_adj_and_name())

def test02():
    """
    Show that the `dodge_prefixes` feature works.
    """
    dodge = list(set(adjectives) - set(['good']))
    a, n = random_adj_and_name(dodge_prefixes=dodge)
    assert a == 'good'

if __name__ == "__main__":
    test02()
