.. _bug \#469326:
   https://bugs.gentoo.org/show_bug.cgi?id=469326

.. _bug \#551430:
   https://bugs.gentoo.org/show_bug.cgi?id=551430

.. _mrueg-kernel-config-check:
   https://gist.github.com/mrueg/cd19a20d2e712f61d2ea

.. _macros file format:
    ../macros_lang.rst

.. sectnum::

.. contents::
   :backlinks: top


PM Integration
==============

This is a draft on the upcoming *package management integration* feature.

Two approaches are presented, they differ in

* availability - one does not exist yet,

* and reliability/accuracy - what to expect from the pm-integration source,
  how useful will it be?


From kernelconfig's perspective,
*pm integration* would **ideally** be about
installing *feature set* files to a location where kernelconfig can find them,
organized in a nested directory structure.

Users could then request to set config options accordingly
by including the *feature set* files in the settings file:

.. code:: text

    [source]
    ...

    [options]
    include pkg/*


Selecting options for individual packages could be done
with ``include pkg/<pkg>``,
and selecting additional per-package features
with ``include pkg/<pkg>/<feature>``.

A ``kernelconfig`` eclass could help to install *feature set* files to
the correct location, and it could also offer functions for creating them.

This approach is covered in `feature set files`_.


An alternative to that is reusing the already existing `CONFIG_CHECK`_
functionality from ``linux-info.eclass``,
which involves either creating a *feature set* file at package/ebuild
build time, or inspecting portage vdb/logs at kernelconfig runtime.


CONFIG_CHECK
------------

Defined in ``linux-info.eclass``::

    # Copyright 1999-2016 Gentoo Foundation
    # Distributed under the terms of the GNU General Public License v2

    ...

    # @ECLASS-VARIABLE: CONFIG_CHECK
    # @DESCRIPTION:
    # A string containing a list of .config options to check for before
    # proceeding with the install.
    [...]
    #
    # You can also check that an option doesn't exist by
    # prepending it with an exclamation mark (!).
    #
    [...]
    # To simply warn about a missing option, prepend a '~'.
    # It may be combined with '!'.

There is also a ``@`` "reworkmodules" prefix which can be combined with ``!``.
It seems to be undocumented
and related to ``linux-mod.eclass`` (``MODULE_NAMES``).

``CONFIG_CHECK`` can be set locally in ``pkg_setup()`` or ``pkg_pretend()``.

Availability
++++++++++++

Better than any other information source,
simply because it is the only existing one covered in this draft-doc.

Not that widely used, though, as seen by counting
``$CATEGORY/$PN`` package dirs:

  .. code:: text

     $ find <PORTDIR> -type f -name "*.ebuild" | \
         sed -r -e 's=/[^/]+[.]ebuild$==' | sort -u | wc -l
     19036

     $ find <PORTDIR> -type f -name "*.ebuild" | \
         xargs grep -l CONFIG_CHECK | \
         sed -r -e 's=/[^/]+[.]ebuild$==' | sort -u | wc -l
     219

     # not counting eclasses here, but for reference,
     # there are only two relevant files:
     $ find <PORTDIR>/eclass -type f -name "*.eclass" | \
         xargs grep -l CONFIG_CHECK | \
         sort
     .../eclass/chromium-2.eclass
     .../eclass/chromium.eclass
     .../eclass/linux-info.eclass
     .../eclass/linux-mod.eclass

For example, there are no config recommendations for ``net-fs/nfs-utils``,
see also `bug #469326`_.

The ebuild ratio should not be overrated,
many packages do not require specific config options.

Since this approach relies on ebuilds,
cross-distro support is limited.


Reliability/Accuracy
++++++++++++++++++++

Reliability/Accuracy varies,
recommendations can be mandatory or optional,
and also conditional or unconditional.

The recommendations are based on what was present at package/ebuild build time,
most importantly which ``.config`` file was used for config checking,
but also kernel version constraints,
which are compared against the kernel srctree
as set by ``linux-info.eclass`` (usually ``/usr/src/linux``).

When running kernelconfig,
``CONFIG_CHECK`` should be considered as an unreliable source,
since especially the configuration basis differs from the build-time one.

The recommendations can be wrong in cross-compilation scenarios.

----

A simple example is ``sys-fs/fuse``, which wants ``FUSE_FS``,
from ``fuse-2.9.7.ebuild``:

.. code:: bash

    # Copyright 1999-2016 Gentoo Foundation
    # Distributed under the terms of the GNU General Public License v2

    ...

    pkg_setup() {
        if use kernel_linux ; then
            if kernel_is lt 2 6 9 ; then
                die "Your kernel is too old."
            fi
            CONFIG_CHECK="~FUSE_FS"
            FUSE_FS_WARNING="You need to have FUSE module built to use user-mode utils"
            linux-info_pkg_setup
        fi
    }

kernelconfig should enable ``FUSE_FS`` here.

A more "extreme" example is ``app-emulation/docker``,
from ``docker-9999.ebuild``:

.. code:: bash

    # Copyright 1999-2016 Gentoo Foundation
    # Distributed under the terms of the GNU General Public License v2

    ...

    CONFIG_CHECK="
        ~NAMESPACES ~NET_NS ~PID_NS ~IPC_NS ~UTS_NS
        ~DEVPTS_MULTIPLE_INSTANCES
        ~CGROUPS ~CGROUP_CPUACCT ~CGROUP_DEVICE ~CGROUP_FREEZER ~CGROUP_SCHED ~CPUSETS ~MEMCG
        ~KEYS ~MACVLAN ~VETH ~BRIDGE ~BRIDGE_NETFILTER
        ~NF_NAT_IPV4 ~IP_NF_FILTER ~IP_NF_MANGLE ~IP_NF_TARGET_MASQUERADE
        ~IP_VS ~IP_VS_RR
        ~NETFILTER_XT_MATCH_ADDRTYPE ~NETFILTER_XT_MATCH_CONNTRACK
        ~NETFILTER_XT_MATCH_IVPS
        ~NETFILTER_XT_MARK ~NETFILTER_XT_TARGET_REDIRECT
        ~NF_NAT ~NF_NAT_NEEDED

        ~POSIX_MQUEUE

        ~MEMCG_SWAP ~MEMCG_SWAP_ENABLED

        ~BLK_CGROUP ~IOSCHED_CFQ
        ~CGROUP_PERF
        ~CGROUP_HUGETLB
        ~NET_CLS_CGROUP
        ~CFS_BANDWIDTH ~FAIR_GROUP_SCHED ~RT_GROUP_SCHED
        ~XFRM_ALGO ~XFRM_USER
    "

    ERROR_KEYS="CONFIG_KEYS: is mandatory"
    ERROR_MEMCG_SWAP="CONFIG_MEMCG_SWAP: is required if you wish to limit swap usage of containers"
    ERROR_RESOURCE_COUNTERS="CONFIG_RESOURCE_COUNTERS: is optional for container statistics gathering"

    ERROR_BLK_CGROUP="CONFIG_BLK_CGROUP: is optional for container statistics gathering"
    ERROR_IOSCHED_CFQ="CONFIG_IOSCHED_CFQ: is optional for container statistics gathering"
    ERROR_CGROUP_PERF="CONFIG_CGROUP_PERF: is optional for container statistics gathering"
    ERROR_CFS_BANDWIDTH="CONFIG_CFS_BANDWIDTH: is optional for container statistics gathering"
    ERROR_XFRM_ALGO="CONFIG_XFRM_ALGO: is optional for secure networks"
    ERROR_XFRM_USER="CONFIG_XFRM_USER: is optional for secure networks"

    ...
    pkg_setup() {
        ...

        if kernel_is lt 4 5; then
            CONFIG_CHECK+="
                ~MEMCG_KMEM
            "
            ERROR_MEMCG_KMEM="CONFIG_MEMCG_KMEM: is optional"
        fi

        ...

        if use aufs; then
            CONFIG_CHECK+="
                ~AUFS_FS
                ~EXT4_FS_POSIX_ACL ~EXT4_FS_SECURITY
            "
            ERROR_AUFS_FS="CONFIG_AUFS_FS: is required to be set if and only if aufs-sources are used instead of aufs4/aufs3"
        fi
    }

How should kernelconfig handle these cases?

* ``ERROR_`` vars are not mandatory,
  and grepping them for "mandatory" or "optional" is not reliable either

* the ``~`` prefix is not a measurement for optionality

* ``MEMCG_KMEM``: recommendation is based on the kernel srctree present
  at package/ebuild build time, not kernelconfig's ``--srctree``

* ``AUFS_FS``: "required", but "if and only if"?



Implementation Remarks
++++++++++++++++++++++

Increasing Reliability
^^^^^^^^^^^^^^^^^^^^^^

It is possible to work around "build-time based recommendations"
by re-evaluating ``pkg_pretend()``, ``pkg_setup()`` for "all"[*]_ packages.

See `mrueg-kernel-config-check`_ and also `bug #551430`_.

To do that, a ``KBUILD_OUTPUT`` dir needs to be created,
after getting the configuration basis::

    KBUILD_OUTPUT="$(mktemp -d)"
    cp $conf_basis_file $KBUILD_OUTPUT/.config
    ln -s $srctree $KBUILD_OUTPUT/source  # required!

Efficiency-wise, this would load ``linux-info.eclass`` multiple times,
causing a lot of repeated and redundant ``Makefile``/``.config`` reads.


.. [*] subject to optimization,
       e.g. include only packages that inherit linux-info


Retrieval of Recommended Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

#. getting ``CONFIG_CHECK`` from ebuilds directly is not reasonable

   * requires sh parsing: at least value spanning over multiple lines
     and if-else, but also evaluating if-else,
     which requires pm//portage functionality for evaluating conditions


#. the ``CONFIG_CHECK`` var is available as part of the package
   environment, but only if ``CONFIG_CHECK`` is not ``local``

    It should be retrievable via portage pym  after running ``pkg_setup()``,
    ``equery has`` does sth. similar.

    Otherwise grep or bash-eval-print
    ``/var/db/pkg/<cat>/<pkg>/environment.bz2``:

    .. code:: bash

        CONFIG_CHECK=""
        source <(bzcat .../environment.bz2) && \
        printf '%s\n' "${CONFIG_CHECK}"

    Easy to implement and maintain, but does not cover all cases.

#. grep logs for ``CONFIG_CHECK`` warnings

    This would also catch ``local CONFIG_CHECK``, but is hacky!

    The reliability can be improved as described in `increasing reliability`_,
    and by reading the log files created in ``PORTAGE_TMPDIR``.

#. extend ``linux-info.eclass, check_extra_config()``
   to create a file in kernelconfig's native config-modification file format
   (a *feature set* file):

    .. code:: text

        ~CONFIG_A   =>  builtin-or-enable A
        ~!CONFIG_A  =>  disable A

        # linux-info dies if config options w/o the "~" prefix are not
        # present at build time, so translating them does not make much sense
        CONFIG_A    =>  nop    # or builtin-or-enable A
        !CONFIG_A   =>  nop    # or disable A

        # "reworkmodules", ignored
        @*          =>  nop

    The created file needs to be installed somehow.

    This approach also increases reliability without having
    to re-evaluate packages, but it would be necessary to rebuild packages.



.. _feature set files:

*feature set* files
-------------------

As outlined before, the idea here is to distribute files
written in the `macros file format`_.
This can range from ``.config`` file snippets to conditional instructions.



Availability
++++++++++++

There are no *feature set* files available yet.


* cross-distro friendly

* duplicated effort

* package rebuild/revbump required
  (when distributing *feature set* files as part of the package)


Potential Availability
^^^^^^^^^^^^^^^^^^^^^^

* ``.config`` fragments - *feature set* files mostly [*]_ support
  the ``.config`` file format, which allows to pick up config snippets
  and use them directly


.. [*] an exception to that are ``# CONFIG_A is not set`` lines,
       but this can be implemented


Reliability/Accuracy
++++++++++++++++++++

Since *feature set* files are kernelconfig's text-based config request
mechanism, the accuracy is good.

Most importantly,
kernelconfig-related conditions can be evaluated at config creation time:

* kernel version

    .. code:: text

        CONFIG_A=y  if kver >= 4

* target architecture

    .. code:: text

        CONFIG_A=y  if arch == x86_64


* existence of config options

    .. code:: text

        CONFIG_A=y  if exists
        CONFIG_B=y  unless _



Implementation Remarks
++++++++++++++++++++++


* the amount of required code changes is minimal,
  except for some tweaks,
  e.g. adding an ``--exclude`` option to the ``include`` instruction



*feature set* overlays
^^^^^^^^^^^^^^^^^^^^^^

In addition to, or as an alternative to distributing *feature set* files
as part of packages, it would be possible to distribute *feature set* files
via git repos (or normal directories).

Code-wise, it would be necessary to add a way to configure
(and possibly, but more time-consuming, manage) the overlays,
adding individual directories to the include file search path is already
implemented.

A useful addition to that would be more fine-grained selection
of include files (e.g. ``include pkg/* if installed``,
or a ``autodetect`` script in the repo which creates a list of
include files).


eclass
^^^^^^

Similar to e.g. ``bash-completion-r1.eclass``,
``kernelconfig.eclass`` would offer ``dokernelconfig/newkernelconfig``
for installing *feature set* files:

.. code:: bash

    # ... eclass header ...

    # @FUNCTION: _kernelconfig_get_include_dir
    # @INTERNAL
    # @USAGE: [relative_path]
    # @DESCRIPTION:
    # Get the path to kernelconfig's include dir, or a subdirectory thereof.
    _kernelconfig_get_include_dir() {
        debug-print-function ${FUNCNAME} "${@}"

        # FIXME: EPREFIX?
        echo "${EPREFIX}/usr/share/kernelconfig/include${2:+/${2#/}}"
    }

    # @FUNCTION: kernelconfig_get_pkg_include_dir
    # @USAGE:
    # @DESCRIPTION:
    # Get the path to kernelconfig's dir for package-related include files.
    kernelconfig_get_pkg_include_dir() {
        debug-print-function ${FUNCNAME} "${@}"

        _kernelconfig_get_include_dir pkg
    }

    # @FUNCTION: dokernelconfig
    # @USAGE: file [...]
    # @DESCRIPTION:
    # Install kernelconfig include files.
    dokernelconfig() {
        debug-print-function ${FUNCNAME} "${@}"

        (
            insinto "$(kernelconfig_get_pkg_include_dir)"
            doins "${@}"
        )
    }

    # @FUNCTION: newkernelconfig
    # @USAGE: file newname
    # @DESCRIPTION:
    # Install a kernelconfig include file under a new name.
    newkernelconfig() {
        debug-print-function ${FUNCNAME} "${@}"

        (
            insinto "$(kernelconfig_get_pkg_include_dir)"
            newins "${@}"
        )
    }



The eclass could also offer functions for creating *feature set* files.
A ``CONFIG_CHECK -> feature set file`` converter would be useful
(overlaps with `Retrieval of Recommended Options`_).
