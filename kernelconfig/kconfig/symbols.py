# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from .abc import symbols as _symbols_abc

__all__ = ["KconfigSymbols"]


class KconfigSymbols(_symbols_abc.AbstractKconfigSymbols):

    def __init__(self):
        super().__init__()
        self.name_map = {}  # this could be a weak-value weakref dict
        self._symbols = set()

    def normalize_symbol_name(self, sym_name):
        return sym_name.upper()

    def get_symbol(self, sym):
        # check membership in _symbols
        if sym in self._symbols:
            return sym
        else:
            raise KeyError(sym)

    def get_symbol_by_name(self, name):
        return self.name_map[self.normalize_symbol_name(name)]

    def __iter__(self):
        return iter(self._symbols)

    def __len__(self):
        return len(self._symbols)   # len(_symbols) >= len(name_map)

    def _add_symbol(self, sym_name_key, sym):
        if sym_name_key is self.name_map:
            raise KeyError("redefiniton of named symbol %r" % sym_name_key)

        if sym in self._symbols:
            raise KeyError("redefinition of symbol %r" % sym)

        if sym_name_key:
            self.name_map[sym_name_key] = sym

        self._symbols.add(sym)

        return sym
    # ---

# --- end of KconfigSymbols ---
