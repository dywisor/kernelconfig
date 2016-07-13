.. _toposort:
    https://pypi.python.org/pypi/toposort/

.. _ply:
    https://pypi.python.org/pypi/ply/

.. _Python String Formatting:
    https://docs.python.org/3/library/string.html#format-string-syntax

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

This is not possible yet,
kernelconfig can only be run in `standalone mode`_ for now.


Dependencies
++++++++++++

Required:

* Python >= 3.4, or Python 3.3 with backports: enum

* `toposort`_

* Python Lex-Yacc (`PLY`_)

* GNU make

* git for various configuration sources

* C compiler, ...


Optional, but recommended:

* Python modules: lxml and beautifulsoup (>= 4),
  for the Ubuntu configuration source

* perl,
  for the Fedora configuration source


Optional:

* Linux kernel sources for copying certain files from ``scripts/kconfig``,
  a bundled copy is used otherwise


Running kernelconfig
--------------------

In the simplest case,
run :code:`kernelconfig` without any arguments
from within the kernel sources directory.
It uses the ``default`` `settings`_ and creates a ``.config`` file.

.. N.B:

    ==comment== only works if $PWD is the top-level kernel source directory


It is also possible to specify the kernel sources directory by hand,
creating the ``.config`` file in this directory::


    $ kernelconfig -k /usr/src/linux


Or write the configuration to a different output file::

    $ kernelconfig -O ./my_config


Instead of using a *configuration source*,
an input config file can be given on the command line::

    $ kernelconfig --config ./my_config


The input and output config file can point to the same file.
Prior to writing the output file,
a backup of the old file is created (``<output>.bak``).

The target architecture is usually determined by ``uname -m``.
For cross-compilation scenarios, it is possible to specify it manually::

    $ kernelconfig -a arm


To get an overview over which *configuration sources* are available,
kernelconfig offers a few helper commands.

To get a list of all known *configuration sources*, run::

    $ kernelconfig --list-source-names

or::

    $ kernelconfig --list-sources


This list includes unvailable sources,
e.g. sources that do not support the target architecture.

To print out help messages for all available sources, run::

    $ kernelconfig --help-sources


To print out the help message for a particular source,
and also report why the source is unavailable (if it is unavailable),
e.g. for Fedora, run::

    $ kernelconfig --help-source Fedora -a mips


.. _usual options:

kernelconfig accepts a number of options:

-h, --help

    Print the help message and exit.

--usage

    Print the usage message and exit.

-V, --print-version

    Print the version and exit.

-q, --quiet

    Decrease the console log level.

    This option can be given multiple times,
    each time it decreases the log level by 1,
    and the effective log level is calculated using
    ``WARNING + (quiet - verbose)`` (higher level means less verbosity).

-v, --verbose

    Increase the console log level.

    Can be specified more than once, see ``--quiet`` for details.

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

    An input configuration file that should be used
    instead of the source configured in the settings file.

    Not set by default.

-O <file>, --outconfig <file>

    The output .config file.

    Defaults to ``<srctree>/.config``.


--generate-config
    Generate a kernel configuration. This is the default mode.

--list-source-names
    List the names of all known configuration sources.
    The information is based on file-exists checks and may be inaccurate.

    No configuration file is generated when this mode is requested.

--list-sources
    List the names of all known configuration sources
    alongside with their filesystem path.
    The information is based on file-exists checks and may be inaccurate.

    No configuration file is generated when this mode is requested.

--help-sources
    Print out help messages for all supported configuration sources
    that did successfully load.
    The information is accurate,
    but varies depending on which ``--arch`` has been specified.

    No configuration file is generated when this mode is requested.

--help-source <name>
    Print out the help message for a single configuration source
    if it is supported and did successfully load.
    Otherwise, print out why it is unavailable.

    No configuration file is generated when this mode is requested.

--script-mode <mode>
    As an alternative to the options above,
    the script mode can be given via this option.

    ``<mode>`` must be either
    ``generate-config``,
    ``list-source-names``, ``list-sources``, or ``help-sources``.

    ``help-source`` can not be specified with this option.



.. _standalone mode:

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
    | source          | command         | input ``.config``                   |
    |                 | + text data     |                                     |
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
the input kernel configuration file.
If a config file has been specified with the ``--config`` option,
then the section is ignored.

kernelconfig needs a *configuration basis* to operate on.
It is served by a *configuration source*
and can be a single ``.config`` file or multiple files

The first non-comment, non-empty line specifies the *configuration source*.
It starts with a keyword describing the source's type,
which can be a local file,
a remote file that can be downloaded via http(s) or ftp,
a ``make defconfig`` target, a command or a script,
and is followed by arguments such as the file path.
The type keyword can be omitted
if the specified configuration source is unambiguous.

It can also point to a *curated source*,
which is a *configuration source* that exists separately from the settings
file, in the ``sources`` subdirectory of the settings directories.
Curated sources behave similar to commands in that they accept parameters,
but their execution, especially argument parsing,
is controlled by kernelconfig.

Except for *curated sources*,
the *configuration source* line gets string-formatted,
see the examples below, or `Python String Formatting`_.
While this allows for some variance in file paths and commands,
it also requires to escape ``{`` and ``}`` characters,
especially for shell scripts.
``${var}`` needs to be written as ``${{var}}``, for instance.

Line continuation can be used to split long commands over multiple lines,
with a backslash ``\\`` at the end each line except for the last one.

Subsequent non-comment lines form the source's data.
Whether the data subsection is subject to string formatting or not depends on
the configuration source type.
Only script-type configuration sources accept non-empty data.


Using a curated source
^^^^^^^^^^^^^^^^^^^^^^

Example::

    [source]
    ubuntu --lowlatency


Curated sources are referenced by their name,
which is case-insensitive [*]_.
Their type keyword is ``source``, it can be omitted
unless the source's name itself is a keyword.

.. [*] names are converted to lowercase before searching for the source

Curated sources usually accept a few parameters
for selecting the configuration basis variant.

As outlined before, kernelconfig has more control over curated sources
than over configuration sources specified in the settings file.
For example, kernelconfig checks whether the target architecture is
supported by the source, and refuses to continue if not.

Run ``kernelconfig --list-sources``
to get a list of potential curated source names.
and ``kernelconfig --help-source <name>``
provides information about a particular source, including its parameters.

Currently, the following curated sources are available:

CentOS

    Supported architectures: ppc64, ppc64le, s390x, x86, x86_64

    Parameters:

        --debug
            Use the ``-debug`` config variant
        --release
            CentOS has per OS-release git branches that correspond to
            a specific kernel version.
            By default, the configuration source tries to identify
            the best-fitting branch, but this option can be used to override
            the auto detection.

Debian

    Supported architectures: x86, x86_64

    Parameters:

        --flavour <flavour>
            Debians kernel ecosystem distinguishes between specialized
            variants of architectures, so-called *flavours*,
            which can be specified with this option.
        --featureset <featureset>
            For some architectures, Debian has config variants that
            enable an additional feature.
            Supported feature sets depend on the target architecture
            and ``--flavour``.
            Possible values are ``rt``, ``none`` and the empty string.


    .. Note::

        The supported architectures mapping for Debian is incomplete.
        The underlying script is able to handle other architectures
        (it has been tested with various mips arch flavours).

Fedora

    Supported architectures:
    aarch64, arm, arm64, armv7hl, s390, s390x, x86, x86_64

    Parameters:

        --pae
            Use the config variant with support for
            Physical Address Extensions (32-bit x86 only)
        --lpae
            Use config variant with support for
            Large Physical Address Extensions (arm only)
        --debug
            Use the ``-debug`` config variant
        --release
            Fedora has per OS-release git branches that correspond to
            a specific kernel version.


Liquorix

    Supported architectures: x86, x86_64

    Parameters:

        --pae
            Use the config variant with support for
            Physical Address Extensions (32-bit x86 only)

Ubuntu

    Supported architectures: arm64, armhf, x86, x86_64

    Parameters:

        --lowlatency
            Use the low-latency config variant (x86, x86_64 only)
        --generic
            Use the generic config variant (which is the default)
        --lpae
            Use config variant with support for
            Large Physical Address Extensions (arm only)



Using defconfig as configuration source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run ``make defconfig`` with a temporary directory
as output directory, and use the generated file as input config file::

    [source]
    defconfig


The type keyword is ``defconfig``, and no parameters are accepted.


Using a file as configuration source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use a local file named ``config_<arch>`` found in the ``sources/files``
subdirectory of the settings directories::

    [source]
    file config_{arch}


It is also possible to download file via http/https/ftp, for example::

    [source]
    http://.../{kv}/config.{arch}


Absolute file paths and file uris starting with ``file://``
are understood, too.

The type keyword is ``file`` and it can be omitted for absolute file paths
and file uris,
but not for relative file paths as that interferes with curated sources.

Besides the file path, no other parameters are accepted.
The path is subject to basic `string formatting`_.


Using a command as configuration source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example::

    [source]
    command wget http://... -O {outconfig}

The type keyword is ``command`` or alternatively ``cmd``,
and it can not be omitted.

All arguments after the keyword are subject to `string formatting`_,
automatic format variables are supported.
Additionally, commands have to access to the
`config source environment variables`_.

The initial working directory is a temporary directory
which is cleaned up by kernelconfig.
If no config file is referenced via
the automatic ``{outconfig}``, ``{out}`` format variables,
kernelconfig expects that the command
creates a ``config`` file in the temporary directory.


Using a script as configuration source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download a tarball,
extract it to a temporary directory,
and pick some of its files as input config::

    [source]
    sh
    wget http://.../file.tgz
    tar xf file.tgz -C '{T0}'
    cp '{T0}/config.common' '{out}'
    for a in {arch} {karch} _; do
        if [ "$a" = "_" ]; then
            exit 1
        elif [ -e "{T0}/config.$a" ]; then
            cat "{T0}/config.$a" >> '{out}'
            break
        fi
    done

The type keyword is ``sh`` for shell scripts,
which are run in errexit mode (``set -e``).

The data subsection contains the script, and it must not be empty.

The script is subject to `string formatting`_,
automatic format variables are supported.
Additionally, the script has access to the
`config source environment variables`_.

The initial working directory is a temporary directory
which is cleaned up by kernelconfig.
If no config file is referenced via
the automatic ``{outconfig}``, ``{out}`` format variables,
kernelconfig expects that the script
creates a ``config`` file in the temporary directory.


.. _config source environment variables:

Configuration Source Environment Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Commands, including scripts,
have access to the following environment variables:

.. table:: configuration source environment variables

    +------------------+-------------------------------------------+
    | name             |  description                              |
    +==================+===========================================+
    | S                | path to the kernel sources                |
    +------------------+                                           |
    | SRCTREE          |                                           |
    +------------------+-------------------------------------------+
    | T                | private temporary directory               |
    |                  |                                           |
    +------------------+-------------------------------------------+
    | TMPDIR           | temporary directory                       |
    |                  | (same as ``T``)                           |
    +------------------+-------------------------------------------+
    | ARCH             | target architecture as specified          |
    |                  | on the command line, or ``$(uname -m)``   |
    +------------------+-------------------------------------------+
    | KARCH            | target kernel architecture                |
    |                  |                                           |
    |                  | For instance, if ``ARCH`` is ``x86_64``,  |
    |                  | ``KARCH`` would be ``x86``.               |
    +------------------+-------------------------------------------+
    | SUBARCH          | *underlying kernel architecture*          |
    |                  |                                           |
    |                  | Usually equal to ``KARCH``.               |
    +------------------+-------------------------------------------+
    | SRCARCH          | target kernel source architecture         |
    |                  |                                           |
    |                  | Usually equal to ``KARCH``.               |
    +------------------+-------------------------------------------+
    | KVER             | full kernel version, e.g.                 |
    |                  | ``4.7.0-rc1``, ``3.0.0``, ``4.5.1``       |
    +------------------+-------------------------------------------+
    | KV               | full kernel version without patchlevel    |
    |                  | unless it is an ``-rc`` version,          |
    |                  | e..g ``4.7.0-rc1``, ``3.0``, ``4.5``      |
    +------------------+-------------------------------------------+
    | KMAJ             | kernel version,                           |
    |                  | e.g. ``4``, ``3``, ``4``                  |
    +------------------+-------------------------------------------+
    | KPATCH           | kernel version patchlevel,                |
    |                  | e.g. ``7``, ``0``, ``5``                  |
    +------------------+-------------------------------------------+
    | KMIN             | kernel version sublevel,                  |
    |                  | e.g. ``0``, ``0``, ``1``                  |
    +------------------+-------------------------------------------+


.. _string formatting:

Configuration Source Format Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All basic source types are subject to Python string formatting.

The available format variables are identical to the environment variables,
except for ``TMPDIR`` (not set) and  ``T`` (special, see below).
Unlike the environment variables, the names of format variables
are case-insensitive, e.g. both ``{kv}`` and ``{KV}`` are accepted.

Additionally, the ``script`` and ``command`` type config sources
support *automatic format variables*,
which can be used to request additional temporary directories and files
and to tell kernelconfig where the ``.config`` file(s) can be found
after processing the configuration source,
without having to specify a filesystem path.

There is no guarantee that filesystem paths produced by automatic format
variables do not require quoting in e.g. shell scripts,
so make sure to quote the automatic variables where appropriate.

*Automatic format variables* start with a keyword
and are optionally followed by an integer identifier,
which can be used to request additional files of the same type.

The following variables exist:

``outconfig`` or ``out``
    Request a temporary file
    and tell kernelconfig that it will be part of the configuration basis.

    The identifier can be used to request additional files.
    Note that ``{out}`` and ``{outconfig}`` will point to distinct files,
    and so do ``{out},  {out0}, {out00}, ..., {out9}, ...``.

``outfile``
    Request a temporary file
    that will not be part of the configuration basis.

    Otherwise, identical to ``outconfig``.

``T``
    Request a temporary directory.

    If used without an identifier, request the default private tmpdir.
    If used with an identifier, creates a new directory.





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
