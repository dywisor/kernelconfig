# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc


__all__ = [
    "Expr",
    "Expr_And",
    "Expr_Not",
    "Expr_Or",
    "Expr_Symbol",
    "Expr_SymbolEQ",
    "Expr_SymbolNEQ"
]


class Expr(object, metaclass=abc.ABCMeta):
    """Base class for dependency expressions."""
    # use __slots__, there will be many Expr objects floating around
    __slots__ = []

    # not hashable
    __hash__ = None

    @abc.abstractmethod
    def add_expr(self, expr):
        """Adds a subordinate expression to this expression.
        Depending on its type,
        it may be consumed (so that subordinate expr of expr are part of self),
        or absorbed (i.e. ignored).

        @raises TypeError: if this expression does not support subexpressions

        @param expr: expression
        @type  expr: subclass of L{Expr}
        @return: the expression object to which expr's subexpression have been
                 added, which may be expr (added as-is), self (consumed)
                 or None (absorbed)
        @rtype: subclass of L{Expr} or C{None}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def __str__(self):
        """Returns a str representation of this expression,
        including all subordinate expressions.

        @returns: expression as str
        @rtype:   C{str}
        """
        raise NotImplementedError()

    def expand_symbols(self, symbol_name_map):
        """Recursively replaces symbol name references with symbols from
        the given mapping.

        @param symbol_name_map:  symbol name to <object> map
        @type  symbol_name_map:  C{dict} :: C{str} => _
        @return: set of missing symbol names
        @rtype:  C{set} of C{str}
        """
        symbol_names_missing = set()
        self.expand_symbols_shared(symbol_name_map, symbol_names_missing)
        return symbol_names_missing
    # ---

    @abc.abstractmethod
    def expand_symbols_shared(self, symbol_name_map, symbols_names_missing):
        """Recursively replaces symbol name references with symbols from
        the given mapping, using a shared set for storing missing names.

        @param symbol_name_map:        symbol name to <object> map
        @type  symbol_name_map:        C{dict} :: C{str} => _
        @param symbols_names_missing:  shared set of missing symbol names
        @type  symbols_names_missing:  C{set} of C{str}
        @return: None
        """
        raise NotImplementedError()
    # ---

# ---


class _UnaryExpr(Expr):
    """
    Base class for expressions that store exactly one subexpression.

    @cvar EXPR_FMT: string that is used for formatting the subexpression,
                    should reference the expression via '{0}' (or '{}', equiv.)
    @type EXPR_FMT: C{str}

    @ivar expr: subexpression
    @type expr: undefined, must support C{__str__}
    """
    __slots__ = ["expr"]

    @abc.abstractproperty
    def EXPR_FMT(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    def __init__(self, expr, **kwargs):
        super().__init__(**kwargs)
        self.expr = expr

    def add_expr(self, expr):
        raise TypeError()

    def __str__(self):
        return self.EXPR_FMT.format(self.expr)
# ---


class _MultiExpr(Expr):
    """
    Base class for dependency expressions
    with a variable count of subexpressions, e.g. AND.

    @cvar OP_STR:  str that is used for combining subexpression strings
    @type OP_STR:  C{str}

    @ivar exprv:   list of subexpressions
    @type exprv:   subclass of L{Expr}
    """
    __slots__ = ["exprv"]

    @abc.abstractproperty
    def OP_STR(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.exprv = []

    def add_expr(self, expr):
        # if expr is None:   # that's nothing that should be decided here
        #    return None
        self.exprv.append(expr)
        return expr

    def __str__(self):
        # redundant parentheses are OK
        return self.OP_STR.join(("({!s})".format(e) for e in self.exprv))

    def expand_symbols_shared(self, symbol_name_map, symbol_names_missing):
        for subexpr in self.exprv:
            if subexpr is not None:
                subexpr.expand_symbols_shared(
                    symbol_name_map, symbol_names_missing
                )
            # --
        # --
    # --- end of expand_symbols_shared (...) ---
# ---


class _SelfConsumingMultiExpr(_MultiExpr):
    """
    Base class for dependency expressions
    with a variable count of subexpressions,
    that also consume subordinate expressions of the same type.
    """
    __slots__ = []

    def add_expr(self, expr):
        if type(expr) is type(self):
            self.exprv.extend(expr.exprv)
            return self
        else:
            return super().add_expr(expr)
    # ---
# ---


class Expr_Symbol(_UnaryExpr):
    """Expression that represents a Kconfig symbol.

    @ivar expr: Kconfig symbol
    @type expr: C{str} or symbol object
    """
    __slots__ = []
    EXPR_FMT = "{0!s}"

    def expand_symbols_shared(self, symbol_name_map, symbol_names_missing):
        if isinstance(self.expr, str):
            try:
                repl = symbol_name_map[self.expr]
            except KeyError:
                symbol_names_missing.add(self.expr)
            else:
                self.expr = repl
    # --- end of expand_symbols_shared (...) ---
# ---


class _Expr_SymbolValueComparison(Expr_Symbol):
    """Expression that represents a comparison of a Kconfig symbol
    with a value or another symbol.

    @ivar cmp_expr: Kconfig symbol or value
    @type cmp_expr: C{str} (for now) or undefined
    """
    __slots__ = ["cmp_expr"]

    # EXPR_FMT needs to be abstract again
    @abc.abstractproperty
    def EXPR_FMT(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    def __init__(self, lsym, rsym, **kwargs):
        super().__init__(lsym, **kwargs)
        self.cmp_expr = rsym
    # ---

    def __str__(self):
        return self.EXPR_FMT.format(self.expr, self.cmp_expr)

    def expand_symbols_shared(self, symbol_name_map, symbols_names_missing):
        for expr in (self.expr, self.cmp_expr):
            if expr is not None:
                expr.expand_symbols_shared(
                    symbol_name_map, symbols_names_missing
                )
        # --
    # --- end of expand_symbols_shared (...) ---
# ---


class Expr_SymbolEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}={1!s}"
# ---


class Expr_SymbolNEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}!={1!s}"
# ---


class Expr_SymbolLTH(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}<{1!s}"
# ---


class Expr_SymbolLEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}<={1!s}"
# ---


class Expr_SymbolGTH(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}!>{1!s}"
# ---


class Expr_SymbolGEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}!>={1!s}"
# ---


class Expr_Not(_UnaryExpr):
    __slots__ = []

    EXPR_FMT = "!({0!s})"

    def expand_symbols_shared(self, symbol_name_map, symbol_names_missing):
        if self.expr is not None:
            self.expr.expand_symbols_shared(
                symbol_name_map, symbol_names_missing
            )
    # --- end of expand_symbols_shared (...) ---
# ---


class Expr_And(_SelfConsumingMultiExpr):
    __slots__ = []

    OP_STR = " && "
# ---


class Expr_Or(_SelfConsumingMultiExpr):
    __slots__ = []

    OP_STR = " || "
# ---
