.. _toposort:
    https://pypi.python.org/pypi/toposort/

.. _ply:
    https://pypi.python.org/pypi/ply/

.. _macros file format:
    macros_lang.rst


kernelconfig
============

Generate Linux kernel configuration files from curated sources,
detected hardware, installed packages and user input.


Introduction
------------



Installing kernelconfig
-----------------------

This is not possible yet.


Dependencies
++++++++++++

Required:

* Python >= 3.4, or Python 3.3 with backports: enum

* `toposort`_

* Python Lex-Yacc (`PLY`_)

* C compiler, ...


Optional:

* Linux kernel sources for copying certain files from ``scripts/kconfig``,
  a bundled copy is used otherwise


Running kernelconfig
--------------------

In the simplest case,
run :code:`kernelconfig` without any arguments
from wihin the kernel sources directory.
It uses the ``default`` `settings`_ and creates a ``.config`` file.

.. N.B:

    ==comment== only works if $PWD is the top-level kernel source directory


.. Important::

    Until *curated sources* are not implemented,
    it is necessary the create an input ``.config`` file before running
    kernelconfig, e.g. with ``make defconfig``.

    This file can be specified with the ``--config`` option
    and defaults to ``<srctree>./.config``.


It is also possible to specify the kernel sources directory by hand,
creating the ``.config`` file in this directory::


    $ kernelconfig -k /usr/src/linux


Or write the configuration to a different output file::

    $ kernelconfig -O ./my_config


It is also possible to read an input config file
rather than using a *curated source*::

    $ kernelconfig --config ./my_config


The input and output config file can point to the same file.
Prior to writing the output file,
a backup of the old file is created (``<output>.bak``).

| The target architecture is usually determined by ``uname -m``.
| For cross-compilation scenarios, it is possible to specify it manually::

    $ kernelconfig -a arm


.. _usual options:

kernelconfig accepts a number of options:

-h, --help

    Print the help message and exit.

--usage

    Print the usage message and exit.

-V, --print-version

    Print the version and exit.

-a <arch>, --arch <arch>

    Target architecture,
    defaults to the system's architecture as returned by ``uname -m``.

-k <srctree>, --kernel <srctree>

    Path to the Linux kernel sources directory.

    Defaults to the current working directory.

-s <settings>, --settings <settings>

    Path to or name of the `settings file`_.

    Files can be specified with an absolute path
    or a relative path starting with ``./``.

    Otherwise, ``<settings>`` refers to a settings file in one of the
    `settings directories`_.

    Defaults to "default".

--config <file>

    The input config file.

    Defaults to ``<srctree>/.config``.
    (**future**: no default, ``[source]`` section settings file)

-O <file>, --outconfig <file>

    The output .config file.

    Defaults to ``<srctree>/.config``.

-q, --quiet

    Decrease the console log level.

    This option can be given multiple times,
    each time it decreases the log level by 1,
    and the effective log level is calculated using
    ``WARNING + (quiet - verbose)`` (higher level means less verbosity).

-v, --verbose

    Increase the console log level.

    Can be specified more than once, see ``--quiet`` for details.





Running kernelconfig from the source directory
++++++++++++++++++++++++++++++++++++++++++++++

kernelconfig can be run in *standalone* mode from the project's sources.
For this purpose, it offers a wrapper script named ``kernelconfig.py``
that takes care of running ``setup.py`` and invoking the main script.

First, get the sources::

    $ mkdir -p ~/git
    $ git clone git://github.com/dywisor/kernelconfig.git ~/git/kernelconfig


The wrapper can be run directly::

    $ ~/git/kernelconfig/kernelconfig.py


It can also be *installed* by creating a symlink to it in one of the
``PATH`` directories.

For example, if ``~/bin`` is in your ``PATH``::

    $ ln -s ~/git/kernelconfig/kernelconfig.py ~/bin/kernelconfig
    $ kernelconfig


Throughout the following sections,
``<prjroot>`` will be used to refer to the project's source directory.

It accepts all of the `usual options`_, and additionally:

--wrapper-help

    Prints a help message describing the wrapper's options.

--wrapper-prjroot <PRJROOT>

    Path to the project's sources.

    If not specified, defaults to the directory containing the wrapper script.

--wrapper-build-base <BUILD_BASE>

    Root directory for build files, can also be specified via the
    ``PY_BUILDDIR`` environment variable.

    Defaults to ``<PRJROOT>/build``.

    The wrapper creates per-Python version subdirectories in
    ``<BUILD_BASE>/kernelconfig-standalone``.

--wrapper-lkc <LKC_SRC>

    Alternate path to lkc files from the Linux kernel sources.
    Must point to ``<linux srctree>/scripts/kconfig``
    and not just ``<linux srctree>``.
    Can also be specified via the ``LKCONFIG_LKC`` environment variable.

    Defaults to ``<PRJROOT>/src/lkc``,
    which contains a bundled copy of the necessary files.

--wrapper-rebuild

    Instructs the wrapper to rebuild Python modules
    by passing ``--force`` to ``setup.py build``.
    The wrapper tries to reuse existing modules
    if this option is not given.


.. _settings:

Settings File
-------------

The settings file is kernelconfig's main configuration file.
It is an ``.ini``-like file consisting of several sections.

Comment lines start with a ``#`` char,
empty lines and most whitespace are ignored.

Sections are introduced with ``[<section name>]``, e.g. ``[source]``.
Unknown sections are ignored.
The format inside each section varies, the following table gives
a quick overview of all sections and their respective format:

.. table:: settings file sections

    +-----------------+-----------------+-------------------------------------+
    | section name    | section format  | short description                   |
    +=================+=================+=====================================+
    | source          | *unspecified*   | input ``.config``                   |
    +-----------------+-----------------+-------------------------------------+
    | options         | macros          | ``.config`` modifications           |
    +-----------------+-----------------+-------------------------------------+


Settings Directories
++++++++++++++++++++

Settings files are usually given by name and are searched for in some
standard directories. The list of these directories varies depending
on whether kernelconfig has been installed or is run in standalone mode.

If kernelconfig has been installed, the directories are as follows::

    $HOME/.config/kernelconfig
    /etc/kernelconfig

In *standalone* mode, the settings directories are::

    $HOME/.config/kernelconfig
    <prjroot>/local/config
    <prjroot>/config


The directories are searched in the order as listed,
and searching stops immediately if a file with the requested name is found.

Settings files should never be named ``include`` or ``data``,
these names are reserved for other purposes.


\[source\]
++++++++++

The ``[source]`` section is used to declare
the input kernel configuration file,
which can be a regular file, a ``make`` target or refer to a *curated source*.

.. Warning::

    ``[source]`` is not implemented yet.

    For now, leave this section empty and use the ``--config`` command line
    option, which supports regular files only.


\[options\]
+++++++++++

The ``[options]`` section should contain a list of config-modifying commands::

    disable            A
    builtin            B
    module             C
    builtin-or-module  D E F

    set                G "value"
    append             H "value"
    add                I "value"

Config option names are case-insensitive
and the ``CONFIG_`` prefix can be omitted.
The first group of commands accepts an arbitrary non-zero
number of config options.

It also possible to load so-called *feature set* files::

    include  feature
    include  feature-dir/*
    include  /path/to/feature/file

The format of *feature set* files is identical
to that of the ``[options]`` section.
Basically, settings files can be viewed as extended *feature set* files.

Relative file paths are looked up in the ``include`` subdirectories
of the `settings directories`_.
Globbing is supported and expands to a combined list of glob matches
from all directories, but with the usual order of preference.

See `macros file format`_ for a more detailed explanation of the format.
