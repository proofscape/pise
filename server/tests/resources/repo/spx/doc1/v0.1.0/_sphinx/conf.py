# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Foobar'
copyright = '2022-2023, author'
author = 'author'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx_proofscape',
]

# We test that it doesn't matter if you set these values, and that they
# are overridden by our use of the `-D` switch when we do the Sphinx build.
pfsc_repopath = 'an.incorrect.value'
pfsc_repovers = "not_the_right_version_number"
pfsc_import_repos = {
    'test.moo.bar': 'contradicts.root.module',
}


templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
