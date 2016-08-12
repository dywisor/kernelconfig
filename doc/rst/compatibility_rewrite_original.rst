.. _original project:
    https://github.com/Calchan/kernelconfig


Discrepancies
=============

This document lists differences in behavior
between this (further referred to as "v1") and the `original project`_ ("v0").
While it highlights some of the features present in *v1*,
it is not meant to be a feature comparison.
Its purpose is to point out where *v1* clearly deviates from *v0*
despite using the seemingly same files
and which command line options changed.

| The evaluation is based on kernelconfig,
| *v0* as of Aug 2016, commit ``21022840c613919ad3a5fa0e05b6b709710834f2``
| and *v1* as of Aug 2016, commit ``278f95616088c572d24dfcb25cee2a37daa801b3``.

Paragraphs marked with ``INTEND-TO-FIX`` denote
that compatibility with *v0* will be restored,
and ``UNSURE-IF-FIX`` means that the discrepancy could be fixed.


Running kernelconfig
--------------------

* *v1* does not support the ``-v``, ``--version`` option.

    ``-v`` is accepted, but it increases the log verbosity.

    | ``UNSURE-IF-FIX``: reintroduce as renamed option: ``--fake-kver``, ``--source-kver``?
    | Not all config sources follow the kernel versioning scheme, see e.g. CentOS.


* In *v0*, ``-a``, ``--arch`` accepts arbitrary target architectures,
  and is only relevant to curated sources.

    In *v1*, ``-a``, ``--arch`` must be a supported kernel architecture,
    either directly or indirectly, and it affects overall config generation,
    e.g. which config options are known.
    ``x86``, ``x86_64`` (``-> x86``) and ``armv6`` (``-> arm``) are accepted,
    for instance, but ``amd64`` is not.

    ``UNSURE-IF-FIX``: introduce "user target arch",
    translate it to target machine arch

* *v1* runs ``make oldconfig`` as part of config generation,
  there is no need to do it manually.


Installing kernelconfig
-----------------------

Be aware that *v1* has different (i.e. more) dependencies.

Unlike *v0*, installing with ``pip`` alone is not sufficient
as it will only install the Python-related files.
The data and config files need to be installed with
``make install-data install-config``.

**v0 and v1 can not be installed at the same time**,
they use the same Python module namespace (``kernelconfig``),
but are not compatible at the source code level.

*v1* can be run in *standalone mode* from the cloned project sources' git repo.


Settings File
-------------

*v0* and *v1* settings files have the same overall structure
and the *v1* parser is mostly compatible with *v0*.

Except for the section headers (``[section name]``),
*v1* settings files are not ini files.
ini constructs such as nested section headers are not allowed.


Settings Directories
++++++++++++++++++++

*v0* and *v1* use the same settings directories::

    ~/.config/kernelconfig
    /etc/kernelconfig

Both prefer '~' over '/etc'.


\[source\]
++++++++++

*v0* reads the first non-empty, non-comment line
and interprets it as curated source.
All remaining lines are completely ignored.

In *v1*, the first non-empty, non-comment line specifies the source,
and it can span over multiple lines by means of backslash line continuation.
All remaining lines are passed as *data* to the source,
depending on the type of the source.
Curated sources do not accept *data*.

When converting a *v0* ``[source]`` section to *v1*,
drop all non-empty, non-comment lines except for the first one.

The line needs to be prefixed with ``source``
if the source has one of the following names:
``cmd``,
``command``,
``defconfig``,
``file``,
``local-file``,
``local_file``,
``make``,
``mk``,
``pym``,
``script``,
``sh``,
and ``source``.


\[options\]
+++++++++++

The syntax of the ``[options]`` section has undergone
substantial changes, at present it is **not compatible with v0**:

* **blocker**: ``enable`` action renamed to ``builtin``
    ``INTEND-TO-FIX``: reintroduce (as alias to ``builtin``)

* **blocker**: ``set OPT=VAL`` action replaced by ``set OPT VAL``
    ``INTEND-TO-FIX``: reintroduce (alternative syntax)

* contradicting actions::

    module A
    disable A

  This is an error in *v1*, and effectively ``disable A`` in *v0*.

* Reserved words must be quoted to get their non-reserved meaning,
  enabling the config option "module" as module would have to be written
  as ``module "module"``.

  In *v0*, there are no reserved words.

* not all characters are allowed in unquoted words
  and string values should always be quoted.

  In *v0*, all chars are allowed and string values must be quoted.

* since the effective kernel configuration gets resolved,
  it is not necessary to specify intermediate config options.

  For example, the *v0* snippet sets the default kernel command line::

    enable CONFIG_CMDLINE_BOOL
    set CONFIG_CMDLINE="panic=10"

  In *v1*, it can be reduced to (note the replaced ``set`` action)::

    set CONFIG_CMDLINE "panic=10"

When converting a *v0* ``[options]`` section to *v1*,
make sure to remove contradicting actions.
The reduced charset in unquoted words should not be much of an issue.

As for ``enable`` and ``set OPT="VAL"``, wait for a fix.

|

Noteworthy changes, but not relevant for converting *v0* ``[options]`` to *v1*:

* config option names can be prefixed with ``CONFIG_``, but do not have to

* actions are case-insensitive (*v0*: case-sensitive)

* new actions:

  * ``builtin-or-module``

  * ``include``

  * ``hwdetect``

  * ``packages``

* action modifiers:

  * ``driver``/``module``

  * ``modalias``

* conditional expressions



Curated Sources
---------------

Different search directories:

*v0* searches for curated sources in::

    /usr/share/kernelconfig/sources

*v1* expects to find sources in the ``sources`` subdirectory
of one of the settings directories::

    ~/.config/kernelconfig/sources
    /etc/kernelconfig/sources

``INTEND-TO-FIX``: add ``/usr/share/kernelconfig/sources`` to the list,
and install system-wide sources to this directory

|

*v0* curated sources are scripts with a fixed script calling convention.

When converting a *v0* curated source to *v1*, nothing needs to be done,
the scripts can be used as-is.
Consider writing a *source definition file* to benefit
from target architecture checks and a meaningful help message
when ``kernelconfig --help-source`` is run.
See *Script-Only Curated Sources* in the userguide for further advice.

Be aware that *v1* adds support for other types of curated sources
such as (remote) files and Python modules with access to common functionality.
It also offers argument parsing.
