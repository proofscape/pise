# --------------------------------------------------------------------------- #
#   Copyright (c) 2018-2023 Proofscape Contributors                           #
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

"""
Write a lookup module with various tables in it.
Also redo some of the findings from the Canon Arithmeticus, like primitive residues.

References:
    https://archive.org/details/canonarithmetic00jacogoog
"""

from sympy import primerange, primitive_root, igcd

primes_under_1000 = list(primerange(2, 1000))
primes_under_100 = primes_under_1000[:25]
three_digit_primes = primes_under_1000[25:]
odd_primes_under_1000 = primes_under_1000[1:]

def compute_primitive_residues():
    """
    Compute _one_ primitive residue for each modulus that has one, under 1000.
    Return these in a dictionary of the form {modulus:prim_res}.

    Compute _all_ primtiive residues for those moduli under 100 that have any.
    Return these in a dictionary of the form {modulus:list}.

    We return both dictionaries.
    """
    prs = {2:1, 4:3}
    all_prs = {2:[1], 4:[3]}

    def find_pr(m, phi, find_all=False):
        r = primitive_root(m)
        if not find_all:
            return r
        else:
            R = []
            a = 1
            for k in range(1, phi):
                a = (a*r) % m
                if igcd(k, phi) == 1:
                    R.append(a)
            R = list(sorted(R))
            return R

    for p in odd_primes_under_1000:
        m = p
        phi = p - 1
        while m < 1000:
            prs[m] = find_pr(m, phi)
            if m < 500:
                prs[2*m] = find_pr(2*m, phi)
            if m < 100:
                all_prs[m] = find_pr(m, phi, find_all=True)
            if m < 50:
                all_prs[2*m] = find_pr(2*m, phi, find_all=True)
            m *= p
            phi *= p

    return prs, all_prs

def write_prim_res_lookup():
    prs, all_prs = compute_primitive_residues()
    s = ''
    s += '# One primitive residue for each modulus under 1000:\n'
    s += 'one_prim_res_under_1000 = {'
    c = 0
    for m in sorted(prs.keys()):
        s += '\n    ' if c % 8 == 0 else ' '
        c += 1
        g = prs[m]
        s += '%3d: %2d,' % (m, g)
    s += '\n}\n\n'
    s += '# All primitive residues for each modulus under 100:\n'
    s += 'all_prim_res_under_100 = {\n'
    for m in sorted(all_prs.keys()):
        s += '    %2d: %s,\n' % (m, sorted(all_prs[m]))
    s += '}\n\n'
    return s

def write_primes():
    s = ''
    s += 'primes_under_1000 = [\n'
    for i in range(11):
        s += '    ' + ', '.join('%3d' % p for p in primes_under_1000[15*i:15*i+15]) + ',\n'
    s += '    ' + ', '.join('%3d' % p for p in primes_under_1000[-3:]) + '\n'
    s += ']\n\n'
    s += 'primes_under_100 = primes_under_1000[:25]\n'
    s += 'three_digit_primes = primes_under_1000[25:]\n'
    s += 'odd_primes_under_1000 = primes_under_1000[1:]\n\n'
    return s

# If any function names begin with "test", then PyCharm insists on
# using pytest as test runner, and won't let you run your
# `if __name__ == "__main__"` block. So we add leading underscores.
def _test1():
    prs = compute_primitive_residues()
    import json
    print()
    print(json.dumps(prs, indent=4))

def _test2():
    from collections import defaultdict
    prs = compute_primitive_residues()
    # Compute histogram.
    H = defaultdict(set)
    for m, g in prs[0].items():
        H[g].add(m)
    # Display histogram.
    for g in sorted(H.keys()):
        n = len(H[g])
        print('%3d: ' % g, "#" * n)
    # List set members.
    print()
    for g in sorted(H.keys()):
        print(g)
        print('    ', sorted(H[g]))

def _test3():
    L = write_prim_res_lookup()
    print(L)

LICENSE_HEADER = """\
# --------------------------------------------------------------------------- #
#   Copyright (c) 2018-2023 Proofscape Contributors                           #
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

"""

def generate_canon():
    """
    Run this method to generate the canon_arithmeticus.py file in the
    `pfsc_examp` package.
    """
    import os
    this_file = os.path.abspath(__file__)
    this_dir = os.path.dirname(this_file)
    output_dir = os.path.join(this_dir, 'pfsc_examp')
    canon_file = os.path.join(output_dir, 'canon_arithmeticus.py')

    text = ''
    text += LICENSE_HEADER
    text += '# This module was generated by gen_CA.py\n\n'
    text += write_primes()
    text += write_prim_res_lookup()

    with open(canon_file, 'w') as f:
        f.write(text)


if __name__ == "__main__":
    generate_canon()
