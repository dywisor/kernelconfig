# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ..abc import loggable
from . import symbol
from . import symbolexpr
from . import lkconfig

__all__ = ["KconfigSymbolGenerator"]


class KconfigSymbolExpressionBuilder(loggable.AbstractLoggable):

    def create(self, top_expr_view):
        logger = self.logger

        def expand_expr(eview):
            nonlocal logger

            def expand_sym(sym):
                if not sym.name:
                    # meta symbols
                    return None
                else:
                    return symbolexpr.Expr_Symbol(sym.name)
            # ---

            def expand_sym_cmp(sym_cmp_cls, lsym, rsym):
                nonlocal logger

                lsym_expr = expand_sym(lsym)
                rsym_expr = expand_sym(rsym)

                if lsym_expr is None or rsym_expr is None:
                    logger.debug("dropping %r expr" % sym_cmp_cls)
                    return None
                else:
                    return sym_cmp_cls(lsym_expr, rsym_expr)
            # ---

            def expand_expr_or_sym(subeview, sym):
                if sym is not None:
                    return expand_sym(sym)
                elif subeview is not None:
                    return expand_expr(subeview)
                else:
                    return None
            # ---

            if eview is None:
                raise AssertionError()
            # --

            etype, lexpr, lsym, rexpr, rsym = eview.get_expr()

            if etype == eview.E_OR:
                expr = symbolexpr.Expr_Or()
                expr.add_expr(expand_expr_or_sym(lexpr, lsym))
                expr.add_expr(expand_expr_or_sym(rexpr, rsym))

            elif etype == eview.E_AND:
                expr = symbolexpr.Expr_And()
                expr.add_expr(expand_expr_or_sym(lexpr, lsym))
                expr.add_expr(expand_expr_or_sym(rexpr, rsym))

            elif etype == eview.E_NOT:
                subexpr = expand_expr_or_sym(lexpr, lsym)
                # subexpr may be None if the not-expr references
                # unknown symbols
                if subexpr is not None:
                    expr = symbolexpr.Expr_Not(subexpr)
                else:
                    logger.debug("dropping empty NOT expr")
                    expr = None

            elif etype == eview.E_EQUAL:
                expr = symbolexpr.Expr_SymbolEQ(
                    expand_sym(lsym), expand_sym(rsym)
                )

            elif etype == eview.E_UNEQUAL:
                expr = symbolexpr.Expr_SymbolNEQ(
                    expand_sym(lsym), expand_sym(rsym)
                )

            elif etype == eview.E_SYMBOL:
                expr = symbolexpr.Expr_Symbol(
                    expand_sym(lsym)
                )

            else:
                raise NotImplementedError(etype)
            # --

            return expr
        # ---

        if top_expr_view.e_type == top_expr_view.E_NONE:
            return None
        else:
            return expand_expr(top_expr_view)
    # ---
# ---


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
