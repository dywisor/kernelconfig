.. _toposort:
    https://pypi.python.org/pypi/toposort/

.. _ply:
    https://pypi.python.org/pypi/ply/

.. _Python String Formatting:
    https://docs.python.org/3/library/string.html#format-string-syntax

.. _Gentoo Bug \#217042:
    https://bugs.gentoo.org/show_bug.cgi?id=217042

.. _layman:
    https://wiki.gentoo.org/wiki/Layman

.. _kernelconfig:
.. _kernelconfig git repo:
.. _git repo:
    https://github.com/dywisor/kernelconfig

.. _kernelconfig\-portage:
    https://github.com/dywisor/tlp-portage

.. _GNU Coding Standards\: Directory Variables:
    https://www.gnu.org/prep/standards/html_node/Directory-Variables.html

.. _macros file format:
    macros_lang.rst

.. sectnum::

.. contents::
   :backlinks: top


kernelconfig
============

Generate Linux kernel configuration files from curated sources,
detected hardware, installed packages and user input.


Introduction
------------



Installing kernelconfig
-----------------------


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

* portage for *package management integration*

* kmod with Python bindings
  for hardware detection based on module aliases

* Python modules: lxml and beautifulsoup (>= 4),
  for the Ubuntu configuration source

* perl,
  for the Fedora configuration source


Optional:

* Linux kernel sources for copying certain files from ``scripts/kconfig``,
  a bundled copy is used otherwise


via emerge (Gentoo)
+++++++++++++++++++

A live ebuild for ``sys-kernel/kernelconfig``
is available in the `kernelconfig-portage`_ overlay.

To add it with `layman`_, run::

    $ layman -o "https://raw.githubusercontent.com/dywisor/kernelconfig-portage/master/layman.xml" -f -a kernelconfig

The live ebuild needs to be ``KEYWORDS``-unmasked::

    $ mkdir -p /etc/portage/package.accept_keywords
    $ echo "~sys-kernel/kernelconfig-9999 **" >> /etc/portage/package.accept_keywords/kernelconfig

It can then be installed with::

    $ emerge -a sys-kernel/kernelconfig


Manual Installation
+++++++++++++++++++

First, make sure to install the `dependencies`_.

After that, clone the `git repo`_ and
change to working directory to kernelconfig's sources::

    git clone git://github.com/dywisor/kernelconfig.git

    cd kernelconfig

Then, prepare the build by creating an *installinfo* file,
which tells kernelconfig where to find its config and data files, once installed.
This can be done with ``make prepare-installinfo``,
it should receive the same variables as ``setup.py install``
and ``make install`` later on (except for ``DESTDIR``)::

    PREFIX=/usr/local   # default: /usr/local
    SYSCONFDIR=/etc     # default: /usr/local/etc

    make prepare-installinfo PREFIX="${PREFIX}" SYSCONFDIR="${SYSCONFDIR}"

Building requires a copy of some files from the Linux kernel sources.
At this point, it is necessary to decide whether to use the bundled copy
distributed with kernelconfig, which is recommended,
or to import the files from a kernel source tree.

To use the bundled lkc files, export ``LKCONFIG_LKC``::

    export LKCONFIG_LKC="src/lkc-bundled"

Alternatively, to import the lkc files from a kernel source tree, run::

    make import-lkc LK_SRC=/usr/src/linux
    #export LKCONFIG_LKC="src/lkc"  # not necessary


After preparing *installinfo* and the lkc files,
build kernelconfig with ``setup.py``::

    python ./setup.py build

This step can be repeated in case of multiple Python versions.


Finally, kernelconfig can be installed.
The python files are installed with ``setup.py``,
and the data and config files with ``make``::

    # install
    DESTDIR=/
    python ./setup.py install --root "${DESTDIR}" --prefix "${PREFIX}"
    make install-data install-config DESTDIR="${DESTDIR}" PREFIX="${PREFIX}" SYSCONFDIR="${SYSCONFDIR}"

The install-related ``make`` variables
follow the `GNU Coding Standards\: Directory Variables`_,
except that the names are in uppercase.
See ``mk/install.mk`` for a list of variables.


.. _standalone mode:

Running kernelconfig without installing it
++++++++++++++++++++++++++++++++++++++++++

kernelconfig can be run in *standalone* mode from the project's sources.
For this purpose, it offers a wrapper script named ``kernelconfig.py``
that takes care of running ``setup.py`` and invoking the main script.

First, get the sources by cloning the `git repo`_::

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



Running kernelconfig
--------------------

In the simplest case,
run :code:`kernelconfig` without any arguments
from within the kernel sources directory.
It uses the ``default`` `settings`_ and creates a ``.config`` file.

.. N.B:

    ==comment== only works if $PWD is the top-level kernel source directory

It is **not advised to run kernelconfig as root**.
Certain features involve execution of arbitrary code,
namely configuration sources and package management integration.
Write access to the kernel sources directory is not required,
provided that ``--outconfig`` points to another location.

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

--config <source>

    Instead of a file, the `name of a curated source`_ prefixed
    with an at-sign ``@`` may also be given, optionally followed
    by parameters separated with whitespace,
    that are passed as-is to the configuration source.

    If parameters are specified, the ``<source>`` must be quoted.

    Examples::

            --config @ubuntu
            --config "@fedora --pae --release f23"

    See ``--list-sources`` for a complete list of available configuration
    sources, and ``--help-source <name>`` for parameters supported by
    a particular source.

-I <file>

    File with additional kernel configuration modifications.
    The file format is identical to the that of the `\[options\]`_ section
    of the settings file, which also allows ``.config`` snippets.

    Can be specified more than once. Not set by default.

-O <file>, --outconfig <file>

    The output .config file.

    Defaults to ``<srctree>/.config``.

-H <file>, --hwdetect <file>

    Enable hardware detection and read the information from a *hwinfo* file
    as created by `hwcollector`_.

    Disables any other hardware detection,
    in particular ``hwdetect`` instructions in the `\[options\]`_ section
    of the settings file.

    Not set by default.

-m <mod_dir>, --modules-dir <mod_dir>

    The `modalias information source`_
    which is used for modaliased-based hardware detection.
    It can be

    * a path to a directory, e.g. ``/lib/$(uname -r)/modules``

    * a path to a tarball file

    * ``none``,
      which disables modalias-based hardware detection completely

    * ``auto``,
      which requires a cached *modalias information source*
      that has previously been created with ``--generate-modalias``.

    * ``optional``,
      which uses a cached *modalias information source* if there is one
      available, and otherwise disables modalias-based hardware detection

    Defaults to ``optional``.

--unsafe-modalias

    Controls how strict cache searching is
    for ``--modules-dir auto`` and ``optional``.
    If this option is given, less compatible *modalias information sources*
    are allowed if no better candidates exist.

    The default behavior is ``--safe``.

--safe-modalias

    Forbid use of unsafe *modalias information sources*.

--generate-config
    Generate a kernel configuration. This is the default mode.

--get-config

    Retrieve the input configuration, but do not generate a configuration.
    Instead, write the input configuration to ``--outfile`` directly.

    This mode is only meaningful for configuration sources
    that are not local files.

    Together with ``--config @<name>``,
    it can be used for testing out configuration sources.

.. _\-\-generate\-modalias:

--generate-modalias

    Create a *modalias information source* and store it in the cache directory.
    It can then be used for modalias-based hardware detection
    in subsequent runs, or shared with others.

    .. Warning::

        *modalias information source* involves building all kernel modules
        with an ``allmodconfig`` configuration, which takes a lot of time
        and about 2GiB of temporary disk space.
        kernelconfig will try to use ``/var/tmp`` if ``/tmp`` does not have
        enough free space, and ``--modalias-build-dir`` can be used
        to specify an alternate build root directory.

        By default, up to ``number of CPU cores`` build jobs are used
        for compiling, this can be adjusted with ``--jobs``.

-j <numjobs>, --jobs <numjobs>

    Allow up to ``<numjobs>`` build jobs when building modules.

    Defaults to the number of processor cores.

--modalias-build-dir <dir>

    Alternative build root directory for *modalias information source*
    building.
    kernelconfig creates a temporary subdirectory within this directory,
    and cleans it up on exit.

    By default, building takes place in ``/tmp`` or ``$TMPDIR``, if set.
    ``/var/tmp`` is used as fallback
    if ``/tmp`` does not have enough free space.

--print-installinfo
    List the directory paths where kernelconfig looks for settings,
    include files, configuration sources, cached and data files,
    alongside with their overall status (exists/missing).

    The paths are grouped (``settings:``, ``include`` a.s.o.),
    and are printed in descending order of priority.

    No configuration file is generated when this mode is requested.

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
    ``get-config``,
    ``generate-modalias``,
    ``print-installinfo``,
    ``list-source-names``, ``list-sources``, or ``help-sources``.

    ``help-source`` can not be specified with this option.



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

.. _name of a curated source:

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

.. N.B: kernel sources only::

Config options can also be referenced by their module name, for example::

    builtin-or-module module ddbridge   # enables DVB_DDBRIDGE

`Hardware detection`_ can be requested with ``hwdetect``, however
it has no effect if the ``--hwdetect`` option is passed to kernelconfig::

    hwdetect

Config recommendations from installed packages can be requested with
``packages``.
The recommendations can be based on what was present at package build-time::

    packages build-time

or re-evaluated against the kernel sources for which a configuration
is being created::

    packages
    # packages re-eval  # alternatively

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



Hardware Detection
------------------

kernelconfig is able to determine which hardware is present on the system
and enable config options accordingly.

This feature can be requested with ``hwdetect`` in the `\[options\]`_ section
of the settings file, or with the ``--hwdetect <file>`` command line option.
The latter is meant for
`collecting hardware information on a different machine`_.

In either case, it relies on at least one *hardware information source*
and a mapping from hardware identifiers to config options,
which is created at runtime from the kernel sources being processed.

Two different *hardware information source* are available:

* **driver**
  \- detect which kernel modules are currently used by any device

* **modalias**
  \- detect kernel modules for all device via module alias identifiers

kernelconfig uses whatever source is available
and potentially both *driver*- and *modalias*-based detection.
The hardware identifiers are translated into config options,
which are enabled as *builtin* or *module*, and *module* is preferred.

If hardware detection has been requested and at least one hardware identifier
has been found but no config options could be determined,
then hardware detection is considered to have failed.


**driver**-based hardware detection has no special requirements except
that modules for ideally all devices must be present and loaded (or builtin).
This can work sufficiently well when a "big" kernel has been booted
and a kernel configuration is being created for the same machine.

Otherwise, **modalias**-based hardware detection provides a more accurate
selection of config options that also includes options for unknown devices,
but requires a *modalias information source*.



Modalias Information Source
+++++++++++++++++++++++++++

A *modalias information source* is, basically, a very reduced variant
of a modules directory that would normally be installed to ``/lib/modules``.
The most important file provided by this source is ``modules.alias``,
a *ideally complete* mapping from module alias identifiers to modules.

*modalias information sources* as used by kernelconfig can be directories,
but are usually xz-compressed tarballs that are kept in the
*modalias cache directory*, ``$HOME/.cache/kernelconfig/modalias``.

When kernelconfig is requested to locate a cached source,
it will by default only look for sources that have been built for the
same target architecture or at least for the same ``SUBARCH``.
Furthermore, the kernel version of the cached source must have the same
major version and the version difference must not exceed 8 patchlevels.
This is the so-called *safe* mode (``--safe-modalias``).

In *unsafe* mode,
the kernel's major version must be equal but is otherwise unrestricted,
and cached sources for different target architectures are considered,
though not preferred.
This mode has to be explicitly enabled with ``--unsafe-modalias``.

A new *modalias information source* can be created with::

    kernelconfig --generate-modalias -k /usr/src/linux


This will build all kernel modules using an ``allmodconfig`` configuration
install them to a temporary directory, run depmod
and create a tarball with the relevant files,
which is stored in the cache directory as
``$HOME/.cache/kernelconfig/modalias/{kernelversion}__{arch}.txz``,
for example ``$HOME/.cache/kernelconfig/modalias/4.6.5__x86_64.txz``.

The tarballs can be shared with others.
Since there is no convenient way to import shared tarballs [yet],
they have to specified with the ``--modules-dir`` option
or copied to the cache directory manually.

Be aware of the time and disk space requirements,
which are covered in `--generate-modalias`_.


.. _hwcollector:

Collecting Hardware Information on a Different Machine
++++++++++++++++++++++++++++++++++++++++++++++++++++++

Hardware detection is not limited to the machine running kernelconfig,
it is also possible to scan for hardware identifiers on another machine.

.. Note::

   modalias-based hardware detection is recommended for this use case.

Example scenarios include booting a live system on the *target* machine,
for example SystemRescueCd, detecting its hardware and sending the information
to the *build* machine, which then feeds kernelconfig with the data.
Another example would be a minimal busybox-based initramfs booted via PXE
that serves the hardware information via netcat.

For this purpose, kernelconfig offers a ``hwcollect`` shell script,
which can be found under ``files/scripts/hwcollect.sh``
in the project's sources.
It scans ``/sys`` and creates a JSON file containing the information,
which is written to stdout,
and can be fed to kernelconfig with the ``--hwdetect`` option.

Under normal circumstances, the script can be run by regular users.
An exception to that is grsec ``/sys`` protections.

If the *build* machine is able to access the *target* machine via ssh
as user ``hwcol`` and the script is installed on the *target*,
the commands for generating a configuration for *target*
with hardware detection would be::

    [build] $ ssh -l hwcol target kernelconfig-hwcollect > ./hwinfo.json
    [build] $ kernelconfig -H ./hwinfo.json ...


It is also possible to send the script to the target machine via ssh::

    [build] $ cd <prjroot>
    [build] $ < ./files/scripts/hwcollect.sh ssh -l hwcol target sh > ./hwinfo.json
    [build] $ kernelconfig -H ./hwinfo.json ...


The script's dependencies are a few basic programs including a shell,
``/sys`` and ``/proc`` mounted, and a way to transfer files from the
target machine to the build machine.


hwinfo file
^^^^^^^^^^^

The hardware information file is a JSON object with dummy null-terminates
that lists which kernel modules and module alias identifiers have been
detected on the *target* machine:

.. code:: json

    {
        "version": 1,
        "driver": [
            ...,
            ""
        ],
        "modalias": [
            ...,
            ""
        ],
        "__null__": null
    }


The ``version`` tells kernelconfig the overall structure of the JSON object,
it has to be ``1``.

``driver`` is a list of kernel modules
that kernelconfig should enable after translating them to config options,
similar to driver-based hardware detection.

``modalias`` is a list of module alias identifiers
that kernelconfig should enable after translating them to config options.

``__null__`` is completely ignored, as are empty strings in lists.
JSON list/object items need to be separated with a comma,
but a comma after the last item is not allowed.
By using dummy null values,
this detail can be mostly ignored in the collector script,
with a small file size overhead of one dummy item per list/object.



Package Management Integration
------------------------------

Installed packages can serve as source for config option recommendations.
This feature relies on packages being managed by portage,
and can be requested with ``packages`` in the `\[options\]`_ section
of the settings file.

Two variants of *pm-integration* are available, *static* and *dynamic*,
both query the value of the ``CONFIG_CHECK`` variable from installed packages,
but to a different extent.

*static pm-integration* uses the package build-time value of ``CONFIG_CHECK``,
which can be retrieved quickly, but is not reliable,
because ``CONFIG_CHECK`` could have been set conditionally,
e.g. by comparing the kernel version
against the kernel sources being present at package build time.

For that reason, a more reliable but also more (time-)complex solution exists,
*dynamic pm-integration*, which re-evaluates ``CONFIG_CHECK``
by running the relevant ebuild phases again.

Either variant transforms ``CONFIG_CHECK`` into a sequence of
*enable option as builtin or module* and *disable option* config modifications.
Unknown config options listed in ``CONFIG_CHECK`` are ignored.

.. Warning::

    *dynamic pm-integration* runs the ``pkg_setup()`` ebuild phase
    for all installed packages that inherit ``linux-info.eclass``,
    as regular user.

    Since ``pkg_setup`` can do arbitrary things like creating users,
    this can fail for individual packages, in which case kernelconfig
    prints a warning message  and tries to use the information gathered
    from running the ebuild so far.

    #. It is very unlikely that the failure is caused by kernelconfig,
       more likely the ebuild is doing things in ``pkg_setup()``
       that should be handled during ``pkg_postinst()`` or ``pkg_preinst()``

    #. Do not run kernelconfig as root,
       especially when using *dynamic pm-integration*!

    For ``enewuser/enewgroup`` related failures, see `Gentoo Bug \#217042`_.



Curated Sources
---------------

This section covers how to add new *curated sources* to kernelconfig.

As previously noted,
the purpose of configuration sources is to provide a *configuration basis*,
a non-empty list of files that is used as input ``.config``.

*Curated sources* are configuration sources
that exist separately from the settings file,
in the ``sources`` subdirectory of the settings directories.

A curated source consists of

* a script ``sources/<name>`` (*script only*)

* a *source definition file* ``sources/<name>.def`` (*sourcedef only*)

* a *source definition file* ``sources/<name>.def``
  plus a script ``sources/<name>`` (*sourcedef with script*)
  or a Python module ``sources/<name>`` (*sourcedef with pym*)


Script-Only Curated Sources
+++++++++++++++++++++++++++

The simplest case is *script only*,
which is limited to single-file configuration bases.
Just put a script in ``<settings>/source``, e.g.
``$HOME/.config/kernelconfig/sources/my_source``,
and make it executable.

It can then be referenced in the settings file with::

    [source]
    my_source

When run,
it receives a file path to which the configuration basis
should be written to as first argument,
the target architecture as second argument,
and the short kernel version (kernel version and patchlevel, e.g. ``4.1``)
as third argument.
Parameters from the settings file are passed as-is to the script,
starting at the fourth argument::

    my_source {outconfig} {arch} {kmaj}.{kpatch} ...

The script has also access to the `config source environment variables`_.


At some point, it might be useful
to restrict the accepted architectures to what is actually supported
and provide a more meaningful help message
when ``kernelconfig --help-source my_source`` is run.

This can be done by creating a ``my_source.def`` source definition file
in the same directory with the following content::

    [source]
    Architectures = x86_64

    # use the script-only script calling convention,
    #  which passes all unknown parameters as-is to the script
    PassUnknownArgs = 1

    Description = my source is ...


Source Definition File
++++++++++++++++++++++

Curated sources that are not script-type sources,
or sources that want to benefit from argument parsing,
need to be described in a source definition file.

Source definition files reside in the same directory as scripts,
and their filename must end with ``.def``.

.. _Liquorix Example:

Example: Liquorix (``sources/liquorix.def``)::

    [source]
    Name = Liquorix

    Architectures = x86_64 x86
    Features = pae

    Type = file
    Path = http://liquorix.net/sources/{kmaj}.{kpatch}/config.{param_arch}{param_pae}

    Description =
      Liquorix is a distro kernel replacement built using the best configuration
      and kernel sources for desktop, multimedia, and gaming workloads.

    [Arch:x86_64]
    Value = amd64

    [Arch:x86]
    Value = i386

    [Feature:PAE]
    Arch = x86
    Value = -pae
    Description = enable Physical Address Extensions ...

Liquorix supports 32-bit and 64-bit x86 architectures
and has a ``-pae`` config variant for 32-bit x86.
The config file can be downloaded via http,
and the url can be constructed with the information
from the source definition file.

The ``Description`` options are used for creating the help message that can
be viewed with ``kernelconfig --help-source liquorix``.

|

The source definition file is an ini file.
Empty lines are ignored, comment lines start with ``#``,
sections are introduced with ``[<name>]``,
and options are set with ``<option> = <value>``.
Option and section names are case-insensitive.
Long values can span over multiple lines by indenting subsequent lines
with whitespace.


The ``[source]`` section describes the source,
how to run it, and states which architectures and features are supported.

The following options are recognized in the ``[source]`` section:

.. table:: source definition ``[source]`` section options

    +-----------------+---------------+-----------+---------------------------------------+
    | field name      | value type    | required  | description                           |
    +=================+===============+===========+=======================================+
    | Name            | str           | *default* | Name of the curated source            |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to the name of the           |
    |                 |               |           | definition file (file suffix removed) |
    +-----------------+---------------+-----------+---------------------------------------+
    | Description     | str           | no        | Description of the curated source,    |
    |                 |               |           | for informational purposes            |
    +-----------------+---------------+-----------+---------------------------------------+
    | Type            | str           | *depends* | The type of the source,               |
    |                 |               |           | which can be                          |
    |                 |               |           |                                       |
    |                 |               |           | * file                                |
    |                 |               |           | * script                              |
    |                 |               |           | * pym                                 |
    |                 |               |           | * command                             |
    |                 |               |           | * make                                |
    |                 |               |           | * defconfig                           |
    |                 |               |           |   (*make* with ``Target=defconfig``)  |
    |                 |               |           |                                       |
    |                 |               |           | If not set, kernelconfig tries to     |
    |                 |               |           | autodetect the type:                  |
    |                 |               |           |                                       |
    |                 |               |           | * *script* if ``Path=`` is set,       |
    |                 |               |           |   or if a file with the source's      |
    |                 |               |           |   name was found in the ``sources``   |
    |                 |               |           |   directory,                          |
    |                 |               |           |                                       |
    |                 |               |           | * *command* if ``Command=`` is set    |
    |                 |               |           |   and does not reference the          |
    |                 |               |           |   ``{script_file}`` format variable   |
    +-----------------+---------------+-----------+---------------------------------------+
    | Path            | format str    | *depends* | For file-type sources, this is the    |
    |                 |               |           | path to the config file and required. |
    |                 |               |           |                                       |
    |                 |               |           | For script- and pym-type sources,     |
    |                 |               |           | this is the path to the script        |
    |                 |               |           | or Python module, and optional.       |
    |                 |               |           | It defaults to                        |
    |                 |               |           | ``<settings dirs>/sources/<name>``    |
    |                 |               |           |                                       |
    |                 |               |           | Ignored for command and make.         |
    +-----------------+---------------+-----------+---------------------------------------+
    | Command         | format str    | *depends* | For command-type sources,             |
    |                 |               |           | this field specifies the command      |
    |                 |               |           | to be run and is mandatory.           |
    | *also*: Cmd     |               |           |                                       |
    |                 |               |           | For script-type sources,              |
    |                 |               |           | this field can be used to override    |
    |                 |               |           | the calling convention.               |
    |                 |               |           | It should include ``{script_file}``,  |
    |                 |               |           | which gets replaced with the          |
    |                 |               |           | script specified in ``Path``          |
    |                 |               |           |                                       |
    |                 |               |           | For make-type sources,                |
    |                 |               |           | this field can be used to pass        |
    |                 |               |           | additional arguments to the           |
    |                 |               |           | ``make`` command.                     |
    +-----------------+---------------+-----------+---------------------------------------+
    | Target          | str           | yes       | Target for make-type sources          |
    |                 |               |           |                                       |
    |                 |               |           | Not supported by defconfig-type       |
    |                 |               |           | sources.                              |
    +-----------------+---------------+-----------+---------------------------------------+
    | Architectures   | str-list      | no        | List of supported architectures       |
    |                 |               |           |                                       |
    | *also*: Arch    |               |           | Defaults to *all*.                    |
    +-----------------+---------------+-----------+---------------------------------------+
    | Features        | str-list      | no        | List of source variants               |
    |                 |               |           |                                       |
    | *also*: Feat    |               |           | Defaults to none (the empty string).  |
    +-----------------+---------------+-----------+---------------------------------------+
    | PassUnknown\    | bool          | no        | Controls whether unknown parameters   |
    | Args            |               |           | should be accepted. By default,       |
    |                 |               |           | kernelconfig refuses to operate when  |
    |                 |               |           | unknown parameters are encountered.   |
    |                 |               |           |                                       |
    |                 |               |           | For script-type sources,              |
    |                 |               |           | the unknown parameters are passed     |
    |                 |               |           | as-is after ``Command``.              |
    +-----------------+---------------+-----------+---------------------------------------+

|
|

If a list of supported architectures is specified,
all other architectures are considered unsupported for a particular source,
and kernelconfig refuses to operate.

Since naming of target architectures varies between sources,
``[Arch:<name>]`` sections can be used to provide a name mapping.
They only have one option, ``Value``, which sets the alternative name.

For example, ``x86_64`` is often named ``amd64``::

    [Arch:x86_64]
    Value = amd64

The *architecture-rename* sections are tried to match
with the most specific arch first (``$(uname -r)``, e.g. ``x86_64``),
and the most generic arch last (kernel arch, e.g. ``x86``).

For renaming ``x86`` to ``i386``, it is necessary to provide an empty
rename section for ``x86_64`` since the kernel architecture
is ``x86`` in both cases::

    [Arch:x86]
    Value = i386

    [Arch:x86_64]
    #Value = x86_64

Supported architectures can also be listed with the ``Architectures`` option
in the ``[source]`` section.

The renamed architecture is available via the ``{param_arch}``
format variable.
If rename action has been taken, ``{param_arch}`` equals ``{arch}``.

|
|

Each curated source has an argument parser that verifies and processes
the parameters it receives from the settings file.

By default, no parameters are accepted, unless ``PassUnknownArgs`` is true.

Configuration sources usually offer several config variants,
e.g. a ``debug`` variant or a ``PAE`` variant for ``x86``.
Such variants can be declared with ``[Feat:<name>]`` sections,
which are converted to ``argparse`` arguments
and can be specified in the settings file with ``--<name>``.

In the source definition file,
they are then available as ``param_{<name>}`` format variables
for options with *format str* values
Depending on the source type,
they can also be accessed via ``PARAM_{<NAME>}`` environment variables.

For script-type sources,
if no ``Command=`` has been specified in the ``[source]`` section,
the parameters are put in the default command
after the kernel version and before the unknown parameters::

    {script_file} {outconfig} {arch} {kmaj}.{kpatch} [<param>...] [<unknown>...]


A ``[Feat:<name>]`` section can contain the following options:

.. table:: source definition ``[Feature:<name>]`` section options

    +-----------------+---------------+-----------+---------------------------------------+
    | field name      | value type    | required  | description                           |
    +=================+===============+===========+=======================================+
    | Name            | str           | no        | Name of the parameter,                |
    |                 |               |           | for informational purposes.           |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to ``<name>``.               |
    +-----------------+---------------+-----------+---------------------------------------+
    | Description     | str           | no        | Description of the parameter,         |
    |                 |               |           | for informational purposes.           |
    +-----------------+---------------+-----------+---------------------------------------+
    | Dest            | str           | no        | Parameter group name,                 |
    |                 |               |           | parameters with the same ``Dest``     |
    |                 |               |           | are mutually exclusive.               |
    |                 |               |           |                                       |
    |                 |               |           | The group name is used as name        |
    |                 |               |           | for the format and environment        |
    |                 |               |           | variables.                            |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to ``<name>``.               |
    +-----------------+---------------+-----------+---------------------------------------+
    | Type            | str           | no        | The argument type of the parameter,   |
    |                 |               |           | which can be                          |
    |                 |               |           |                                       |
    |                 |               |           | * const                               |
    |                 |               |           |     parameter accepts no value        |
    |                 |               |           |     and a constant value (``Value``)  |
    |                 |               |           |     gets stored in ``Dest``           |
    |                 |               |           |     if the parameter is given,        |
    |                 |               |           |     and the default value             |
    |                 |               |           |     (``Default``) otherwise.          |
    |                 |               |           |                                       |
    |                 |               |           | * optin                               |
    |                 |               |           |     Similar to *const*,               |
    |                 |               |           |     stores ``y`` and defaults to      |
    |                 |               |           |     the empty string                  |
    |                 |               |           |                                       |
    |                 |               |           | * optout                              |
    |                 |               |           |     Similar to *const*,               |
    |                 |               |           |     stores the empty string           |
    |                 |               |           |     and defaults to ``y``.            |
    |                 |               |           |                                       |
    |                 |               |           | * arg                                 |
    |                 |               |           |     parameter accepts one value       |
    |                 |               |           |     and stores it in ``Dest``,        |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to *const*.                  |
    +-----------------+---------------+-----------+---------------------------------------+
    | Default         | str           | no        | Default value if the parameter        |
    |                 |               |           | is not specified.                     |
    |                 |               |           |                                       |
    |                 |               |           | Only meaningful for *const*- and      |
    |                 |               |           | *arg*-type parameters.                |
    |                 |               |           |                                       |
    |                 |               |           | Defaults to the empty string.         |
    +-----------------+---------------+-----------+---------------------------------------+
    | Value           | str           | no        | Value gets set if the parameter       |
    |                 |               |           | is given                              |
    |                 |               |           |                                       |
    |                 |               |           | Only meaningful for *const*-type      |
    |                 |               |           | parameters, in which case it defaults |
    |                 |               |           | to ``--<name>``.                      |
    +-----------------+---------------+-----------+---------------------------------------+

|
|

Another section exists that is only relevant to ``pym``-type sources,
``[Config]``.
It can be accessed by the source via ``env.get_config(<option>)``,
which options are recognized is therefore up to the source.



Python-Module Configuration Sources
+++++++++++++++++++++++++++++++++++

Python-Module Configuration Sources gain access
to kernelconfig's functionality such as error reporting and logging,
and also temporary files/directories, file downloading and git repo handling.

A python module source must implement a ``run()`` function that takes
exactly one argument, which is an object that acts as interface
between the source and kernelconfig. It should be named ``env``.

Additionally, a source definition file is required for this type,
and its ``Type`` needs to be set to ``pym`` (in the ``[source]`` section).

Here is what a Python module looks like:

.. code:: Python

    # Python Module for the <name> configuration source
    # -*- coding: utf-8 -*-

    def reset():
        """
        The reset() function is optional.

        It is called whenever the Python Module gets loaded.

        It takes no arguments and does not have access
        to kernelconfig's pymenv interface.

        Usage scenarios include initializing module-level global variables.
        """
        pass
    # --- end of reset (...) ---


    def run(env):
        """
        The run() function must be implemented
        and is responsible for setting up the configuration basis,
        e.g. by downloading files.

        To facilitate this, it has to access to kernelconfig's pymenv interface,
        which provides some useful helper methods
        as well as error reporting and logging.

        If this function returns False (or false value that is not None),
        kernelconfig prints an error message and exits.
        """

        # The parsed parameters can be accessed via the "parameters" attribute
        params = env.parameters

        # The kernel version for which a configuration basis should be provided
        # can be accessed via the "kernelversion" attribute
        kver = env.kernelversion
        #
        # The kernel version provides access to individual version components via
        # the version, patchlevel, sublevel, subsublevel and rclevel attributes.

        # As an example,
        # the Liquorix source presented before
        # could also be written as a Python-Module source.
        # It needs to
        # (1) construct the url by means of string formatting
        # (2) download the config file
        # (3) register the downloaded file as (part of the) configuration basis
        #
        # It can be done by chaining 3 function calls to pymenv,
        # which also takes care of error handling:
        env.add_config_file(
            env.download_file(
                env.str_format(
                    'http://liquorix.net/sources/{kmaj}.{kpatch}/config.{param_arch}{param_pae}'
                )
            )
        )

        # the configuration basis can consist of multiple files,
        # just register them in the order as they should be read later on
        #
        # env.add_config_file(another_config_file)
    # --- end of run (...) ---


Template files for *pym*-type configuration sources can be found
in ``<settings>/sources/skel``,
named ``pymsource.def`` (source definition file)
and ``pymsource`` (Python module).


The methods and attributes available via the ``pymenv`` interface
are covered in detail as in-code documentation,
which can be read with ``pydoc kernelconfig.sources.pymenv``.

The class-level documentation gives a quick reference over what is offered:

.. code:: Python


    class PymConfigurationSourceRunEnv(...):
        """
        This is the runtime environment that gets passed
        to configuration source python modules, version 1.

        The python module's run() function
        receives the environment as first arg,
        interfacing with kernelconfig should only occur via this environment.

        The following attributes can be referenced by the python module,
        they should all be treated as readonly except where noted otherwise,
        see the @property in-code doc for details:

        * logger:         logger, can also be accessed via log_*() methods

        * name:           conf source name
        * exc_types:      exception types (namespace object/module)
        * parameters:     arg parse result (namespace object)
        * environ:        extra-env vars dict
        * str_formatter:  string formatter
        * format_vars:    string formatter's vars dict
        * kernelversion:  kernel version object
        * tmpdir:         temporary dir object
        * tmpdir_path:    path to temporary dir

        The following methods can be used for communicating with kernelconfig:

        * log_debug(...)         --  log a debug-level message
        * log_info(...)          --  log an info-level message
        * log_warning(...)       --  log a warning-level message
        * log_error(...)         --  log an error-level message

        * error([msg])           --  signal a "config uncreatable" error
                                     (log an error-level message
                                      and raise an appropriate exception)

        * add_config_file(file)  --  add a .config file that will later be
                                     used as configuration basis
                                     (can be called multiple times
                                     in splitconfig scenarios)

        The pym-environment also offers some helper methods, including:

        * run_command(cmdv)      --  run a command
        * get_tmpfile()          --  create new temporary file

        * download(url)          --  download url, return bytes
        * download_file(url)     --  download url to temporary file


        * git_clone_configured_repo()
                                 --  clone the repo configured in [config]
                                     and change the working dir to its path

        * git_clone(url)         --  clone a git repo and returns it path,
                                      using a per-confsource cache dir
        * git_checkout_branch(branch)
                                 --   switch to git branch

        * run_git(argv)          --  run a git command in $PWD
        * run_git_in(dir, argv)  --  run a git command in <dir>
        """
