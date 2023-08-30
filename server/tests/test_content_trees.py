# --------------------------------------------------------------------------- #
#   Copyright (c) 2011-2023 Proofscape Contributors                           #
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

from pfsc.contenttree import parse, build_forest_for_content


def test_round_trip():
    print()
    text = "foo.bar(cat@3_1_4~s(g1t2*g2t0)b*cat2@W(foo2*bar2~c(0)))"
    forest = parse(text)
    assert len(forest) == 1
    root = forest[0]
    print(root.write())
    auglps = root.expand()
    print('-------------')
    for alp in auglps:
        print(str(alp))
    print('-------------')
    forest2 = build_forest_for_content(auglps)
    assert len(forest2) == 1
    root2 = forest2[0]
    print(root2.write())
    print('-------------')
    resulting_text = root2.linearize()
    print(resulting_text)
    print(text)
    assert resulting_text == text


def test_code_formats():
    print()
    text = "foo.bar.cat~abc()d(3)Zfoo()Zbar(p7q11)"
    forest = parse(text, allowed_codes=['a', 'b', 'c', 'd', 'Zfoo', 'Zbar'])
    root = forest[0]
    print(root.write())
    auglps = root.expand()
    print('-------------')
    assert len(auglps) == 1
    alp = auglps[0]
    codes = alp.codes
    assert len(codes) == 6

    expected = [
        ['a', 0],
        ['b', 0],
        ['c', 0],
        ['d', 1, 3],
        ['Zfoo', 0],
        ['Zbar', 1, {'p': '7', 'q': '11'}]
    ]
    for code, ex in zip(codes, expected):
        assert code.type == ex[0]
        assert len(code.locations) == ex[1]
        if ex[1]:
            a = ex[2]
            if isinstance(a, int):
                assert code.locations[0].n == a
            elif isinstance(a, dict):
                assert code.locations[0].args == a
