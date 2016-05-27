# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections.abc

from .abc import symbol as _symbol_abc

__all__ = ["KconfigSymbols"]


class KconfigSymbols(collections.abc.Mapping):

    def __init__(self):
        super().__init__()
        self.name_map = {}  # this could be a weak-value weakref dict
        self._symbols = set()

    # def iter_match_key(self, key):
    #     return ()
    #
    # def match_key(self, *args, **kwargs):
    #     return list(self.iter_match_key(*args, **kwargs))

    def normalize_key(self, key):
        return key

    def __getitem__(self, key):
        if isinstance(key, _symbol_abc.AbstractKconfigSymbol):
            # key is a symbol, check membership in _symbols
            if key in self._symbols:
                return key
            else:
                raise KeyError(key)

        else:
            # key is assumed to be a symbol name
            return self.name_map[self.normalize_key(key)]
        # --
    # ---

    def __iter__(self):
        return iter(self.name_map)  # debatable, could also iter(_symbols)

    def __len__(self):
        return len(self._symbols)   # len(_symbols) > len(name_map)

    def _add_symbol(self, sym_name_key, sym):
        if sym_name_key is self.name_map:
            raise KeyError("redefiniton of named symbol %r" % sym_name_key)

        if sym in self._symbols:
            raise KeyError("redefinition of symbol %r" % sym)

        if sym_name_key:
            self.name_map[sym_name_key] = sym

        self._symbols.add(sym)
    # ---

    def add_symbol(self, sym):
        assert isinstance(sym, _symbol_abc.AbstractKconfigSymbol)

        if not sym.name:
            # not a technical requirement,
            # but storing nameless symbols doesn't make much sense
            raise ValueError("symbol without a name")
        # --

        return self._add_symbol(sym.name, sym)
    # ---

    def add_unknown_symbol(self, sym_value_type, sym_name):
        assert issubclass(sym_value_type, _symbol_abc.AbstractKconfigSymbol)

        sym = sym_value_type(sym_name)
        return self.add_symbol(sym)
    # ---

# --- end of KconfigSymbols ---
