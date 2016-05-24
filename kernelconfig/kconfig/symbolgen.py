# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ..abc import loggable
from . import symbol
from . import lkconfig

__all__ = ["KconfigSymbolGenerator"]


class KconfigSymbolGenerator(loggable.AbstractLoggable):
    SYMBOL_TYPE_TO_CLS_MAP = {
        lkconfig.S_TRISTATE:    symbol.TristateKconfigSymbol,
        lkconfig.S_BOOLEAN:     symbol.BooleanKconfigSymbol,
        lkconfig.S_STRING:      symbol.StringKconfigSymbol,
        lkconfig.S_INT:         symbol.IntKconfigSymbol,
        lkconfig.S_HEX:         symbol.HexKconfigSymbol,
        lkconfig.S_OTHER:       None
    }

    _did_read_symbols = False

    def __init__(self, kernel_info, **kwargs):
        super().__init__(**kwargs)
        self.kernel_info = kernel_info
    # --- end of __init__ (...) ---

    def gen_symbols(self):
        if not self._did_read_symbols:
            self._did_read_symbols = True
            self._read_symbols()

        return self._gen_symbols()
    # --- end of gen_symbols (...) ---

    __iter__ = gen_symbols

    def _gen_symbols(self):
        get_symbol_cls = self.SYMBOL_TYPE_TO_CLS_MAP.__getitem__

        for sym_view in lkconfig.get_symbols():
            sym_cls = get_symbol_cls(sym_view.s_type)

            yield sym_cls(sym_view.name)
    # --- end of _gen_symbols (...) ---

    def _read_symbols(self):
        self.kernel_info.setenv()  # FIXME: not here
        self._symbols = lkconfig.read_symbols(
            self.kernel_info.get_filepath("Kconfig")
        )
    # --- end of _read_symbols (...) ---

# --- end of KconfigSymbolGenerator ---
