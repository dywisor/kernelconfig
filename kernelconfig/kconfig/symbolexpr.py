# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import operator

from . import symbol


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

    @abc.abstractmethod
    def evaluate(self, symbol_value_map):
        """
        Given a symbol => value map,
        calculates the boolean value of this expression.

        Note: the expression should be simplified before calling this method.

        @param symbol_value_map:  (incomplete) symbol to value mapping
        @type  symbol_value_map:  C{dict} :: L{AbstractKconfigSymbol} => _
        @return: tristate value
        @rtype:  L{TristateKconfigSymbolValue}
        """
        raise NotImplementedError()
    # --- end of evaluate (...) ---

    @abc.abstractmethod
    def simplify(self):
        """Simplifies the expression.

        Note: this performs basic simplifications only,
        such as evaluating constant expressions.

        @return:  unmodified self, or new, modified Expr
        @rtype:   subclass of L{Expr}
        """
        raise NotImplementedError()
    # --- end of simplify (...) ---

# --- end of Expr ---


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

    def __init__(self, expr):
        super().__init__()
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

    def __init__(self, *args):
        super().__init__()
        self.exprv = []
        self.extend_expr(args)

    def add_expr(self, expr):
        self.exprv.append(expr)
        return expr

    def extend_expr(self, exprv):
        for expr in exprv:
            self.add_expr(expr)

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

    def iter_evaluate_subexpr(self, symbol_value_map):
        if not self.exprv:
            raise AssertionError("empty expr")

        for subexpr in self.exprv:
            yield subexpr.evaluate(symbol_value_map)
    # --- end of iter_evaluate_subexpr (...) ---

    def simplify_and_split_subexpr(self):
        """Splits self.exprv into constants, symbols and nested expressions.

        The result can then be simplified,
        and then converted back into a Expr with join_simplified_subexpr().

        @return: 3-tuple (
                   set of constant values,
                   set of symbol expr,
                   list of recursive expr
                 )
        @rtype:  3-tuple (
                   C{set} of C{TristateKconfigSymbolValue},
                   C{set} of L{Expr_Symbol},
                   C{set} of subclass of L{Expr}
                 )
        """
        constant_values = set()
        symbol_exprs = set()
        nested_exprs = []

        # assert commutative, associative, idempotent
        for expr in self.exprv:
            simpler_expr = expr.simplify()

            if isinstance(simpler_expr, Expr_Constant):
                constant_values.add(simpler_expr.evaluate(None))
            elif isinstance(simpler_expr, Expr_Symbol):
                symbol_exprs.add(simpler_expr)
            else:
                nested_exprs.append(simpler_expr)
        # -- end for

        return (constant_values, symbol_exprs, nested_exprs)
    # --- end of simplify_and_split_subexpr (...) ---

    def join_simplified_subexpr(
        self, constant_values, symbol_exprs, nested_exprs
    ):
        """Constructs a new expression
        from the given constants, symbols and nested expressions.

        "Inverse" of simplify_and_split_subexpr(),
        but does not accept all-empty input and creates a new Expr object.

        @param constant_values:  constant values
        @type  constant_values:  C{set} of C{TristateKconfigSymbolValue}
        @param symbol_exprs:     symbol expressions
        @type  symbol_exprs:     C{set} of L{Expr_Symbol}
        @param nested_exprs:     nested expressions
        @type  nested_exprs:     C{list} of subclass L{Expr}

        @return:  new expression
        @rtype:   this class
        """
        expr = self.__class__()
        expr.extend_expr(
            (Expr_Constant.get_instance(v) for v in constant_values)
        )
        expr.extend_expr(symbol_exprs)
        expr.extend_expr(nested_exprs)

        if not expr.exprv:
            raise AssertionError("created empty expression")

        return expr
    # --- end of join_simplified_subexpr (...) ---

# --- end of _MultiExpr


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

    def simplify(self):
        return self

    @abc.abstractmethod
    def get_value(self, symbol_value_map):
        raise NotImplementedError()

    def evaluate(self, symbol_value_map):
        value = self.get_value(symbol_value_map)
        if isinstance(value, symbol.TristateKconfigSymbolValue):
            return value
        elif value:
            return symbol.TristateKconfigSymbolValue.y
        else:
            return symbol.TristateKconfigSymbolValue.n
    # --- end of evaluate (...) ---

    def __repr__(self):
        return "{c.__qualname__}<{s.expr}>".format(s=self, c=self.__class__)

# --- end of _UnaryValueExpr ---


class Expr_Constant(_UnaryValueExpr):
    """Expression that represents a constant value.

    @ivar expr:  constant value
    @type expr:  undef
    """
    __slots__ = []
    _instances = {}

    def get_value(self, symbol_value_map):
        return self.expr
    # --- end of evaluate (...) ---

# --- end of Expr_Constant ---


class Expr_Symbol(_UnaryValueExpr):
    """Expression that references a Kconfig symbol.

    @ivar expr: Kconfig symbol
    @type expr: L{AbstractKconfigSymbol}
    """
    __slots__ = []
    _instances = {}

    def get_value(self, symbol_value_map):
        try:
            return symbol_value_map[self.expr]
        except KeyError:
            return symbol.TristateKconfigSymbolValue.n
    # --- end of evaluate (...) ---

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

    def get_value(self, symbol_value_map):
        raise TypeError()
    # --- end of get_value (...) ---

    def evaluate(self, symbol_value_map):
        raise TypeError()
    # --- end of evaluate (...) ---

    def simplify(self):
        return self
    # --- end of simplify (...) ---
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
    def OP_EVAL(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    @abc.abstractproperty
    def EXPR_FMT(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    def __init__(self, lsym, rsym):
        super().__init__()
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

    def evaluate(self, symbol_value_map):
        loper = self.lsym.get_value(symbol_value_map)
        roper = self.rsym.get_value(symbol_value_map)
        return self.OP_EVAL(loper, roper)
    # --- end of evaluate (...) ---

    def simplify(self):
        if (
            isinstance(self.lsym, Expr_Constant)
            and isinstance(self.rsym, Expr_Constant)
        ):
            return Expr_Constant(self.evaluate(None))
        else:
            return self
    # --- end of simplify (...) ---

# ---


class Expr_SymbolEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}={1!s}"
    OP_EVAL = operator.__eq__
# ---


class Expr_SymbolNEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}!={1!s}"
    OP_EVAL = operator.__ne__
# ---


class Expr_SymbolLTH(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}<{1!s}"
    OP_EVAL = operator.__lt__
# ---


class Expr_SymbolLEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}<={1!s}"
    OP_EVAL = operator.__le__
# ---


class Expr_SymbolGTH(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}!>{1!s}"
    OP_EVAL = operator.__gt__
# ---


class Expr_SymbolGEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}!>={1!s}"
    OP_EVAL = operator.__ge__
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

    def evaluate(self, symbol_value_map):
        return self.expr.evaluate(symbol_value_map).__invert__()
    # --- end of evaluate (...) ---

    def simplify(self):
        simpler_expr = self.expr.simplify()

        if isinstance(simpler_expr, Expr_Constant):
            return Expr_Constant.get_instance(
                simpler_expr.evaluate(None).__invert__()
            )

        elif isinstance(self.expr, Expr_Not):
            # not not expr => expr
            return self.expr.expr.simplify()

        elif simpler_expr is self.expr:
            return self  # unmodified

        else:
            return Expr_Not(simpler_expr)
    # --- end of simplify (...) ---
# ---


class Expr_And(_SelfConsumingMultiExpr):
    __slots__ = []

    OP_STR = " && "

    def evaluate(self, symbol_value_map):
        # this is not identical to all(...),
        #  which would return a bool, whereas "y and m" == "m"
        ret_value = symbol.TristateKconfigSymbolValue.y
        for value in self.iter_evaluate_subexpr(symbol_value_map):
            ret_value = min(ret_value, value)
            if not ret_value:
                break

        return ret_value
    # --- end of evaluate (...) ---

    def simplify(self):
        constant_values, symbol_exprs, nested_exprs = \
            self.simplify_and_split_subexpr()

        if symbol.TristateKconfigSymbolValue.n in constant_values:
            # constant "n" in AND
            return Expr_Constant.get_instance(
                symbol.TristateKconfigSymbolValue.n
            )

        elif not symbol_exprs and not nested_exprs:
            if constant_values:
                # any other constant in AND (and no symbols/exprs)
                return Expr_Constant.get_instance(min(constant_values))
            else:
                # empty AND
                return Expr_Constant.get_instance(
                    symbol.TristateKconfigSymbolValue.n
                )

        else:
            # AND depends on a dynamic value

            # "y" && _ <=> _
            constant_values.discard(symbol.TristateKconfigSymbolValue.y)
            # constant_values is now either empty or contains just m

            return self.join_simplified_subexpr(
                constant_values, symbol_exprs, nested_exprs
            )
    # --- end of simplify (...) ---

# ---


class Expr_Or(_SelfConsumingMultiExpr):
    __slots__ = []

    OP_STR = " || "

    def evaluate(self, symbol_value_map):
        ret_value = symbol.TristateKconfigSymbolValue.n
        for value in self.iter_evaluate_subexpr(symbol_value_map):
            ret_value = max(ret_value, value)
            if ret_value == symbol.TristateKconfigSymbolValue.y:
                # "m" is not enough
                break

        return ret_value
    # --- end of evaluate (...) ---

    def simplify(self):
        constant_values, symbol_exprs, nested_exprs = \
            self.simplify_and_split_subexpr()

        if symbol.TristateKconfigSymbolValue.y in constant_values:
            # constant "y" in OR
            return Expr_Constant.get_instance(
                symbol.TristateKconfigSymbolValue.y
            )

        elif not symbol_exprs and not nested_exprs:
            if constant_values:
                # any other constant in OR (and no symbols/exprs)
                return Expr_Constant.get_instance(max(constant_values))
            else:
                # empty OR
                return Expr_Constant.get_instance(
                    symbol.TristateKconfigSymbolValue.y
                )

        else:
            # OR depends on a dynamic value

            # "n" || _ <=> _
            constant_values.discard(symbol.TristateKconfigSymbolValue.n)
            # constant_values is now either empty or contains just m

            return self.join_simplified_subexpr(
                constant_values, symbol_exprs, nested_exprs
            )
    # --- end of simplify (...) ---
# ---
