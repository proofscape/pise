# Requirements files

## What's here

* `requirements.in`: Manually listed packages we have deliberately installed
  (so, no recursive requirements), which are available from PyPI, and which are 
  required for the app to run.

* `requirements.nodeps`: Manually listed packages we want to install while
  telling `pip` _not_ to add their dependencies.

* `requirements.local`: Manually listed packages that are required to run, and
  which are _not_ available on PyPI, but which are expected to be found as
  siblings of `pfsc-server`.

* `requirements.txt`: Automatically generated from `requirements.in` using the
  `pip-tools` package.

* `test-requirements.in`: Maually listed; required for testing.

* `test-requirements.hashless`: Manually listed; lacking a hash.

* `test-requirements.txt`: Generated from the `.in` file.

* `dev-requirements.in`: Manually listed; required only for development.

* `dev-requirements.txt`: Generated from the `.in` file.


## How to install packages

What you need to do depends on whether you are setting up a development
environment, or a testing environment, or building a docker image to run the
app.


### Setting up a development environment

Go to the top level directory of this project, and:

```shell
python -m venv venv
. venv/bin/activate
pip install -U pip
./req/install.sh
```

(Note: If at some point we no longer need the `.nodeps` and `.local` files,
we might change  the instructions here to using `pip-sync` (also included
with `pip-tools`). See <https://pypi.org/project/pip-tools/>)


### Setting up a testing environment

Same, except run

```shell
./req/install_testing.sh
```

instead of `install.sh`.


### Building a docker image

This should be carried out using an appropriate command in the `pfsc-manage`
project, such as `pfsc build server latest`.

Internally, that command will copy `requirements.nodeps` and `requirements.txt`
into the image and use them there, whereas for `requirements.local` it will
take special steps to copy the packages into the image, and see that they too
are installed.


## How to make updates

If you change a package version number, or add or remove a package, make this
change in a `.nodeps`, `.in`, or `.local` file.

If the change is made in a `.nodeps` file, then there's a good chance you need
to also update a corresponding list of selected dependencies in a `.in` file
as well (for those of the package's dependencies that you _do_ want).

If the change is made in a `.in` file, you then need to recompile the `.txt`
files. From this directory, just do:

```shell
./compile.sh
```


## Version control

All the files in this directory are committed to version control, including
the compiled ones.
