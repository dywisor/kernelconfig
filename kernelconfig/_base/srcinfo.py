# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os

from ..abc import loggable
from ..util import fspath
from ..util import misc


__all__ = ["SourceInfo", "SourceInfoProxy", "ProxiedMethodNotAvailable"]


class ProxiedMethodNotAvailable(TypeError):
    pass
# ---


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

    def get_path(self):
        return self.srctree
    # --- end of get_path (...) ---

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
        """Returns whether the sources support out-of-tree building.

        Derived classes must implement this method.

        @return:  True if out-of-tree building is supported, else False.
        @rtype:   C{bool}
        """
        return False

    @abc.abstractmethod
    def iter_out_of_tree_build_make_vars(self, build_dir):
        """
        Returns an iterable of varname, value pairs
        that are relevant for out-of-tree building.

        Whether out-of-tree building is supported, should be checked with
        check_supports_out_of_tree_build() before calling this method.

        Derived classes must implement this method.
        They may raise a TypeError if out-of-tree building is not supported.

        @raises TypeError:  if out-of-tree building not supported

        @param build_dir:  path to the build directory
                           (non-empty, does not have to exist)
        @type  build_dir:  C{str}

        @return:  iterable|genexpr|iterator of 2-tuples (varname, value)
        @rtype:   iterable of 2-tuple (C{str}, object)
        """
        raise TypeError()

    @abc.abstractmethod
    def iter_target_arch(self):
        """
        @raises TypeError:  if not appropriate for this source info

        @return:  an iterable of target architectures,
                  ordered from most specific to least specific,
                  possibly containing duplicates - see iter_target_arch_dedup()
        @return:  iterable of C{str}  (usually)
        """
        raise TypeError()

    def iter_target_arch_dedup(self):
        """
        Same as iter_target_arch(),
        but deduplicates the target architecture candidates.
        """
        return misc.iter_dedup(self.iter_target_arch(), key=lambda xv: xv[1])

    def get_defconfig_target(self, arg=None):
        """Returns the name of the "best suited" make defconfig target.
        The optional arg may specify the requested target further.

        Returns None if no defconfig target is known.

        Raises a TypeError if not supported by this source info type.
        @raises TypeError:

        @keyword arg:  defconfig variant arg, defaults to None
        @type    arg:  C{str}

        @return:  defconfig target or None
        @rtype:   C{str} or C{None}
        """
        raise TypeError()

# --- end of SourceInfo ---


class SourceInfoProxy(object):
    __slots__ = ["_source_info"]

    def __init__(self, source_info):
        super().__init__()
        self._source_info = source_info

    def __getattr__(self, attr_name):
        if attr_name and attr_name[0] != "_":
            return getattr(self._source_info, attr_name)
        else:
            return super().__getattr__(self, attr_name)  # AttributeError
    # ---

# --- end of SourceInfoProxy ---
