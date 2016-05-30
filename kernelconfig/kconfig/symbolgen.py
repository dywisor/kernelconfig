# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ..abc import loggable
from . import symbol
from . import symbols
from . import symbolexpr
from . import lkconfig  # pylint: disable=E0611

__all__ = ["KconfigSymbolGenerator"]


class KconfigSymbolExpressionBuilder(loggable.AbstractLoggable):
    """Converts 'C' struct expr/ExprView objects to 'Python' Expr objects."""

    SYM_CMP_CLS_MAP = {
        lkconfig.ExprView.E_EQUAL: symbolexpr.Expr_SymbolEQ,
        lkconfig.ExprView.E_UNEQUAL: symbolexpr.Expr_SymbolNEQ,
        lkconfig.ExprView.E_LTH: symbolexpr.Expr_SymbolLTH,
        lkconfig.ExprView.E_LEQ: symbolexpr.Expr_SymbolLEQ,
        lkconfig.ExprView.E_GTH: symbolexpr.Expr_SymbolGTH,
        lkconfig.ExprView.E_GEQ: symbolexpr.Expr_SymbolGEQ,
    }

    def create(self, top_expr_view):
        """Recursively converts an ExprView to an Expr.

        @param top_expr_view:  struct expr view object
        @type  top_expr_view:  L{ExprView}

        @return: expr
        @rtype:  subclass of L{Expr}
        """
        sym_cmp_cls_map = self.SYM_CMP_CLS_MAP
        logger = self.logger

        def expand_expr(eview):
            """Recursively expands/converts an ExprView.

            Recursive: expand_expr -> _
            """
            nonlocal logger
            nonlocal sym_cmp_cls_map

            def expand_sym(sym):
                """Expands a E_SYMBOL-type ExprView.

                Non-recursive.

                @param sym:  symbol view object
                @type  sym:  L{SymbolView}

                @rtype: L{Expr_Symbol}
                """
                if not sym.name:
                    # meta symbols
                    return None
                else:
                    return symbolexpr.Expr_Symbol(sym.name)
            # ---

            def expand_sym_cmp(sym_cmp_cls, lsym, rsym):
                """Expands a E_EQUAL/E_UNEQUAL-type ExprView.

                Non-recursive.

                @param sym_cmp_cls:  Expr class
                @type  sym_cmp_cls:  subclass of L{_Expr_SymbolValueComparison}
                @param lsym:         symbol view object (left operand)
                @type  lsym:         L{SymbolView}
                @param rsym:         symbol view object (right operand)
                @type  rsym:         L{SymbolView}

                @return:  Expr
                @rtype:   sym_cmp_cls
                """
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
                """Recursively expands a symbol or ExprView,
                depending on which param is not None.

                Recursive: expand_expr_or_sym -> expand_expr -> _

                Note: at least one out of the two parameters {subeview,sym}
                      must be None.
                      This is guaranteed by how SymbolView.get_expr() works.

                @param subeview:  expr view object, may be None
                @type  subeview:  L{ExprView} or C{None}
                @param sym:       symbol view object, may be None
                @type  sym:       L{SymbolView} or C{None}

                @return: expanded expression
                @rtype:  subclass of L{Expr}
                """
                if sym is not None:
                    assert subeview is None
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

            elif etype == eview.E_SYMBOL:
                expr = symbolexpr.Expr_Symbol(
                    expand_sym(lsym)
                )

            else:
                try:
                    sym_cmp_cls = sym_cmp_cls_map[etype]
                except KeyError:
                    raise NotImplementedError(etype) from None

                expr = expand_sym_cmp(sym_cmp_cls, lsym, rsym)
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
    """Creates kconfig symbols using the kconfig parser
    from the linux kernel sources.

    Use KconfigSymbolGenerator(source_info).get_symbols()
    to read kconfig symbols from a Kconfig file
    and create a KconfigSymbols instance.

    Note: due to how the lkc parser processes Kconfig files,
          some environment variables need to be modified,
          namely srctree, ARCH, SRCARCH and KERNELVERSION.


    @cvar SYMBOL_TYPE_TO_CLS_MAP:  mapping from lkc symbol type to symbol class
    @type SYMBOL_TYPE_TO_CLS_MAP:  C{dict} :: C{int} => C{type}|C{None}

    @cvar _did_read_lkc_symbols:   class-wide variable that is used to remember
                                   whether lkconfig.read_symbols() has been
                                   called, which should only be done once
                                   per script run/process.
    @type _did_read_lkc_symbols:   C{bool}

    @ivar source_info:  object that provides some information about the
                        kconfig structure being parsed
    @type source_info:  subclass of L{SourceInfo}

    @ivar _symbols:     kconfig symbols data structure
    @type _symbols:     L{KconfigSymbols}
    @ivar _dir_deps:    a symbol -> dir_dep mapping,
                        used for linking symbols to Expr objects
    @type _dir_deps:    C{dict} :: L{AbstractKconfigSymbol} => L{Expr}
    @ivar _rev_deps:    a symbol -> rev_dep mapping,
                        used for linking symbols to Expr objects
    @type _rev_deps:    C{dict} :: L{AbstractKconfigSymbol} => L{Expr}
    """

    SYMBOL_TYPE_TO_CLS_MAP = {
        lkconfig.S_TRISTATE:    symbol.TristateKconfigSymbol,
        lkconfig.S_BOOLEAN:     symbol.BooleanKconfigSymbol,
        lkconfig.S_STRING:      symbol.StringKconfigSymbol,
        lkconfig.S_INT:         symbol.IntKconfigSymbol,
        lkconfig.S_HEX:         symbol.HexKconfigSymbol,
        lkconfig.S_OTHER:       None
    }

    _did_read_lkc_symbols = False

    def __init__(self, source_info, **kwargs):
        super().__init__(**kwargs)
        self.source_info = source_info
        self._symbols = symbols.KconfigSymbols()
        self._dir_deps = {}
        self._rev_deps = {}
    # --- end of __init__ (...) ---

    def read_lkc_symbols(self):
        """Instructs the lkc parser to read kconfig symbols.

        No-op if _did_read_lkc_symbols is True.

        @return: None (implicit)
        """
        if not self.__class__._did_read_lkc_symbols:
            self.__class__._did_read_lkc_symbols = True
            self._read_lkc_symbols()
    # --- end of read_lkc_symbols (...) ---

    def get_lkc_symbols(self):
        """Gets SymbolView objects from the lkc parser.

        @return: list of symbol view objects
        @rtype:  list of L{SymbolView}
        """
        self.read_lkc_symbols()
        return self._get_lkc_symbols()
    # --- end of get_lkc_symbols (...) ---

    def _prepare_symbols(self):
        """
        Imports kconfig symbols from the lkc parser
        and adds them to self._symbols.

        Also collects dependencies, but does not "link" them to symbols,
        which needs to be done after reading all symbols.
        """
        get_symbol_cls = self.SYMBOL_TYPE_TO_CLS_MAP.__getitem__

        expr_builder = self.create_loggable(
            KconfigSymbolExpressionBuilder, logger_name="ExpressionBuilder"
        )

        kconfig_symbols = self._symbols
        dir_deps = self._dir_deps
        rev_deps = self._rev_deps

        for sym_view in self.get_lkc_symbols():
            sym_cls = get_symbol_cls(sym_view.s_type)

            if sym_view.name:
                # do not create nameless symbols
                sym = sym_cls(sym_view.name)

                kconfig_symbols.add_symbol(sym)
                dir_deps[sym] = expr_builder.create(sym_view.get_dir_dep())
                rev_deps[sym] = expr_builder.create(sym_view.get_rev_dep())
            # --
        # --
    # --- end of _prepare_symbols (...) ---

    def _link_deps(self):
        """
        Links the dependencies of all symbols to symbols,
        so that they can be evaluated.

        Reports missing symbol names via self.logger.
        """
        symbol_names_missing = set()

        for sym, dep_expr in self._dir_deps.items():
            if dep_expr is not None and sym.dir_dep is None:
                dep_expr.expand_symbols_shared(
                    self._symbols, symbol_names_missing
                )
                sym.dir_dep = dep_expr
        # --

        for sym, dep_expr in self._rev_deps.items():
            if dep_expr is not None and sym.rev_dep is None:
                dep_expr.expand_symbols_shared(
                    self._symbols, symbol_names_missing
                )
                sym.rev_dep = dep_expr
        # --

        if symbol_names_missing:
            # FIXME: reduce log level,
            #        sym-names-missing includes constant values (n,m,y,0,1)
            self.logger.error(
                "missing symbols: %s", ", ".join(sorted(symbol_names_missing))
            )
    # --- end of _link_deps (...) ---

    def get_symbols(self):
        """
        Imports Kconfig symbols, collects and expand dependencies,
        and returns the result as KconfigSymbols object.

        @return: kconfig symbols
        @rtype:  L{KconfigSymbols}
        """
        self._prepare_symbols()
        self._link_deps()
        return self._symbols
    # --- end of get_symbols (...) ---

    def _read_lkc_symbols(self):
        """Instructs the lkc parser to read kconfig symbols.
        Unsafe, use read_lkc_symbols().
        """
        lkconfig.read_symbols(
            self.source_info.get_toplevel_kconfig_filepath()
        )
    # --- end of _read_lkc_symbols (...) ---

    def _get_lkc_symbols(self):
        """Instructs the lkc parser to return a list of symbol view objects.
        Does not make an attempt at reading the symbols, use get_lkc_symbols().
        """
        return lkconfig.get_symbols()
    # --- end of _get_lkc_symbols (...) ---

# --- end of KconfigSymbolGenerator ---
