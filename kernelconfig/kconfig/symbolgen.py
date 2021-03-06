# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import logging

from ..abc import loggable
from ..abc import informed
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

    def _gen_createv(self, top_expr_views):
        _create = self.create

        for top_expr_view in top_expr_views:
            expr = _create(top_expr_view)
            if expr is not None:
                yield expr
        # --
    # ---

    def createv(self, top_expr_views):
        return list(self._gen_createv(top_expr_views))

    def _createv_junction(self, junction_cls, one_expr_cls, component_views):
        expr_iter = self._gen_createv(component_views)

        try:
            first_expr = next(expr_iter)
        except StopIteration:
            # no expr
            return None

        try:
            next_expr = next(expr_iter)
        except StopIteration:
            # one expr
            if one_expr_cls is None:
                return first_expr
            else:
                return one_expr_cls(first_expr)

        junction_expr = junction_cls(first_expr, next_expr)
        # add remaining exprs
        junction_expr.extend_expr(expr_iter)
        return junction_expr
    # --- end of _createv_junction (...) ---

    def createv_and(self, component_views):
        return self._createv_junction(
            symbolexpr.Expr_And, None, component_views
        )
    # ---

    def createv_or(self, component_views):
        return self._createv_junction(
            symbolexpr.Expr_Or, None, component_views
        )
    # ---

    def create(self, top_expr_view):
        """Recursively converts an ExprView to an Expr.

        @param top_expr_view:  struct expr view object
        @type  top_expr_view:  L{ExprView}

        @return: expr
        @rtype:  subclass of L{Expr}
        """
        sym_cmp_cls_map = self.SYM_CMP_CLS_MAP

        const_false = symbolexpr.Expr_Constant.get_instance(
            symbol.TristateKconfigSymbolValue.n
        )

        def expand_expr(eview):
            """Recursively expands/converts an ExprView.

            Recursive: expand_expr -> _
            """
            nonlocal sym_cmp_cls_map
            nonlocal const_false

            def expand_sym(sym):
                """Expands a E_SYMBOL-type ExprView.

                Non-recursive.

                @param sym:  symbol view object
                @type  sym:  L{SymbolView}

                @rtype: L{Expr_Symbol}
                """
                nonlocal const_false

                if not sym.name:
                    # meta symbols
                    return const_false
                else:
                    return symbolexpr.Expr_SymbolName(sym.name)
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
                return sym_cmp_cls(expand_sym(lsym), expand_sym(rsym))
            # ---

            def expand_expr_or_sym(subeview, sym):
                """Recursively expands a symbol or ExprView,
                depending on which param is not None.

                Recursive: expand_expr_or_sym -> expand_expr -> _

                Note: exactly one out of the two parameters {subeview,sym}
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
                    raise AssertionError()
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
                expr = symbolexpr.Expr_Not(expand_expr_or_sym(lexpr, lsym))

            elif etype == eview.E_SYMBOL:
                expr = expand_sym(lsym)

            else:
                try:
                    sym_cmp_cls = sym_cmp_cls_map[etype]
                except KeyError:
                    raise NotImplementedError(etype) from None

                expr = expand_sym_cmp(sym_cmp_cls, lsym, rsym)
            # --

            # Note: "return expr.simplify()" would hide missing symbols
            return expr
        # ---

        if top_expr_view is None:
            return None
        elif top_expr_view.e_type == top_expr_view.E_NONE:
            return None
        else:
            return expand_expr(top_expr_view).move_negation_inwards()
    # ---
# ---


class KconfigSymbolGenerator(informed.AbstractSourceInformed):
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
    @ivar _vis_deps:    a symbol -> vis_dep mapping
    @type _vis_deps:    C{dict} :: L{AbstractKconfigSymbol} => L{Expr}
    @ivar _def_deps:    a symbol -> intermediate symbol defaults mapping
                        "intermediate symbol defaults" are
                        2-tuples (dir_dep, vis_dep).
                        They are converted to L{KconfigSymbolDefault} objects
                        during the "link deps" phase.
    @type _def_deps:    C{dict} :: L{AbstractKconfigSymbol}
                                => C{list} of 2-tuple <L{Expr}>
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

    @classmethod
    def get_default_symbol_constants(cls):
        return {
            "n": symbol.TristateKconfigSymbolValue.n,
            "m": symbol.TristateKconfigSymbolValue.m,
            "y": symbol.TristateKconfigSymbolValue.y,
            "0": 0,
            "1": 1
        }
    # --- end of get_default_symbol_constants (...) ---

    def __init__(self, source_info, **kwargs):
        super().__init__(source_info=source_info, **kwargs)
        self._symbols = symbols.KconfigSymbols()
        self._dir_deps = {}
        self._vis_deps = {}
        self._def_deps = {}
    # --- end of __init__ (...) ---

    def read_lkc_symbols(self):
        """Instructs the lkc parser to read kconfig symbols.

        No-op if _did_read_lkc_symbols is True.

        @return: None (implicit)
        """
        # pylint: disable=W0212
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

    def constify_missing_symbol(self, name):
        """Converts the name of a missing symbol into a constant value.

        First, checks if the name is already a value and, if so,
        returns that value.

        Otherwise, defaults to symbol to tristate "n".

        @param name:  name of the missing symbol
        @type  name:  C{str}
        @return:      hashable value
        @rtype:       L{symbol.TristateKconfigSymbolValue} | C{int}
        """
        try:
            value_type, value = symbol.unpack_value_str(name)
        except ValueError:
            return symbol.TristateKconfigSymbolValue.n

        if value_type == symbol.KconfigSymbolValueType.v_unknown:
            # this cannot happen,
            # unpack_value_str() should have raised a ValueError
            raise AssertionError()

        elif value_type == symbol.KconfigSymbolValueType.v_string:
            # unpack_value_str() is strict when determing a string value type,
            # but don't allow string comparisons for now
            self.logger.warning(
                "string comparisons are not allowed: %r", value
            )
            return symbol.TristateKconfigSymbolValue.n
        else:
            return value
    # --- end of constify_missing_symbol (...) ---

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
        vis_deps = self._vis_deps
        def_deps = self._def_deps

        for sym_view in self.get_lkc_symbols():
            sym_cls = get_symbol_cls(sym_view.s_type)

            if sym_view.name:
                # do not create nameless symbols
                sym = sym_cls(sym_view.name)
                sym_prompts = sym_view.get_prompts()

                kconfig_symbols.add_symbol(sym)
                dir_deps[sym] = expr_builder.create(sym_view.get_dir_dep())
                vis_deps[sym] = expr_builder.createv_or(
                    (p[1] for p in sym_prompts)
                )

                # get symbol defaults
                #  keep dependency and visibility depepencies separate,
                #  visibility does not contribute to the default value
                #  except that it can limit a tristate "y" to "m" (and similar)
                #
                # spare the overhead if defaults
                # are not supported for the symbol (type)
                if sym.supports_defaults():
                    def_deps[sym] = [
                        (
                            expr_builder.create(def_dir_dep),
                            expr_builder.create(def_vis_dep),
                        )
                        for def_dir_dep, def_vis_dep in sym_view.get_defaults()
                    ]
                # --
            # --
        # --
    # --- end of _prepare_symbols (...) ---

    def _link_deps(self):
        """
        Links the dependencies of all symbols to symbols,
        so that they can be evaluated.

        Reports missing symbol names via self.logger.
        """
        def expand_once(symbol_map, constants):
            def expand_dep_dict(dep_dict, symbol_names_missing):
                nonlocal symbol_map, constants
                for sym_key in list(dep_dict):
                    dep_expr = dep_dict[sym_key]
                    if dep_expr is not None:
                        dep_dict[sym_key] = dep_expr.expand_symbols_shared(
                            symbol_map, constants, symbol_names_missing
                        )
            # ---

            def expand_def_dep_dict(def_dep_dict, symbol_names_missing):
                # def_dep_dict: sym -> list of 2-tuple (dir_dep, vis_dep)
                nonlocal symbol_map, constants
                for sym_key in list(def_dep_dict):
                    dep_exprv = def_dep_dict[sym_key]
                    if dep_exprv:
                        def_dep_dict[sym_key] = [
                            [
                                (
                                    dep_expr.expand_symbols_shared(
                                        symbol_map, constants,
                                        symbol_names_missing
                                    ) if dep_expr is not None else None
                                ) for dep_expr in dep_tuple
                            ]
                            for dep_tuple in dep_exprv
                        ]
            # ---

            symbol_names_missing = set()
            expand_dep_dict(self._dir_deps, symbol_names_missing)
            expand_dep_dict(self._vis_deps, symbol_names_missing)
            expand_def_dep_dict(self._def_deps, symbol_names_missing)

            return symbol_names_missing
        # ---

        sym_constants = self.get_default_symbol_constants()

        # expand once, collect missing names
        self.logger.debug("Expanding dependency expressions")
        symbol_names_missing = expand_once(self._symbols, sym_constants)

        if symbol_names_missing:
            self.logger.info(
                "missing %d symbols, defaulting them.",
                len(symbol_names_missing)
            )

            if self.logger.isEnabledFor(logging.DEBUG):
                for name in sorted(symbol_names_missing):
                    value = self.constify_missing_symbol(name)
                    self.logger.debug(
                        "Defaulting symbol %s to %s", name, value
                    )
                    sym_constants[name] = value
                # --
            else:
                sym_constants.update((
                    (name, self.constify_missing_symbol(name))
                    for name in symbol_names_missing
                ))
            # -- end debug | nodebug

            self.logger.debug("Expanding dependency expressions again")
            symbol_names_missing = expand_once(self._symbols, sym_constants)
            if symbol_names_missing:
                raise AssertionError(
                    "second expr expansion should not report missing symbols",
                    symbol_names_missing
                )
            # --
        # -- end if default missing and retry

        # simplify and assign dir_dep to symbols
        for sym, dep_expr in self._dir_deps.items():
            sym.dir_dep = None if dep_expr is None else dep_expr.simplify()

        for sym, vis_expr in self._vis_deps.items():
            sym.vis_dep = None if vis_expr is None else vis_expr.simplify()

        for sym, def_exprv in self._def_deps.items():
            sym.defaults = None  # nop
            if def_exprv:
                simplified_def_exprv = [
                    [
                        (None if dep_expr is None else dep_expr.simplify())
                        for dep_expr in dep_tuple
                    ] for dep_tuple in def_exprv
                ]

                # construct KconfigSymbolDefault objects
                #  FIXME: does it make sense to construct a default
                #         if dir_dep is None?
                #  FIXME: filter out constant "n"
                defaultv = [
                    symbol.KconfigSymbolDefault(
                        dir_dep=dir_dep, vis_dep=vis_dep
                    )
                    for dir_dep, vis_dep in simplified_def_exprv
                    if (dir_dep is not None or vis_dep is not None)
                ]

                if defaultv:
                    sym.defaults = defaultv
                # -- end if set defaults?
            # -- otherwise keep None
        # --
    # --- end of _link_deps (...) ---

    def get_symbols(self):
        """
        Imports Kconfig symbols, collects and expand dependencies,
        and returns the result as KconfigSymbols object.

        @return: kconfig symbols
        @rtype:  L{KconfigSymbols}
        """
        symbolexpr.clear_cache()
        try:
            self._prepare_symbols()
            self._link_deps()
        finally:
            symbolexpr.clear_cache()
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
