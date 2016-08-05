# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections.abc

from ....abc import loggable

from . import mkscanner
from .. import util


__all__ = ["ModulesMap"]


class ModulesMap(loggable.AbstractLoggable, collections.abc.Mapping):

    normalize_module_name = staticmethod(util.normalize_module_name)

    @property
    def is_loaded(self):
        return self._mk_modmap is not None

    def load(self):
        self._get_mk_modmap()
    # --- end of load (...) ---

    def __init__(self, source_info, **kwargs):
        super().__init__(**kwargs)
        self.source_info = source_info
        self._mk_modmap = None
    # --- end of __init__ (...) ---

    def __iter__(self):
        return iter(self._get_mk_modmap())

    def __len__(self):
        return len(self._get_mk_modmap())

    def __getitem__(self, key):
        normkey = self.normalize_module_name(key)

        mk_modmap = self._get_mk_modmap()
        return mk_modmap[normkey]
    # --- end of __getitem__ (...) ---

    def _get_mk_modmap(self):
        mk_modmap = self._mk_modmap
        if mk_modmap is None:
            mk_modmap = self._load_new_mk_modmap()
            self._mk_modmap = mk_modmap
        return mk_modmap
    # --- end of _get_mk_modmap (...) ---

    def _load_new_mk_modmap(self):
        scanner = self.create_loggable(
            mkscanner.ModuleConfigOptionsScanner, self.source_info
        )
        return scanner.get_module_options_map()
    # --- end of _load_new_mk_modmap (...) ---

# --- end of ModulesMap (...) ---
