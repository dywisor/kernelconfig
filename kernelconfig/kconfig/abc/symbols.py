# kernelconfig -- abstract description of Kconfig-related classes
# -*- coding: utf-8 -*-

import abc
import collections.abc

from . import symbol


__all__ = ["AbstractKconfigSymbols"]


class AbstractKconfigSymbols(collections.abc.Mapping):
    """The set of all kconfig symbols, which also offers dict-like
    subscription access by symbol and by name.
    """

    # @abc.abstractmethod
    # def iter_match_key(self, key):
    #     return ()
    #
    # @abc.abstractmethod
    # def match_key(self, *args, **kwargs):
    #     return list(self.iter_match_key(*args, **kwargs))

    @abc.abstractmethod
    def normalize_symbol_name(self, sym_name):
        """Converts a symbol name to a symbol name key,
        so that the symbol can be accessed more efficiently in
        get_symbol_by_name().

        @param sym_name:  symbol name, possibly already normalized
        @type  sym_name:  C{str}

        @return:  normalized symbol name
        @rtype:   usually C{str}
        """
        raise NotImplementedError()
    # --- end of normalize_symbol_name (...) ---

    @abc.abstractmethod
    def get_symbol(self, sym):
        """Returns the given symbol if it is part of the kconfig symbols set,
        and raises a KeyError otherwise.

        @raises KeyError:  if symbol is not a member

        @param symbol:  symbol
        @type  symbol:  subclass of AbstractKconfigSymbol

        @return:  symbol
        """
        raise NotImplementedError()
    # --- end of get_symbol (...) ---

    @abc.abstractmethod
    def get_symbol_by_name(self, name):
        """Returns the symbol referenced by the given name,
        it must be a member of this symbol set.

        @raises KeyError:  if symbol does not exist

        @param name:  symbol name, possibly normalized
        @type  name:  C{str}

        @return:  symbol
        @rtype:   subclass of AbstractKconfigSymbol
        """
        raise NotImplementedError()
    # --- end of get_symbol_by_name (...) ---

    def __getitem__(self, key):
        if isinstance(key, symbol.AbstractKconfigSymbol):
            return self.get_symbol(key)
        else:
            # key is assumed to be a symbol name
            return self.get_symbol_by_name(key)
    # ---

    @abc.abstractmethod
    def _add_symbol(self, sym_name_key, sym):
        """Adds a symbol and adds it to the name->symbol mapping using the
        given str key.

        @param sym_name_key:  symbol name key
        @type  sym_name_key:  C{str}
        @param sym:           symbol
        @type  sym:           subclass of AbstractKconfigSymbol

        @return:  symbol
        """
        raise NotImplementedError()
    # --- end of _add_symbol (...) ---

    def add_symbol(self, sym):
        """Adds a symbol and adds it to the name->symbol mapping.

        @raises ValueError:  if symbol has no name

        @param sym:  symbol
        @type  sym:  subclass of AbstractKconfigSymbol

        @return:  symbol
        """
        assert isinstance(sym, symbol.AbstractKconfigSymbol)

        if not sym.name:
            # not a technical requirement,
            # but storing nameless symbols doesn't make much sense
            raise ValueError("symbol without a name")
        # --

        return self._add_symbol(self.normalize_symbol_name(sym.name), sym)
    # --- end of add_symbol (...) ---

    def add_unknown_symbol(self, sym_value_type, sym_name):
        """Creates and adds a new symbol.

        @param sym_value_type:  symbol constructor (symbol descriptor class)
        @type  sym_value_type:  type, subclass of AbstractKconfigSymbol
        @param sym_name:        the symbol's name
        @type  sym_name:        C{str}

        @return:  the created symbol
        @rtype:   sym_value_type
        """
        assert issubclass(sym_value_type, symbol.AbstractKconfigSymbol)

        sym = sym_value_type(sym_name)
        return self.add_symbol(sym)
    # --- end of add_unknown_symbol (...) ---

# --- end of AbstractKconfigSymbols ---
