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

The language is case-insensitive and ignores whitespace.
String values should be quoted.

There is also an alternative syntax
that is more in line with the original format of ``.config`` files,
which can be used interchangeably:

.. code:: text

    KCONFIG_OPTION=m
    KCONFIG_OPTION=y
    KCONFIG_OPTION=ym
    KCONFIG_OPTION=n

    KCONFIG_OPTION="STR"
    KCONFIG_OPTION+="STR"
    KCONFIG_OPTION|="STR"

Spaces around the assignment operators are ignored.

Additional instructions for loading other files:

.. code:: text

   include            FILE

Each statement may be followed by a ``if``\-condition,
which disables the entire statement if the condition is not met,
or a ``unless``\-condition with the opposite meaning.

Overall, the following $things$ can be checked:

* existence of config options or include files

* kernel version

* ``true``/``false``

* hardware modalias match

  .. Note::

     Future extension. Recognized, but the interpreter will complain about it.

* the truth value of the previous instruction's condition

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



The table below gives a quick overview of the instructions
that modify the value of kernel config options:

.. table:: kconfig instructions

   +------------+---------------+---------------------------------------------+
   | keyword    | symbol type   | description                                 |
   +============+===============+=============================================+
   | builtin    |               |                                             |
   |            | tristate      | set option to ``y``                         |
   |            +---------------+---------------------------------------------+
   |            | boolean       | set option to ``y``                         |
   |            +---------------+---------------------------------------------+
   |            | string        | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | int           | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | hex           | *illegal*                                   |
   +------------+---------------+---------------------------------------------+
   | module     |               |                                             |
   |            | tristate      | set option to ``m`` or ``y``                |
   |            +---------------+---------------------------------------------+
   |            | boolean       | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | string        | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | int           | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | hex           | *illegal*                                   |
   +------------+---------------+---------------------------------------------+
   | builtin\-\ |               |                                             |
   | or\-\      | tristate      | set option to ``y`` or ``m``                |
   | module     +---------------+---------------------------------------------+
   |            | boolean       | set option to ``y``                         |
   |            +---------------+---------------------------------------------+
   |            | string        | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | int           | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | hex           | *illegal*                                   |
   +------------+---------------+---------------------------------------------+
   | disable    |               | set option to ``n`` (``# ... is not set``)  |
   |            | tristate      |                                             |
   |            +---------------+                                             |
   |            | boolean       |                                             |
   |            +---------------+                                             |
   |            | string        |                                             |
   |            +---------------+                                             |
   |            | int           |                                             |
   |            +---------------+                                             |
   |            | hex           |                                             |
   +------------+---------------+---------------------------------------------+
   | set        |               | set option to any value,                    |
   |            |               | provided that the symbol accepts this value |
   |            +---------------+---------------------------------------------+
   |            | tristate      | ``y``, ``m`` or ``n``                       |
   |            +---------------+---------------------------------------------+
   |            | boolean       | ``y`` or ``n``                              |
   |            +---------------+---------------------------------------------+
   |            | string        | ``<str>``                                   |
   |            +---------------+---------------------------------------------+
   |            | int           | ``<int>``                                   |
   |            +---------------+---------------------------------------------+
   |            | hex           | ``<hex>``                                   |
   +------------+---------------+---------------------------------------------+
   | append     |               |                                             |
   |            | tristate      | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | boolean       | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | string        | add ``<str>`` to the end of the existing    |
   |            |               | value, preceeded by a separator             |
   |            |               | (whitespace)                                |
   |            |               |                                             |
   |            |               | Same as ``set`` if no value defined.        |
   |            +---------------+---------------------------------------------+
   |            | int           | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | hex           | *illegal*                                   |
   +------------+---------------+---------------------------------------------+
   | add        |               |                                             |
   |            | tristate      | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | boolean       | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | string        | same as ``append``,                         |
   |            |               | but set-like operation (membership test)    |
   |            +---------------+---------------------------------------------+
   |            | int           | *illegal*                                   |
   |            +---------------+---------------------------------------------+
   |            | hex           | *illegal*                                   |
   +------------+---------------+---------------------------------------------+


Load-File Instructions
----------------------

``include FILE``
    Load and process instructions from another file.

    Files are not loaded directly when the ``include`` statements gets
    processed, but instead are accumulated and loaded after processing all
    other commands.

    .. NOTE::

        Future extension:
        When used with a relative file path,
        the file will be looked up in $some_dir.
