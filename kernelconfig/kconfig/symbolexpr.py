# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc


__all__ = [
    "clear_cache",
    "Expr",
    "Expr_And",
    "Expr_Not",
    "Expr_Or",
    "Expr_Constant",
    "Expr_Symbol",
    "Expr_SymbolName",
    "Expr_SymbolEQ",
    "Expr_SymbolNEQ"
]


def clear_cache():
    """
    Clears the instance caches of various classes provided by this module.
    """
    Expr_Constant.clear_instance_cache()
    Expr_Symbol.clear_instance_cache()
# --- end of clear_cache (...) ---


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

    def expand_symbols(self, symbol_name_map, constants):
        """Recursively replaces symbol name references with symbols from
        the given mappings.
        The symbol name is first looked up in constants
        (resulting in a Expr_Constant object),
        and then in symbol_name_map (Expr_Symbol).

        @param symbol_name_map:  symbol name to <object> map
        @type  symbol_name_map:  C{dict} :: C{str} => _
        @param constants:        symbol name to constant,hashable value map
        @type  constants:        C{dict} :: C{str} => a, a.__hash__ != None
        @return: 2-tuple
                 (modified Expr structure or self, set of missing symbol names)
        @rtype:  2-tuple (L{Expr}, C{set} of C{str})
        """
        symbol_names_missing = set()
        expr = self.expand_symbols_shared(
            symbol_name_map, constants, symbol_names_missing
        )
        return (expr, symbol_names_missing)
    # ---

    @abc.abstractmethod
    def expand_symbols_shared(
        self, symbol_name_map, constants, symbols_names_missing
    ):
        """Recursively replaces symbol name references with symbols from
        the given mapping, using a shared set for storing missing names.

        @param symbol_name_map:        symbol name to <object> map
        @type  symbol_name_map:        C{dict} :: C{str} => _
        @param constants:              symbol name to hashable value map
        @type  constants:              C{dict} :: C{str} => a
        @param symbols_names_missing:  shared set of missing symbol names
        @type  symbols_names_missing:  C{set} of C{str}

        @return: modified Expr structure or self
        """
        raise NotImplementedError()
    # ---

    def expand_subexpr_symbols_shared(
        self, subexpr, symbol_name_map, constants, symbol_names_missing
    ):
        """Recursively expands a single subexpression by calling
        its expand_symbols_shared() method.

        @param subexpr:                subexpression, must not be self
        @type  subexpr:                subclass of L{Expr} or C{None}
        @param symbol_name_map:        symbol name to <object> map
        @type  symbol_name_map:        C{dict} :: C{str} => _
        @param constants:              symbol name to hashable value map
        @type  constants:              C{dict} :: C{str} => a
        @param symbols_names_missing:  shared set of missing symbol names
        @type  symbols_names_missing:  C{set} of C{str}

        @return: modified Expr structure
        """
        if subexpr is None:
            return None
        else:
            return subexpr.expand_symbols_shared(
                symbol_name_map, constants, symbol_names_missing
            )
        # --
    # --- end of expand_subexpr_symbols_shared (...) ---
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

    def expand_symbols_shared(
        self, symbol_name_map, constants, symbols_names_missing
    ):
        self.exprv = [
            self.expand_subexpr_symbols_shared(
                subexpr, symbol_name_map, constants, symbols_names_missing
            ) for subexpr in self.exprv
        ]
        return self
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


class _UnaryValueExpr(_UnaryExpr):
    """Expression that represents a value, either from a symbol or a constant.

    @cvar _instances:  a value => object cache,
                        derived classes must set this to a dict
    @type _instances:  C{dict} :: a => subclass of L{_UnaryValueExpr},
                         a.__hash__ != None

    @ivar expr:  Kconfig symbol or constant value
    @type expr:  L{AbstractKconfigSymbol} or undef a, a.__hash__ != None
    """
    __slots__ = []
    EXPR_FMT = "{0!s}"

    _instances = None

    @classmethod
    def clear_instance_cache(cls):
        cls._instances.clear()
    # --- end of clear_instance_cache (...) ---

    @classmethod
    def get_instance(cls, value):
        try:
            obj = cls._instances[value]
        except KeyError:
            obj = cls(value)
            cls._instances[value] = obj

        return obj
    # --- end of get_instance (...) ---

    def __hash__(self):
        return hash((self.__class__, self.expr))

    def expand_symbols_shared(
        self, symbol_name_map, constants, symbols_names_missing
    ):
        return self

# --- end of _UnaryValueExpr ---


class Expr_Constant(_UnaryValueExpr):
    """Expression that represents a constant value.

    @ivar expr:  constant value
    @type expr:  undef
    """
    __slots__ = []
    _instances = {}
# --- end of Expr_Constant ---


class Expr_Symbol(_UnaryValueExpr):
    """Expression that references a Kconfig symbol.

    @ivar expr: Kconfig symbol
    @type expr: L{AbstractKconfigSymbol}
    """
    __slots__ = []
    _instances = {}
# --- end of Expr_Symbol ---


class Expr_SymbolName(_UnaryExpr):
    """Expression that references a Kconfig symbol by name.

    @ivar expr: Kconfig symbol name
    @type expr: C{str}
    """
    __slots__ = []
    EXPR_FMT = "{0!s}"

    def expand_symbols_shared(
        self, symbol_name_map, constants, symbol_names_missing
    ):
        key = self.expr

        try:
            repl = constants[key]
        except KeyError:
            pass
        else:
            return Expr_Constant.get_instance(repl)

        if key is None:
            return self

        try:
            repl = symbol_name_map[key]
        except KeyError:
            symbol_names_missing.add(key)
            return self
        else:
            return Expr_Symbol.get_instance(repl)
    # --- end of expand_symbols_shared (...) ---
# ---


class _Expr_SymbolValueComparison(Expr):
    """Expression that represents a comparison of a Kconfig symbol
    with a value or another symbol.

    @ivar lsym:  symbol or value (left operand)
    @type lsym:  L{Expr_SymbolName}|L{Expr_Symbol}|L{Expr_Constant}|C{None}
    @ivar rsym:  symbol or value (right operand)
    @type rsym:  L{Expr_SymbolName}|L{Expr_Symbol}|L{Expr_Constant}|C{None}
    """
    __slots__ = ["lsym", "rsym"]

    @abc.abstractproperty
    def EXPR_FMT(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    def __init__(self, lsym, rsym, **kwargs):
        super().__init__(**kwargs)
        self.lsym = lsym
        self.rsym = rsym
    # ---

    def add_expr(self, expr):
        raise TypeError()

    def __str__(self):
        return self.EXPR_FMT.format(self.lsym, self.rsym)

    def expand_symbols_shared(
        self, symbol_name_map, constants, symbols_names_missing
    ):
        self.lsym = self.expand_subexpr_symbols_shared(
            self.lsym, symbol_name_map, constants, symbols_names_missing
        )
        self.rsym = self.expand_subexpr_symbols_shared(
            self.rsym, symbol_name_map, constants, symbols_names_missing
        )
        return self
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

    def expand_symbols_shared(
        self, symbol_name_map, constants, symbols_names_missing
    ):
        self.expr = self.expand_subexpr_symbols_shared(
            self.expr, symbol_name_map, constants, symbols_names_missing
        )
        return self
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
