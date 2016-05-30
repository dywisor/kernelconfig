# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os
import re

from ..abc import loggable
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
        norm_relpath = (
            os.path.normpath(relpath.strip(os.path.sep))
            if relpath else None
        )
        if norm_relpath and norm_relpath != ".":
            return os.path.join(self.srctree, norm_relpath)
        else:
            return self.srctree
    # --- end of get_filepath (...) ---

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

# --- end of SourceInfo ---


class KernelInfo(SourceInfo):
    """
    @cvar SRCARCH_MAP:  a partial arch to srcarch mapping
    @type SRCARCH_MAP:  C{dict} :: C{str} => C{str}


    @ivar arch:           target architecture
    @type arch:           C{str} or C{None}
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
    def calculate_srcarch(cls, arch):
        """Determines the SRCARCH from ARCH.

        @param arch:  arch
        @type  arch:  C{str}

        @return:  srcarch
        @rtype:   C{str}
        """
        if not arch:
            raise ValueError()

        return cls.SRCARCH_MAP.get(arch, arch)
    # --- end of calculate_srcarch (...) ---

    @classmethod
    def calculate_arch(cls, subarch):
        """Determines the ARCH from SUBARCH.

        This is a no-op.

        @param subarch:  subarch
        @type  subarch:  C{str}

        @return:  arch
        @rtype:   C{str}
        """
        if not subarch:
            raise ValueError()

        return subarch
    # --- end of calculate_arch (...) ---

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

    def __init__(self, srctree, arch=None, srcarch=None, **kwargs):
        """Constructor.

        @param   srctree:  path to the kernel sources
        @type    srctree:  C{str}
        @keyword arch:     target architecture.
                           Defaults to None (-> autodetect using os.uname()) .
        @type    arch:     C{str} or C{None}
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
        self.srcarch = srcarch
        self.kernelversion = None
    # --- end of __init__ (...) ---

    def prepare(self):
        if not self.arch:
            self.arch = self.calculate_arch(
                self.calculate_subarch(os.uname().machine)
            )
            self.logger.debug("detected ARCH=%s", self.arch)
        # --

        if not self.srcarch:
            self.srcarch = self.calculate_srcarch(self.arch)
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
            ('ARCH', self.arch),
            ('SRCARCH', self.srcarch),
            ('srctree', self.srctree),
            ('KERNELVERSION', self.kernelversion)
        ]
    # --- end of iter_env_vars (...) ---

# --- end of KernelInfo ---
