# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import re

from .._base import srcinfo

from . import kversion

__all__ = ["KernelInfo"]


class KernelInfo(srcinfo.SourceInfo):
    """
    Kernel sources information object - srctree, arch, kernelversion.

    After creating the object, its attributes need to be read
    from the kernel srctree with prepare():

       >>> kinfo = KernelInfo("/usr/src/linux")
       >>> kinfo.prepare()

       >>> kinfo.kernelversion
       KernelVersion('4.7.1')
       >>> kinfo.name
       'Psychotic Stoned Sheep'


    @cvar SRCARCH_MAP:  a partial arch to srcarch mapping
    @type SRCARCH_MAP:  C{dict} :: C{str} => C{str}


    @ivar karch:          target kconfig architecture
    @type karch:          C{str} or C{None}
    @ivar srcarch:        target (kconfig) source architecture
    @type srcarch:        C{str} or C{None}
    @ivar kernelversion:  (real) version of the kernel sources,
                          read from <srctree>/Makefile
    @type kernelversion:  L{kversion.KernelVersion} or C{None}

    @ivar real_kernelversion:  readonly alias to kernelversion
                               (KernelInfoVersionOverrideProxy compatibility)
    @type real_kernelversion:  L{kversion.KernelVersion} or C{None}

    @ivar name:           Linux kernel name (readonly property)
    @type name:           C{str} or C{None}
    """

    SRCARCH_MAP = {
        "i386":    "x86",
        "x86_64":  "x86",
        "sparc32": "sparc",
        "sparc64": "sparc",
        "sh64":    "sh",
        "tilegx":  "tile",
        "tilepro": "tile",
    }

    @classmethod
    def calculate_arch(cls):
        """Determines the default target architecture using os.uname().

        @return:  arch
        @rtype:   C{str}
        """
        return os.uname().machine

    @classmethod
    def calculate_srcarch(cls, karch):
        """Determines the SRCARCH from ARCH.

        @param karch:  kconfig arch
        @type  karch:  C{str}

        @return:  srcarch
        @rtype:   C{str}
        """
        if not karch:
            raise ValueError()

        return cls.SRCARCH_MAP.get(karch, karch)
    # --- end of calculate_srcarch (...) ---

    @classmethod
    def calculate_karch(cls, subarch):
        """Determines the ARCH from SUBARCH.

        This is a no-op.

        @param subarch:  subarch
        @type  subarch:  C{str}

        @return:  kconfig arch
        @rtype:   C{str}
        """
        if not subarch:
            raise ValueError()

        return subarch
    # --- end of calculate_karch (...) ---

    @classmethod
    def calculate_subarch(cls, march):
        """Determines the SUBARCH from a machine arch as printed by "uname -m".

        SUBARCH can be used to calculate can be used to calculate ARCH,
        which in turn can be used to calculate SRCARCH.

        @raises: ValueError if machine arch is empty

        @param march:  machine arch
        @type  march:  C{str}

        @return: subarch
        @rtype:  C{str}
        """
        if not march:
            raise ValueError()

        # loosely mirroring the SUBARCH calculation
        # from linux-sources' Makefile
        #
        # a big difference to the original variant
        # is that match patterns are not chained.
        match = re.match(
            (
                r'^(?:'
                r'(?P<x86>(?:i.86|x86_64))'
                r'|(?P<sparc64>(?:sun4u))'
                r'|(?P<arm>(?:arm.*|sa110))'
                r'|(?P<s390>(?:s390x))'
                r'|(?P<parisc>(?:parisc64))'
                r'|(?P<powerpc>(?:ppc.*))'
                r'|(?P<mips>(?:mips.*))'
                r'|(?P<sh>(?:sh[234].*))'
                r'|(?P<arm64>(?:aarch64.*))'
                r')$'
            ),
            march
        )

        if match:
            subarchs = [k for k, v in match.groupdict().items() if v]
            if len(subarchs) == 1:
                return next(iter(subarchs))
            elif not subarchs:
                raise AssertionError(
                    "matched march, but no named group feels responsible"
                )
            else:
                raise AssertionError(
                    "matched march, got multiple possible subarchs"
                )
            # --
        else:
            return march
    # --- end of calculate_subarch (...) ---

    @property
    def name(self):
        kver = self.kernelversion
        return kver.name if kver is not None else None
    # --- end of property name (...) ---

    @property
    def real_kernelversion(self):
        return self.kernelversion
    # --- end of property real_kernelversion (...) ---

    def __init__(self, srctree, arch=None, karch=None, srcarch=None, **kwargs):
        """Constructor.

        Note: it is not advisable to specify arch parameters without
              also specifying the arch parameters they depend on.
              For example, when passing a non-empty karch,
              arch should also be set.

        @param   srctree:  path to the kernel sources
        @type    srctree:  C{str}
        @keyword arch:     target architecture.
                           Defaults to None (-> autodetect using os.uname()).
        @type    arch:     C{str} or C{None}
        @keyword karch:    target kconfig architecture.
                           Defaults to None (-> autodetect from arch).
        @type    karch:    C{str} or C{None}
        @keyword srcarch:  target (kconfig) source architecture.
                           It is not necessary to specifiy the srcarch,
                           as it can be derived from arch.
                           Defaults to None (-> autodetect).
        @type    srcarch:  C{str} or C{None}
        @param   kwargs:   additional keyword arguments
                           for inherited constructor (logger)
        @type    kwargs:   C{dict} :: C{str} => _
        """
        super().__init__(srctree, **kwargs)
        self.arch = arch
        self.subarch = None
        self.karch = karch
        self.srcarch = srcarch
        self.kernelversion = None
    # --- end of __init__ (...) ---

    def prepare(self):
        if not self.arch:
            self.arch = self.calculate_arch()
            self.logger.debug("detected target architecture %s", self.arch)
        # --

        if not self.karch:
            if not self.subarch:
                self.subarch = self.calculate_subarch(self.arch)
                self.logger.debug("detected SUBARCH=%s", self.subarch)
            # --

            self.karch = self.calculate_karch(self.subarch)
            self.logger.debug("detected kernel ARCH=%s", self.karch)
        # -- else keep subarch possibly None

        if not self.srcarch:
            self.srcarch = self.calculate_srcarch(self.karch)
            self.logger.debug("detected SRCARCH=%s", self.srcarch)
        # --

        if not self.kernelversion:
            self.kernelversion = kversion.KernelVersion.new_from_makefile(
                self.get_filepath("Makefile")
            )
            self.logger.debug("detected KERNELVERSION=%s", self.kernelversion)
        # --

        self.setenv()
    # --- end of prepare (...) ---

    def get_toplevel_kconfig_filepath(self):
        return self.get_filepath("Kconfig")
    # --- end of get_toplevel_kconfig_filepath (...) ---

    def iter_env_vars(self):
        return [
            ('ARCH', self.karch),
            ('SRCARCH', self.srcarch),
            ('srctree', self.srctree),
            ('KERNELVERSION', self.kernelversion)
        ]
    # --- end of iter_env_vars (...) ---

    def iter_make_vars(self):
        return [
            ('ARCH', self.subarch or self.karch)
        ]
    # --- end of iter_make_vars (...) ---

    def check_supports_out_of_tree_build(self):
        return True

    def iter_out_of_tree_build_make_vars(self, build_dir):
        return [
            ('O', build_dir)
        ]

    def iter_target_arch(self):
        # FIXME: generator instead of list return
        #        (here and in the other methods)
        return [
            ("arch", self.arch),
            ("subarch", self.subarch),
            ("karch", self.karch),
            ("srcarch",  self.srcarch)
        ]

    def get_defconfig_target(self, arg=None):
        if arg:
            raise NotImplementedError("specialized defconfig target")

        return "defconfig"
    # ---

    def pretend_kernelversion(self, kernelversion):
        """
        Creates a kernel info proxy object that pretends
        to have a different kernel version.

        It provides a subset of the attributes and methods of this object,
        the "kernelversion" attribute returns the fake version
        and the "real_kernelversion" attribute returns the original version.

        Methods that involve the kernel version of the original object
        are either overridden or raise a ProxiedMethodNotAvailable exception
        (sub-of TypeError).

        Attribute access is rerouted via __getattr__() and does not get cached.
        Thus, attribute updates are propagated to the proxy,
        but there is some overhead on each and every attr access.

        Also, isinstance, issubclass will not work,
        and dir(<proxy obj>) will not return a complete attr list.

        @param kernelversion:  fake kernelversion,
                               either a kernel version object,
                               a version string ("4.7.1"),
                               or a version code int (0x40701).
                               Version code strings are not supported.
        @type  kernelversion:  L{KernelVersion} | C{str} | C{int}

        @return:  kernel info w/ fake kernelversion (proxy object)
        @rtype:   L{KernelInfoVersionOverrideProxy}
        """
        return KernelInfoVersionOverrideProxy(self, kernelversion)

# --- end of KernelInfo ---


class KernelInfoVersionOverrideProxy(srcinfo.SourceInfoProxy):
    __slots__ = ["_kernelversion"]  # and _source_info from super

    def __init__(self, kernel_info, kernelversion):
        super().__init__(kernel_info)
        self._kernelversion = kernelversion

    @property
    def name(self):
        return self._kernelversion.name  # which is probably None
    # --- end of property name (...) ---

    @property
    def kernelversion(self):
        return self._kernelversion

    @property
    def real_kernelversion(self):
        return self._source_info.kernelversion

    def prepare(self):
        # Would be OK to call if KernelInfo.prepare() did not call setenv(),
        # the set default kernelversion code does not affect the proxy.
        raise srcinfo.ProxiedMethodNotAvailable()

    def iter_env_vars(self):
        # the env vars are needed for lkc functionality only
        # (mostly kconfig parsing), this shouldn't affect the use case of
        # this proxy, which is currently "configuration sources" only
        raise srcinfo.ProxiedMethodNotAvailable()

# --- end of KernelInfoVersionOverrideProxy ---
