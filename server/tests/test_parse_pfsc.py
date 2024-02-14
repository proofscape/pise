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

import pytest

from pfsc.excep import PfscExcep, PECode
from pfsc.build.repo import RepoInfo, get_repo_info
from pfsc.lang.modules import (
    load_module, PathInfo, strip_comments, remove_modules_from_disk_cache
)
from pfsc.lang.annotations import json_parser, PfscJsonTransformer
from pfsc.lang.widgets import ChartWidget
from pfsc.sphinx.pages import SphinxPage
from pfsc.constants import WIP_TAG


error = [
    ('deduc Thm { asrt C {} meson="C" } deduc Pf of Thm.A {}', PECode.TARGET_DOES_NOT_EXIST),
    ('deduc Thm { asrt C {} meson="C" } deduc Pf of Thm {}', PECode.TARGET_OF_WRONG_TYPE),
    ('deduc Thm1 { asrt C {} meson="C" }  deduc Thm2 { asrt C {} meson="C" }  deduc Pf of Thm1.C, Thm2.C {}', PECode.TARGETS_BELONG_TO_DIFFERENT_DEDUCS),
]
@pytest.mark.parametrize(['pfsc_text', 'err_code'], error)
@pytest.mark.psm
def test_load_module_error(app, pfsc_text, err_code):
    with app.app_context():
        with pytest.raises(PfscExcep) as ei:
            mod = load_module('foo.dummy.path', text=pfsc_text)
            mod.resolve()
        assert ei.value.code() == err_code


import_success = [
    'test.hist.lit.H.ilbert.ZB.Thm168',
    'test.hist.lit.H.ilbert.ZB.Thm119',
    'test.hist.lit.G.auss'
]
@pytest.mark.parametrize('libpath', import_success)
@pytest.mark.psm
def test_pfsc_import_1(app, libpath):
    with app.app_context():
        module = load_module(libpath, caching=0)
    pass

def test_name_availability_check():
    ri = get_repo_info('test.foo.bar')
    ri.checkout('v0')
    pi = PathInfo('test.foo.bar')
    assert pi.name_is_available('spam')
    assert not pi.name_is_available('expansions')
    pi2 = PathInfo('test.foo.bar.expansions')
    with pytest.raises(PfscExcep) as ei:
        pi2.name_is_available('spam')
    assert ei.value.code() == PECode.LIBPATH_IS_NOT_DIR

def test_name_availability_check_2():
    """
    Test that we correctly identify dirs with dunder modules in them as
    having unavailable names.
    """
    ri = get_repo_info('test.foo.imp')
    ri.checkout('v0')
    pi = PathInfo('test.foo.imp')
    assert not pi.name_is_available('A')
    assert pi.name_is_available('Z')

@pytest.mark.psm
def test_parse(app):
    with app.app_context():
        mod = load_module('test.hist.lit.H.ilbert.ZB.rdefs', caching=0)
        d_alp = mod['d_alp']
        assert d_alp.lhs == r"$\alpha$"

@pytest.mark.psm
def test_no_cyclic_import_error(app):
    """
    This test shows that, FOR NOW at least, there is no error in the case in
    which module A imports something from module B, while module B also
    imports something from module A.

    In our old system, with early resolution, we detected this case and raised
    a PECode.CYCLIC_IMPORT_ERROR. Having now moved to a system with separate
    READ and RESOLVE phases, cyclic imports don't *have to* be an error.

    However, they are still an odd case, and it remains to be seen whether we
    should make them an error or not. If we wanted to detect them now, we
    might do that in `pfsc.lang.modules.PfscModule.resolve()`, under an
    `if self.resolving:` block.

    The potential remaining problem is that, while the second module gets away
    with importing an object from the first, that object is, as yet, unresolved.
    As the second module proceeds with its own resolution, might something go
    wrong as it attempts to *use* this "unsaturated" object?

    It seems like some imports of this kind could be fine, while others could
    be problematic, depending on the types of objects involved.
    """
    with app.app_context():
        ri = get_repo_info('test.foo.bar')
        ri.checkout('v6')
        mod = load_module('test.foo.bar.results', caching=0)
        mod.resolve()


@pytest.mark.parametrize(['vers_num', 'err_code'], [
    (0, PECode.PLAIN_RELATIVE_IMPORT_MISSING_LOCAL_NAME),
    (1, PECode.CYCLIC_IMPORT_ERROR),
    (2, PECode.CYCLIC_IMPORT_ERROR),
    (3, PECode.CYCLIC_IMPORT_ERROR),
    (4, PECode.CYCLIC_IMPORT_ERROR),
    (5, PECode.CYCLIC_IMPORT_ERROR),
    (6, PECode.CYCLIC_IMPORT_ERROR),
    (7, PECode.CYCLIC_IMPORT_ERROR),
    (8, PECode.CYCLIC_IMPORT_ERROR),
    (9, PECode.CYCLIC_IMPORT_ERROR),
])
@pytest.mark.psm
def test_isolated_import_error(app, vers_num, err_code):
    """
    This test shows that we catch "isolated" import errors, i.e.
    errors arising from single import statements. This is as opposed
    to errors that arise from the interaction of two or more import
    statements, which we examined in another unit test.
    """
    # Need an app context since we are going to load modules that define
    # annotations, and that means we will check whether the repo is trusted,
    # and that requires a configuration, hence an app context.
    with app.app_context():
        vers = f'v{vers_num}'
        with pytest.raises(PfscExcep) as ei:
            ri = get_repo_info('test.foo.imp')
            ri.checkout(vers)
            mod = load_module('test.foo.imp.A.B', caching=0)
            mod.resolve()
        print('\n', vers)
        print(ei.value)
        assert ei.value.code() == err_code


@pytest.mark.psm
def test_import_unbuilt_external_rst_module_at_wip(app):
    """
    Test that we can import from an rst module defined in another repo,
    at WIP version, which has not been built yet (or anyway, which has no
    pickle file).

    What's special about this case is that it prompts a call to
    `Builder.build()` from within the `load_module()` function.
    """
    with app.app_context():
        # Purge pickle file, ensuring that the module has to be rebuilt.
        remove_modules_from_disk_cache(['test.spx.doc0.index'], version=WIP_TAG)

        ri = get_repo_info('test.foo.imp')
        ri.checkout('v11')
        mod = load_module('test.foo.imp.A.B', caching=0)
        mod.resolve()

        assert mod
        ix = mod.get('doc0_index')
        assert isinstance(ix, SphinxPage)
        w0 = ix.get('w0')
        assert isinstance(w0, ChartWidget)


@pytest.mark.psm
def test_import_submodule_through_self(app):
    """
    Test that we are allowed to import a submodule through its parent,
    using a `from ... import ...` statement.
    """
    with app.app_context():
        ri = get_repo_info('test.foo.imp')
        ri.checkout('v10')
        mod = load_module('test.foo.imp.A.B', caching=0)
        mod.resolve()
        assert mod['C.c'].typename == 'annotation'

@pytest.mark.psm
def test_supp_alts_and_flse_contras(app):
    """
    Test the ability to name sets of alternatives for supp nodes,
    and to tell flse nodes which supp's are contradicted.
    """
    with app.app_context():
        ri = get_repo_info('test.foo.bar')
        ri.checkout('v7')
        cache = {}
        res = load_module('test.foo.bar.results', cache=cache)
        exp = load_module('test.foo.bar.expansions', cache=cache)
        exp.resolve(cache=cache)
        assert res['Pf.F'].get_contras()[0]['en'] == "Suppose not C."
        assert res['Pf.T'].wolog
        assert res['Pf.Case1.S'].get_alternates().pop()['en'] == "The assumption of the second case."
        assert res['Pf.Case2.S'].get_alternates().pop()['en'] == "The assumption of the first case."
        assert len(exp['Pf1.Case1.S'].get_alternates()) == 2
        assert len(exp['Pf2.Case1.S'].get_alternates()) == 2
        INSPECT = False
        if INSPECT:
            for m in [1, 2]:
                print()
                for n in [1, 2, 3]:
                    alts = exp['Pf%s.Case%s.S' % (m, n)].get_alternates()
                    print('\nPf%s, Case%s alternates:' % (m, n))
                    for alt in alts:
                        print('  %s' % alt.getLibpath())

def test_json_parse():
    """
    We use a custom json parser which allows the following things:
        - keys may be strings (in double quotes ") or any "CNAME", i.e. anything matching ("_"|LETTER) ("_"|LETTER|DIGIT)*
        - strings may be multiline. They may be delimited with single (') or double (") quotation marks
        - for the boolean and null constants, you may write the Javascript or Python versions; in other
          words, all these are valid: true, True, false, False, null, None

    Since we modified the version from the Lark tutorial to parse integers _as_ integers,
    we also test an integer and float value here.
    """
    j = """{
        foo: "bar
              bar",
        cat: 3,
        "spam": 3.0,
        baz: 'spam',    
        eins: true,
        zwei: True,
        drei: false,
        vier: False,
        funf: null,
        sechs: None
    }"""
    tree = json_parser.parse(j)
    d = PfscJsonTransformer().transform(tree)
    print()
    print(d)
    assert d['foo'] == "bar\n              bar"
    assert isinstance(d['cat'], int)
    assert isinstance(d['spam'], float)
    assert d['eins'] is d['zwei']
    assert d['drei'] is d['vier']
    assert d['funf'] is d['sechs']

@pytest.mark.psm
def test_widget_braces(app):
    """
    Just realized we need to watch strings in widgets, since they may contain unmatched braces!
    Let's test this.
    """
    with app.app_context():
        ri = get_repo_info('test.foo.bar')
        ri.checkout('v8')
        exp = load_module('test.foo.bar.expansions', caching=0)
        exp.resolve()
        for i in range(1, 5):
            print(exp['Notes2.q%s' % i].writeData())
        i1 = exp['Notes2.q1'].writeData()['answer'].find('({)')
        print(i1)
        assert i1 == 28
        i2 = exp['Notes2.q2'].writeData()['answer'].find('(})')
        print(i2)
        assert i2 == 29
        i3 = exp['Notes2.q3'].writeData()['answer'].find('(&#34;)')
        print(i3)
        assert i3 == 74
        i4 = exp['Notes2.q4'].writeData()['answer'].find('things.')
        print(i4)
        assert i4 == 160

@pytest.mark.psm
def test_extended_json_syntax(app):
    """
    Show that libpaths occurring in assignments are replaced by the objects
    they point to.
    """
    print()
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v11')
        mod = load_module('test.foo.bar.expansions', caching=0)
        mod.resolve()
        print(mod['obj1'].rhs)
        obj1 = {'foo': ['bar', 3, True, False, None]}
        assert mod['obj1'].rhs == obj1
        print(mod['obj2'].rhs)
        obj2 = {'spam': obj1}
        assert mod['obj2'].rhs == obj2
        print(mod['Notes4'].widget_seq[0].data['stuff'])
        assert mod['Notes4'].widget_seq[0].data['stuff'] == obj2


mod_text_01 = """
# Header notice...
deduc Thm {
    asrt C {  # here is an inline comment
        sy="C#this one stays"
    }
    
    # Here a comment in the middle of a deduc defn.
    meson='''C # this is not a comment'''
}
"""

mod_text_01_stripped = """

deduc Thm {
    asrt C {  
        sy="C#this one stays"
    }
    
    
    meson='''C # this is not a comment'''
}
"""

@pytest.mark.parametrize("text, expected", [
    [mod_text_01, mod_text_01_stripped],
])
def test_strip_comments(text, expected):
    assert strip_comments(text) == expected


@pytest.mark.psm
def test_empty_meson_script(app):
    with app.app_context():
        ri = RepoInfo('test.foo.bar')
        ri.checkout('v15')
        with pytest.raises(PfscExcep) as ei:
            mod = load_module('test.foo.bar.results', caching=0)
            mod.resolve()
        assert ei.value.code() == PECode.DEDUCTION_DEFINES_NO_GRAPH


######################################################################
# Manual testing

def run_error_case(n):
    p = error[n]
    test_load_module_error(p[0], p[1])

if __name__ == "__main__":
    try:
        test_pfsc_import_1(import_success[4])
    except AssertionError:
        pass
