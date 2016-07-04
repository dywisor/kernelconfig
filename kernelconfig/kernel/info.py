# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os
import re

from ..abc import loggable
from ..util import fspath
from ..util import misc
from . import kversion

__all__ = ["SourceInfo", "KernelInfo"]


class SourceInfo(loggable.AbstractLoggable):
    """
    An object that provides information about the source files being processed.

    @ivar srctree:  path to the source directory
    @type srctree:  C{str}
    """

    def __init__(self, srctree, **kwargs):
        super().__init__(**kwargs)
        self.srctree = srctree
    # --- end of __init__ (...) ---

    def get_filepath(self, relpath=None):
        """Interprets a path relative to the source directory and returns
        its absolute path.

        If no path is given, returns the path to the source directory.

        Note: the relpath parameter is always interpreted as relative path,
              even if it begins with os.path.sep.


        @param relpath:  path relative to the source directory or None
                         Defaults to None.
        @type  relpath:  C{str} or C{None}

        @return:  absolute filesystem path
        @rtype:   C{str}
        """
        return fspath.join_relpath(self.srctree, relpath)
    # --- end of get_filepath (...) ---

    def check_srctree(self):
        """Checks whether the srctree directory is present
        and could be an entity of the sources being processed.

        @return:  True or False
        @rtype:   C{bool}
        """
        return (
            self.srctree and os.path.isdir(self.srctree)
            and os.path.isfile(self.get_toplevel_kconfig_filepath())

        )
    # --- end of check_srctree (...) ---

    @abc.abstractmethod
    def get_toplevel_kconfig_filepath(self):
        """Returns the path to the top-level Kconfig file.

        @return: path to Kconfig file
        @rtype:  C{str}
        """
        raise NotImplementedError()
    # --- end of get_toplevel_kconfig_filepath (...) ---

    @abc.abstractmethod
    def prepare(self):
        """Prepares the source info object for further processing.
        This may involve reading files from srctree and needs to be
        called manually.

        @return: None (implicit)
        """
        raise NotImplementedError()
    # --- end of prepare (...) ---

    @abc.abstractmethod
    def iter_env_vars(self, **kwargs):
        """
        Returns an iterable of env varname, value pairs.
        This method may be also be a generator, or return an iterator.
        """
        raise NotImplementedError()
    # --- end of iter_env_vars (...) ---

    def iter_make_vars(self, **kwargs):
        return self.iter_env_vars(**kwargs)

    def setenv(self, dst_env=None, **kwargs):
        """Sets environment variables necessary for processing source files.

        @keyword dst_env:  environment var dict to modify.
                           May be None, in which case os.environ will be used.
                           Defaults to None.
        @type    dst_env:  C{None} or C{dict} :: C{str} => C{str}
        @param   kwargs:   additional keyword arguments for iter_env_vars()
        @type    kwargs:   C{dict} :: C{str} => C{str}

        @return: None (implicit)
        """
        if dst_env is None:
            dst_env = os.environ

        if dst_env is os.environ:   # catch dst_env=os.environ
            self.logger.debug("Setting environment variables in os.environ")

        for key, val in self.iter_env_vars(**kwargs):
            if val is not None:
                dst_env[key] = str(val)
            else:
                dst_env.pop(key, None)
            # --
        # --
    # --- end of setenv (...) ---

    def unsetenv(self, dst_env=None, **kwargs):
        """Unsets environment controlled by this source info object.

        @keyword dst_env:  environment var dict to modify.
                           May be None, in which case os.environ will be used.
                           Defaults to None.
        @type    dst_env:  C{None} or C{dict} :: C{str} => C{str}
        @param   kwargs:   additional keyword arguments for iter_env_vars()
        @type    kwargs:   C{dict} :: C{str} => C{str}

        @return: None (implicit)
        """
        if dst_env is None:
            dst_env = os.environ

        if dst_env is os.environ:   # catch dst_env=os.environ
            self.logger.debug("Unsetting environment variables in os.environ")

        for key, _ in self.iter_env_vars(**kwargs):
            dst_env.pop(key, None)
        # --
    # --- end of unsetenv (...) ---

    @abc.abstractmethod
    def check_supports_out_of_tree_build(self):
        return False

    @abc.abstractmethod
    def iter_out_of_tree_build_make_vars(self, build_dir):
        raise TypeError()

    @abc.abstractmethod
    def iter_target_arch(self):
        raise TypeError()

    def iter_target_arch_dedup(self):
        return misc.iter_dedup(self.iter_target_arch(), key=lambda xv: xv[1])

# --- end of SourceInfo ---


class KernelInfo(SourceInfo):
    """
    @cvar SRCARCH_MAP:  a partial arch to srcarch mapping
    @type SRCARCH_MAP:  C{dict} :: C{str} => C{str}


    @ivar karch:          target kconfig architecture
    @type karch:          C{str} or C{None}
    @ivar srcarch:        target (kconfig) source architecture
    @type srcarch:        C{str} or C{None}
    @ivar kernelversion:  version of the kernel sources
    @type kernelversion:  L{kversion.KernelVersion} or C{None}
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


# --- end of KernelInfo ---
