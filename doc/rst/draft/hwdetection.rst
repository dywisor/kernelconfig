Hardware Detection
==================

This is a draft on the upcoming *hardware detection* feature.


What is hardware detection?
---------------------------

kernelconfig scans ``/sys`` for hardware identifiers
and determines which kernel config options needs to be set
in order to have the necessary kernel modules.


What kind of hardware identifiers exist?
----------------------------------------

* **driver**
  per-device ``/sys/devices/**/driver`` symlinks
  point to the sysfs directory of the already loaded driver,
  its name can be get with ``basename <dir>``

  In shell code, this info can be collected with::

    find /sys -type l -name driver -exec readlink  '{}' + | xargs -r -n 1 basename | sort -u


* **modalias**
  per-device ``/sys/devices/**/modalias`` files
  contain module aliases that can be mapped to kernel module names
  with help of ``/lib/modules/$(uname -r)/modules.alias``

  In shell code, this info can be collected with::

    find /sys -type f -name modalias -exec sort -u '{}' +


How to map kernel module names back to config options\?
-------------------------------------------------------

This can be done by inspecting the module Makefiles in the kernel sources,
which contain entries of the form ``obj-$(<config option>) += <module>.o``

For example, e1000e has (``drivers/net/ethernet/intel/e1000e/Makefile``)::

    obj-$(CONFIG_E1000E) += e1000e.o


kernel module Makefiles are only included
if certain other config options are set.

In case of e1000e,
``drivers/net/ethernet/Makefile`` includes ``intel/Makefile``
only if ``CONFIG_NET_VENDOR_INTEL`` is set,
and ``intel/Makefile`` includes ``intel/e1000e/Makefile``
only if ``CONFIG_E1000E`` is set.
This is not of interest,
since the kconfig structure mirrors these dependencies
(or the other way around),
and ``kernelconfig.kconfig`` takes care of resolving such dependencies.


How to map module aliases to config options\?
---------------------------------------------

This can be split into two steps:

#. map module aliases to module names

#. map module names to config options, which has already been addressed above


Mapping module aliases to module names can be done by parsing
``modules.alias``, which can be created with a throw-away
``make ARCH=... allmodconfig && make ARCH=... modules`` run.
Reusing a precompiled modules.alias file could work in the average case.

The unaliasing can be done with libkmod's Python bindings or manually,
the ``modules.alias`` format is sufficiently simple
(``alias <alias_name> <module_name>``).


Other ideas
-----------


Collect hardware information on another machine\?
+++++++++++++++++++++++++++++++++++++++++++++++++

Scenario: workstation/desktop + embedded device

Run hw-collector on the embedded device, which creates an hw-info file,
e.g. a text file that lists module names/module aliases.

The hw-collector could be written in C or sh (compatible with busybox ash)

Dependencies:

    * ``/sys`` mounted
    * a way to transfer the hw-info file to the workstation/desktop
    * maybe ``sh``

Back on the workstation/desktop,
feed kernelconfig with the hw-info file, generate config && compile.
