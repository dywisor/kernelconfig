Config Generation
=================

This chapter describes the procedure of generating kernel configurations.
It starts with an informal characterization of the various data objects
involved in the process, and the modus operandi,
followed by a more detailed view on select aspects.


Basic Structure
---------------

**Symbol descriptors** store the name of a Kconfig symbol (if it has one)
and its dependencies on other symbols, and encode the symbol type
via the descriptor class.

They do not store values, because the descriptors can be shared across
more than one ``Config`` object.
However, they offer value-related functionality such as normalizing,
checking, and string-formatting.

All descriptor classes are subclasses of ``AbstractKconfigSymbol``.

Symbol descriptors are collected in **KconfigSymbols**,
the set of all Kconfig symbol descriptors,
which provides dict-like access by symbol name.

A concrete configuration maps a subset of the descriptors to values,
which is implemented in the **Config** object.
It is also responsible for config file I/O,
and for translating between Kconfig symbol names and config option names.

The configuration can be modified via a **ConfigChoices** object,
which wraps the ``Config`` object, accepts modification requests
and stores them in an intermediate *decision dict*,
resolves the effective configuration
and transfers it back to the ``Config`` object.

There is also an **interpreter** that reads commands from text files
and converts them into method calls to ``ConfigChoices`` objects.


How Config Generation Works
---------------------------

Given a kernel sources directory and an input ``.config`` file,
apply user-requested modifications, determine a working configuration
and write it to the output ``.config``:

#. **read Kconfig** symbol information

   Read the top-level ``Kconfig`` file and create symbol descriptors.

#. **load .config**

   Read config options and values from the input ``.config`` file,
   translate option names to Kconfig symbols
   and store the configuration as ``symbol -> value`` dict.

#. **modify** the configuration

   Modification requests can be
   read from text files using the "macros" interpreter,
   or made by using the ``ConfigChoices`` Python-Level interface.

   The are stored in an intermediate *decision* object,
   accumulate with other requests, and form a *decision dict*
   where each Kconfig symbol is mapped to a specific value or a range
   of acceptable values.

#. **resolve**

   Resolving the final configuration is split into 3 phases:

   * **Expand**, upwards-propagate decisions:

     For a given set of config option decisions,
     find out which other config options need to be set
     so that the dependencies of the *decision symbols* are satisfied.

   * **Apply**:

     Set config options to the decided values.
     If there is more than one *decision value*
     available for a specific symbol, pick one.

   * **Reduce/Expand**, downwards-propagate decisions:

     Find Kconfig symbols that are visible but have no value
     and set them to their default value while taking the *decisions*
     into account, which is mainly relevant for ``disable`` decisions
     (``# option is not set``).

     Similarly, disable config options that are no longer visible
     due to the *decisions*.

     The code for this phase is based on the oldconfig code
     from the Linux Kernel sources,
     and can be summarized as an *informed oldconfig*.

#. **write .config**

   If an intermediate ``.config`` file has been created during the
   reduce/expand phase of resolving, then that file is copied to the
   output ``.config`` file.
   Otherwise, a new file will be created.

   The advantage of using the intermediate file is that its format is
   exactly that of a conventional Linux Kernel configuration file.
   That is, running ``make oldconfig`` on it will produce no diff,
   provided that the kernel versions match.

   In constrast, the newly generated file is equivalent
   in terms of config options, but has no comments
   and the options may be ordered differently.



Symbol Descriptor Creation
--------------------------

:Input: sources info
:Output: ``KconfigSymbols``


*Symbol descriptors* are created at runtime
from the sources being processed.

In case of Linux Kernel sources, the top-level ``Kconfig`` file
is read after setting up relevant environment variables
(``srctree``, ``ARCH``, ``KERNELVERSION``).

The reading itself is handled by the Python/C API
``lkconfig`` module, which uses a copy of the
``zconf`` parser from the Linux Kernel sources,
and exposes the symbols as ``SymbolView`` objects.

On the Python side, ``KconfigSymbolGenerator`` is responsible
for converting the view objects into symbol descriptors,
which contain the following information:

* symbol name, if available

* dependencies on other symbols,
  as ``Expr`` object,
  a boolean expression data structure
  referencing other symbols

* symbol type via the descriptor's class, which is one of

  * TristateKconfigSymbol
  * BooleanKconfigSymbol
  * StringKconfigSymbol
  * IntKconfigSymbol
  * HexKconfigSymbol

  .. Note::

     The descriptor types do not mirror the
     Kconfig type hierarchy strictly.
     In Kconfig, ``int`` and ``hex`` are based on ``string``,
     in *kernelconfig*, they are not.


``KconfigSymbolGenerator`` creates a ``KconfigSymbols`` object,
which can then be used to instantiate ``Config`` objects.


Choices and Decisions
---------------------

:Input: ``Config``, user input in form of files, cmdline
:Output: decisions dict


``ConfigChoices`` is the Python-level interface for modifying kernel
configurations. It receives a number of modification requests
and stores them in a temporary *decisions dict*.

A request is of the form ``want <value> for <config option>`` or
``want any of <values> for <config option>``.

Generally, each request must be a restriction of previous
requests, and initially, there are no restrictions.
An exception to that are ``discard previous decisions on <config option>``
and ``add/append value``.

A request can be made by calling the appropriate ``ConfigChoices`` method:

.. table::

    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | modification request              |   supported for symbol type                 | description                    |
    | method                            |                                             |                                |
    |                                   +------------+--------+-------+-------+-------+                                |
    |                                   |  tristate  |  bool  |  str  |  int  |  hex  |                                |
    |                                   |            |        |       |       |       |                                |
    +===================================+============+========+=======+=======+=======+================================+
    | ``option_disable(opt)``           | yes                                         | decide ``<opt> := {n}``        |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | ``option_module(opt)``            | yes        | no                             | decide ``<opt> := {m}``        |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | ``option_builtin(opt)``           | yes        | yes    | no                    | decide ``<opt> := {y}``        |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | ``option_builtin_or_module(opt)`` | yes        | yes    | no                    | decide ``<opt> := {m, y}``     |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | ``option_set_to(opt, val)``       | yes                                         | decide ``<opt> := {<val>}``    |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | ``option_append(opt, val)``       | no                  | yes   | no            | extend decision on ``<opt>``:\ |
    |                                   |                     |       |               |                                |
    |                                   |                     |       |               | **str**: add ``<val>`` to the  |
    |                                   |                     |       |               | end of the existing value,     |
    |                                   |                     |       |               | preceeded by whitespace        |
    |                                   |                     |       |               |                                |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | ``option_add(opt, val)``          | no                  | yes                   | extend decision on ``<opt>``:\ |
    |                                   |                     |                       |                                |
    |                                   |                     |                       | **str**: add ``<val>`` to the  |
    |                                   |                     |                       | end of the existing value,     |
    |                                   |                     |                       | preceeded by whitespace,       |
    |                                   |                     |                       | if it does not already appear  |
    |                                   |                     |                       | in there                       |
    |                                   |                     |                       |                                |
    |                                   |                     |                       | **int**, **hex**:              |
    |                                   |                     |                       | change value by the            |
    |                                   |                     |                       | specified amount               |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+
    | ``discard(opt)``                  | yes                                         | reset ``<opt>`` to undecided   |
    +-----------------------------------+------------+--------+-------+-------+-------+--------------------------------+


The decision status and the requested values for each symbol are stored in
``ConfigDecision`` objects.

Once there are no further modification requests, the *decisions dict*
is created, which maps each decided Kconfig symbol to a set of acceptable
values. For *tristate* symbols, the set may contain one or two values,
and for all other symbol types, it contains one value.



Config Resolving
----------------

:Input: ``Config``, decisions dict
:Output: resolved ``Config``

.. Note::

    The pseudo-code examples in this section are not an exact transcript
    of the actual code, but rather give an idea of how it generally works.

Resolving a working configuration is split into several phases.

At first, a graph is created where the vertices are Kconfig symbols
that appear in ``Config`` or the *decisions dict*,
either directly or indirectly via dependencies,
and the edges represent a "possibly depends on" relationship.

This graph is then topologically sorted into groups,
where each symbol can only depend on symbols from upper-level groups.

Then, the *decisions dict* gets expanded: starting at the
lowest symbol group level,
determine which upper-level symbols need to be set as well,
and repeat that for each upper level:

.. code:: text

   expand-decisions(input_decisions):
        decisions_solution := empty dict {};
        need_expansion     := input_decisions;

        FOR each symbol_group IN reversed order LOOP
            -- the set of symbols from symbol_group that need to be expanded
            symbols_to_expand := symbol_group & need_expansion;

            -- at this point, symbols_to_expand have already been decided
            --  (the solution finding below affects upper-level symbols only)
            --
            merge symbols_to_expand with decisions_solution;

            --  list of solutions for the current symbol group
            --
            --    Each solution is a dict that maps symbols from
            --    upper-level groups to acceptable values
            --
            --    Initially there is only one solution,
            --    which contains all symbols from need_expansion
            --    except for symbols that are also in symbol_group
            --    (need_expansion - symbol_group)
            --    This solution may be empty, which simply means "no change".
            --
            --    If the list of solutions itself is empty,
            --    then there are no solutions and expand-decisions fails.
            --
            --    Similarily, if any symbol in a solutions dict is mapped
            --    to any empty value set, then the solution is invalid.
            --
            group_solutions := list of dict [need_expansion];

            FOR symbol in symbols_to_expand LOOP
                IF requested symbol value is not tristate "n" THEN
                    -- otherwise, there are no dependencies to be expanded

                    IF symbol is a tristate symbol THEN
                        symbol_solutions := get solutions for the symbol's
                                            dependencies so that the
                                            symbol's dir_dep evaluates to
                                            >= requested symbol value;
                    ELSE
                        symbol_solutions := get solutions for the symbol's
                                            dependencies so that the
                                            symbol's dir_dep evaluates to
                                            >= tristate "m";
                    END IF;

                    IF there are no symbol_solutions THEN
                        error;
                    END IF;

                    merge symbol_solutions with group_solutions,
                    elimininate invalid solutions

                    IF there are no group_solutions THEN
                        error;
                    END IF;

                END IF;
            END FOR LOOP;

            -- pick one solution from group_solutions that
            --  appears to have the least impact on the configuration
            group_solution := pick one out of group_solutions;

            --  update need_expansion with symbols/values from group_solution
            need_expansion := group_solution;

        END FOR LOOP;

        RETURN decisions_solution;


In a second iteration, the symbols get set to their decided values:

.. code:: text

    set-decisions(decisions):
        partial_config := empty dict {};

        FOR each symbol_group LOOP

            FOR each symbol IN symbol_group LOOP

                IF there is a decision for symbol THEN
                    verify that decision can be applied;
                    partial_config[symbol] = value from decisions[symbol];
                END IF;

            END FOR LOOP;

        END FOR LOOP;

        RETURN partial_config;


The existing configuration is then updated with ``partial_config``,
and expanded again in an oldconfig-like procedure:

.. code:: text

    informed-oldconfig(config, decisions)
        changed := TRUE;
        WHILE changed LOOP
            changed := FALSE;

            --  find symbols that have become visibile, but have no value
            new_symbols := find NEW symbols;

            FOR each symbol IN new_symbols LOOP
                IF there is a decision for symbol THEN
                    --  decision value is tristate "n"
                    config[symbol] := decision value;
                ELSE
                    config[symbol] := default value;
                END IF;

                changed := TRUE;
            END FOR LOOP;

        END WHILE LOOP;

        RETURN config;
