Configuration Statements
========================


The kernel configuration itself is configured via *kconfig instructions*
in the ``[options]`` section of the settings file,
or in separate *feature set* files.


Instructions that operate on Kconfig symbols:

.. code:: text

   module             KCONFIG_OPTION [KCONFIG_OPTION...]
   builtin            KCONFIG_OPTION [KCONFIG_OPTION...]
   builtin-or-module  KCONFIG_OPTION [KCONFIG_OPTION...]
   disable            KCONFIG_OPTION [KCONFIG_OPTION...]

   m                  KCONFIG_OPTION [KCONFIG_OPTION...]
   y                  KCONFIG_OPTION [KCONFIG_OPTION...]
   ym                 KCONFIG_OPTION [KCONFIG_OPTION...]
   n                  KCONFIG_OPTION [KCONFIG_OPTION...]

   set                KCONFIG_OPTION  STR
   append             KCONFIG_OPTION  STR
   add                KCONFIG_OPTION  STR

   hardware-detect
   hwdetect

   packages           [build-time|re-eval]
   pkg                [build-time|re-eval]

The language is case-insensitive and ignores whitespace.
String values should be quoted.

To refer to module names instead of config options,
put the ``driver`` keyword after the command and before the module names:

.. code:: text

    module             driver  MODULE_NAME [MODULE_NAME...]
    builtin            driver  MODULE_NAME [MODULE_NAME...]
    builtin-or-module  driver  MODULE_NAME [MODULE_NAME...]
    disable            driver  MODULE_NAME [MODULE_NAME...]

    # likewise for m, y, ym, n

    # not supported for set, append, add

    # not supported for hardware-detect

    # not supported for packages

The ``modalias`` allows to specify module aliases,
its usage is identical to ``driver``.

There is an alternative syntax
that is more in line with the original format of ``.config`` files,
which can be used interchangeably, but supports config option names only:

.. code:: text

    KCONFIG_OPTION=m            # module
    KCONFIG_OPTION=y            # builtin
    KCONFIG_OPTION=ym           # builtin-or-module
    KCONFIG_OPTION=n            # disable

    KCONFIG_OPTION="STR"        # set
    KCONFIG_OPTION+="STR"       # append
    KCONFIG_OPTION|="STR"       # add

Spaces around the assignment operators are ignored.

Additional instructions for loading other files:

.. code:: text

   include            FILE

Each statement may be followed by a ``if``\-condition,
which disables the entire statement if the condition is not met,
or a ``unless``\-condition with the opposite meaning.

Overall, the following conditions can be checked:

* existence of config options or include files with the ``exists`` or ``exist``
  keyword

  It accepts up to one arg. The meaning of this condition
  depends on whether the command it appears in is
  a *kconfig instruction* or a *load-file instruction*.

  If used with no arg or the placeholder arg ``_``,
  it checks for existence of the config option
  or the file currently being processed.

  Otherwise, existence of the supplied arg is checked.

  A statement of the form

  .. code:: text

     builtin A B C if exists

  would enable any or all of the config options `A`, `B` and/or `C` if
  they exist, and is equivalent to the longer and overly explicit variant:

  .. code:: text

     builtin A if exists A
     builtin B if exists B
     builtin C if exists C


* kernel version

  The kernelversion can be compared, either as a whole, or partially:

  .. code:: text

    builtin B if kver == 4.7.0            # full kernel version (a.b.c...)
    builtin A if kver >= 4.2              #  can also be given partially
    builtin C if kmaj < 5                 # the "version" of the kernel version
    builtin D if kmaj == 4 && kmin != 3   # the "sublevel" of the kernel version
    builtin E if kpatch == 0              # the "patchlevel" of the version


* hardware modalias match with the ``hardware-match``, ``hw`` keywords

  .. Note::

     Future extension. Recognized, but the interpreter will complain about it.


* ``true``/``false``


* the truth value of the previous instruction's condition can be
  accessed with the placeholder expression ``_``

  .. code:: text

     builtin A if false       # Disabled, sets _ to false
                              #
     builtin B unless _       # Enabled, because "unless false" is true.
                              # However, the value of the condition is false
                              # and thus _ is set to false.
                              #
     builtin D E if exists    # This sets _ twice,
                              # once to "exists D", and then to "exists E".


Conditions can be negated or combined with:

.. code:: text

    ! COND
    COND && COND
    COND || COND

    not COND
    COND and COND
    COND or  COND



Kconfig Instructions
--------------------

``hardware-detect``
   Scans ``/sys`` for kernel modules that are currently used by any device,
   and enables corresponding config options as builtin or module.

   Modules for which no config options can be found are ignored,
   but get logged.

   Alternative names: ``hwdetect``.

``packages [build-time|re-eval]``
    Query portage for a list of installed packages that use
    ``linux-info.eclass`` and get their build-time value of the
    ``CONFIG_CHECK`` variable or re-evaluate config recommendations
    against the kernel sources for which a configuration is being created.

    Recommended config options are enabled as builtin or module (``OPTION``),
    or disabled (``!OPTION``), respectively.

    If the modifier is omitted, ``re-eval`` is assumed.

    Alternative names: ``pkg``.

``module KCONFIG_OPTION [KCONFIG_OPTION...]``
   Enable one or more kernel config options as module.

   The modified options must be of *tristate* type.

``builtin KCONFIG_OPTION [KCONFIG_OPTION...]``
   Enable one or more kernel config options as builtin.

   The modified options must be of *tristate* or *boolean* type.

``builtin-or-module KCONFIG_OPTION [KCONFIG_OPTION...]``
   Enable one or more kernel config options as builtin or module.

   The modified options must be of *tristate* or *boolean* type.
   The effective value is ``y`` or ``m``, out of which ``m`` gets preferred.

``disable KCONFIG_OPTION [KCONFIG_OPTION...]``
   Disable one or more kernel config options.

``set KCONFIG_OPTION VALUE``
   Set the value of a kernel config option to ``VALUE``.

   The modified option may be of any type,
   and the ``VALUE`` must match that type.

``append KCONFIG_OPTION VALUE``
   Add a value to the end of a list-like, *string*-type option.

``add KCONFIG_OPTION VALUE``
   Add a value to the end of a list-like, *string*-type option
   if it is not already part of that list.


Some of the instructions also accept kernel module names,
which must be explicitly requested
by putting the ``driver`` keyword in front of the module name list.
The module names get expanded to a list of config options
to which the instruction is then applied.
Alternative names for the ``driver`` keyword are ``drv`` and ``module``.

``module driver MODULE_NAME [MODULE_NAME...]``
   Determine which config options correspond to the given modules
   and enable them as module.

   The modified options must be of *tristate* type.

``builtin driver MODULE_NAME [MODULE_NAME...]``
   Determine which config options correspond to the given modules
   and enable them as builtin.

   The modified options must be of *tristate* or *boolean* type.

``builtin-or-module driver MODULE_NAME [MODULE_NAME...]``
   Determine which config options correspond to the given modules
   and enable them as builtin or module.

   The modified options must be of *tristate* or *boolean* type.
   The effective value is ``y`` or ``m``, out of which ``m`` gets preferred.

``disable driver MODULE_NAME [MODULE_NAME...]``
   Determine which config options correspond to the given modules
   and disable them.

Module aliases are also accepted by these commands by means of the
``modalias`` keyword.
Module aliases are expanded to module names and then to config options.

``module modalias MODULE_ALIAS [MODULE_ALIAS...]``
   Determine which config options correspond to the given module aliases
   and enable them as module.

   Unmatched module aliases are ignored,
   but at least one alias must resolve to a config option.



The table below gives a quick overview of the instructions
that modify the value of kernel config options:

.. table:: kconfig instructions

   +------------+---------------+-------------+---------------------------------------------+
   | keyword    | symbol type   | ``driver``, | description                                 |
   |            |               | ``mod``\    |                                             |
   |            |               | ``alias``?  |                                             |
   +============+===============+=============+=============================================+
   | builtin    |               | yes         |                                             |
   |            | tristate      |             | set option to ``y``                         |
   |            +---------------+             +---------------------------------------------+
   |            | boolean       |             | set option to ``y``                         |
   |            +---------------+             +---------------------------------------------+
   |            | string        |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | int           |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | hex           |             | *illegal*                                   |
   +------------+---------------+-------------+---------------------------------------------+
   | module     |               | yes         |                                             |
   |            | tristate      |             | set option to ``m`` or ``y``                |
   |            +---------------+             +---------------------------------------------+
   |            | boolean       |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | string        |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | int           |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | hex           |             | *illegal*                                   |
   +------------+---------------+-------------+---------------------------------------------+
   | builtin\-\ |               | yes         |                                             |
   | or\-\      | tristate      |             | set option to ``y`` or ``m``                |
   | module     +---------------+             +---------------------------------------------+
   |            | boolean       |             | set option to ``y``                         |
   |            +---------------+             +---------------------------------------------+
   |            | string        |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | int           |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | hex           |             | *illegal*                                   |
   +------------+---------------+-------------+---------------------------------------------+
   | disable    |               | yes         | set option to ``n`` (``# ... is not set``)  |
   |            | tristate      |             |                                             |
   |            +---------------+             |                                             |
   |            | boolean       |             |                                             |
   |            +---------------+             |                                             |
   |            | string        |             |                                             |
   |            +---------------+             |                                             |
   |            | int           |             |                                             |
   |            +---------------+             |                                             |
   |            | hex           |             |                                             |
   +------------+---------------+-------------+---------------------------------------------+
   | set        |               | no          | set option to any value,                    |
   |            |               |             | provided that the symbol accepts this value |
   |            +---------------+             +---------------------------------------------+
   |            | tristate      |             | ``y``, ``m`` or ``n``                       |
   |            +---------------+             +---------------------------------------------+
   |            | boolean       |             | ``y`` or ``n``                              |
   |            +---------------+             +---------------------------------------------+
   |            | string        |             | ``<str>``                                   |
   |            +---------------+             +---------------------------------------------+
   |            | int           |             | ``<int>``                                   |
   |            +---------------+             +---------------------------------------------+
   |            | hex           |             | ``<hex>``                                   |
   +------------+---------------+-------------+---------------------------------------------+
   | append     |               | no          |                                             |
   |            | tristate      |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | boolean       |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | string        |             | add ``<str>`` to the end of the existing    |
   |            |               |             | value, preceeded by a separator             |
   |            |               |             | (whitespace)                                |
   |            |               |             |                                             |
   |            |               |             | Same as ``set`` if no value defined.        |
   |            +---------------+             +---------------------------------------------+
   |            | int           |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | hex           |             | *illegal*                                   |
   +------------+---------------+-------------+---------------------------------------------+
   | add        |               | no          |                                             |
   |            | tristate      |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | boolean       |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | string        |             | same as ``append``,                         |
   |            |               |             | but set-like operation (membership test)    |
   |            +---------------+             +---------------------------------------------+
   |            | int           |             | *illegal*                                   |
   |            +---------------+             +---------------------------------------------+
   |            | hex           |             | *illegal*                                   |
   +------------+---------------+-------------+---------------------------------------------+
   | hardware-\ | *n/a*         | *n/a*       | scan ``/sys`` for hardware identifiers and  |
   | detect     |               |             | enable config options accordingly           |
   +------------+---------------+-------------+---------------------------------------------+


Load-File Instructions
----------------------

``include FILE``
    Load and process instructions from another file.

    The ``FILE`` may be an absolute or relative filesystem path.
    Absolute paths are processed as-is,
    whereas relative paths are looked up in the include-file directories.

    Relative paths can contain wildcard characters `*`, `?`,
    and are subject to non-recursive glob expansion over all directories.

    A statement of the form::

        include pkg/*

    would load all files that are in *any* ``pkg`` subdirectory
    of *any* include-file directory.

    Assuming the default include-file directories
    and the following files structure,
    above command would  load ``B`` and ``C`` from the home directory,
    and ``E`` from ``/etc``::

        /home/user/.config/kernelconfig/include/A
        /home/user/.config/kernelconfig/include/pkg/B
        /home/user/.config/kernelconfig/include/pkg/C
        /etc/kernelconfig/include/D
        /etc/kernelconfig/include/pkg/B
        /etc/kernelconfig/include/pkg/E
        /etc/kernelconfig/include/pkg/F/G

    * neither ``A`` nor ``D``,
      because they are not matched by the pattern

    * not ``B`` from ``/etc``,
      because it is overshadowed by the file in ``/home``

    * not ``F``, because it is a directory

    * not ``F/G``, because the glob-expansion is non-recursive
      and therefore it is not matched by the pattern

    If there are no files matching ``pkg/*``, the command would fail.
    If that is not desired, an ``exists`` condition should be appended::

        include pkg/* if exists

    Files are not loaded directly when the ``include`` statements gets
    processed, but instead are accumulated and loaded after processing all
    other commands.

    .. Note::

        Absolute filesystem paths do not get glob-expanded.
        This might change in future.
