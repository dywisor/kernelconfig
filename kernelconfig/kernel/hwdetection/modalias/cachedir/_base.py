# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import re
import stat


from .....abc import loggable
from .....util import fspath
from .....util import misc
from .....util import objcache

from . import exc
from . import util


__all__ = [
    "ModaliasCacheBase",
    "ModaliasCacheKey",
    "ModaliasCacheEntryInfo",
]


_ModaliasCacheKey = collections.namedtuple(
    "ModaliasCacheKey", "kernelversion arch"
)


_ModaliasCacheEntryInfo = collections.namedtuple(
    "ModaliasCacheEntryInfo", "filepath is_file cache_key"
)


class ModaliasCacheEntryInfo(_ModaliasCacheEntryInfo):

    @property
    def arch(self):
        return self.cache_key.arch

    @property
    def kernelversion(self):
        return self.cache_key.kernelversion

# ---


class ModaliasCacheKey(_ModaliasCacheKey):

    KVER_OBJ_CACHE = objcache.ObjectCache()

    @classmethod
    def decode(cls, key_str):
        key_components = key_str.split("__")

        if key_components:
            arch_key = None
            if len(key_components) > 1:
                arch_key = key_components.pop()

            kernelversion = cls.KVER_OBJ_CACHE.get(
                util.create_kernelversion_noerr, key_components.pop()
            )

            # other key components are ignored

            if kernelversion:
                return cls(arch=arch_key, kernelversion=kernelversion)
        # --

        return None
    # --- end of decode (...) ---

    def encode(self):
        forbidden_seq = re.compile(r'(?:__)|(?:/)')

        def strconvert(arg):
            str_val = str(arg)
            if forbidden_seq.search(str_val):
                raise exc.ModaliasCacheError(
                    "invalid cache key element", str_val
                )
            return str_val
        # ---

        return "__".join((
            strconvert(self.kernelversion),
            strconvert(self.arch)
        ))
    # ---

    def __str__(self):
        return self.encode()

# ---


class ModaliasCacheBase(loggable.AbstractLoggable):

    CACHE_DIR_RELPATH = "modalias"

    def iter_cache_dir_entries(self, *, cache_search_dirs=None):
        def iter_candidates():
            nonlocal cache_search_dirs

            for fname, filepath, stat_info in (
                cache_search_dirs.iglob_stat("*__*")
            ):
                # files end with ".txz"
                #  -- this can be adjusted to allow other tarballs,
                #     e.g. tarfile.is_tarfile() (which would open the file)

                if stat.S_ISREG(stat_info.st_mode) and fname.endswith(".txz"):
                    fbasename = fname.rpartition(".")[0]
                    yield (True, fbasename, filepath)

                elif stat.S_ISDIR(stat_info.st_mode):
                    yield (False, fname, filepath)
            # --
        # --- end of iter_candidates (...) ---

        if cache_search_dirs is None:
            cache_search_dirs = self.get_cache_search_dirs()

        for is_file, fbasename, filepath in iter_candidates():
            cache_key = ModaliasCacheKey.decode(fbasename)
            if cache_key is not None:
                yield ModaliasCacheEntryInfo(
                    filepath=filepath, is_file=is_file, cache_key=cache_key
                )
    # --- end of iter_cache_dir_entries (...) ---

    def __init__(self, install_info, source_info, **logger_kwargs):
        super().__init__(**logger_kwargs)
        self.install_info = install_info
        self.source_info = source_info
        self._cache_key_str = None
    # --- end of __init__ (...) ---

    def zap(self):
        self._cache_key_str = None

    def get_cache_file_path(self):
        return self.get_cache_dir_path("%s.txz" % self.get_cache_key_str())

    def get_cache_dirs(self, relpath=None):
        return self.install_info.get_cache_dirs(
            fspath.join_relpath(self.CACHE_DIR_RELPATH, relpath)
        )

    def get_cache_dir_path(self, relpath=None):
        return self.get_cache_dirs(relpath).get_path()

    def get_cache_search_dirs(self, relpath=None, check_exist=False):
        return self.install_info.get_cache_search_dirs(
            fspath.join_relpath(self.CACHE_DIR_RELPATH, relpath),
            check_exist=check_exist
        )

    def get_arch_keys(self):
        return misc.iter_dedup(
            filter(
                # skip unset arch attrs,
                # and also "usermode" archs
                lambda w: (w and w != "um"),
                (
                    self.source_info.arch,
                    self.source_info.subarch,
                    self.source_info.karch
                )
            )
        )
    # ---

    def get_cache_key_components(self):
        """
        Returns the 'ideal' cache key for the modalias info source as list.

        @return:  cache key components
        @rtype:   C{list} of C{object}
        """
        def get_arch_key():
            for arch_key in self.get_arch_keys():
                return arch_key
            raise exc.ModaliasCacheError("no arch cache key")
        # ---

        # the cache key consists of
        # * the kernel version
        # * the target arch, see get_arch_key() above
        return ModaliasCacheKey(
            kernelversion=self.source_info.kernelversion,
            arch=get_arch_key()
        )
    # --- end of get_cache_key_components (...) ---

    def _get_cache_key_str(self):
        """Returns the 'ideal' cache key for the modalias info source.
        This is mostly useful for storing new info sources.

        @return:  cache key (can be interpreted as relative fs path)
        @rtype:   C{str}
        """
        return self.get_cache_key_components().encode()
    # --- end of _get_cache_key_str (...) ---

    def get_cache_key_str(self):
        """See _get_cache_key_str(). This method adds result caching."""
        cache_key_str = self._cache_key_str
        if cache_key_str is None:
            cache_key_str = self._get_cache_key_str()
            self._cache_key_str = cache_key_str
        return cache_key_str
    # --- end of get_cache_key_str (...) ---

# --- end of ModaliasCacheBase ---
