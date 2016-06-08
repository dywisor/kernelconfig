# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections.abc
import operator
import itertools

from ..abc import loggable
from . import symbol


__all__ = [
    "clear_cache",
    "merge_solutions",
    "Expr",
    "Expr_And",
    "Expr_Not",
    "Expr_Or",
    "Expr_Constant",
    "Expr_Symbol",
    "Expr_SymbolName",
    "Expr_SymbolEQ",
    "Expr_SymbolNEQ",
    "Expr_Impl",
]


def clear_cache():
    """
    Clears the instance caches of various classes provided by this module.
    """
    Expr_Constant.clear_instance_cache()
    Expr_Symbol.clear_instance_cache()
# --- end of clear_cache (...) ---


class Visitable(collections.abc.Hashable):
    __slots__ = []

    @abc.abstractmethod
    def visit(self, visitor):
        raise NotImplementedError()

    @abc.abstractmethod
    def __eq__(self, other):
        raise NotImplementedError()

    @abc.abstractmethod
    def calculate_static_hash(self):
        raise NotImplementedError()

# --- end of Visitable (...) ---


class SolutionCache(object):
    __slots__ = ["solutions"]

    def __init__(self):
        super().__init__()
        self.solutions = [{}]

    def _replace_solutions(self, new_solutions):
        self.solutions = new_solutions
        return bool(new_solutions)

    def push_symbol(self, sym, values):
        solutions_new = []
        for sol in self.solutions:
            try:
                entry = sol[sym] & values
            except KeyError:
                entry = values

            if entry:
                sol[sym] = entry
                solutions_new.append(sol)
        # --

        return self._replace_solutions(solutions_new)

    def get_solutions(self):
        return self.solutions

    @classmethod
    def merge_solution_dict_x_dict(cls, dina, dinb):
        dout = {}
        for sym, values in dina.items():
            if sym in dinb:
                entry = values & dinb[sym]
            else:
                entry = values  # ref

            if entry:
                dout[sym] = entry
            else:
                return None
        # --

        for sym in dinb:
            if sym not in dout:
                dout[sym] = dinb[sym]  # ref
        # --

        return dout
    # ---

    @classmethod
    def merge_solutions_list_x_list(cls, la, lb):
        solutions = []
        for sol_a, sol_b in itertools.product(la, lb):
            sol_res = cls.merge_solution_dict_x_dict(sol_a, sol_b)
            if sol_res is not None:
                solutions.append(sol_res)

        return solutions
    # ---

    def merge_alternatives(self, alternatives):
        merged_sol = []
        #
        # for alternative in alternatives:
        #    for alt-solutions in alternative:
        #       self.solutions X alt-solutions
        #
        for sol_cache in alternatives:
            subsol_merged = self.merge_solutions_list_x_list(
                self.solutions, sol_cache.solutions
            )
            merged_sol.extend(subsol_merged)
        # --

        return self._replace_solutions(merged_sol)

# --- end of SolutionCache ---


merge_solutions = SolutionCache.merge_solutions_list_x_list


class Expr(Visitable):
    """Base class for dependency expressions."""
    # use __slots__, there will be many Expr objects floating around
    __slots__ = []

    EXPR_VALUES_N = frozenset([symbol.TristateKconfigSymbolValue.n])
    EXPR_VALUES_M = frozenset([symbol.TristateKconfigSymbolValue.m])
    EXPR_VALUES_Y = frozenset([symbol.TristateKconfigSymbolValue.y])
    EXPR_VALUES_YM = EXPR_VALUES_Y | EXPR_VALUES_M
    EXPR_VALUES_YMN = EXPR_VALUES_Y | EXPR_VALUES_M | EXPR_VALUES_N

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

    @abc.abstractmethod
    def gen_func_str(self, indent=None):
        raise NotImplementedError()

    def func_str(self, indent=None):
        return "\n".join((
            (("%s%s" % (ind or "", text)) if text else "")
            for ind, text in self.gen_func_str(indent=indent)
        ))
    # --- end of func_str (...) ---

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

    @abc.abstractmethod
    def move_negation_inwards(self):
        raise NotImplementedError()

    def find_solution(self, expr_values):
        sol_cache = SolutionCache()
        ret = self._find_solution(expr_values, sol_cache)
        return (ret, sol_cache.get_solutions())
    # ---

    @abc.abstractmethod
    def _find_solution(self, expr_values, sol_cache):
        raise NotImplementedError()

    def get_dependent_symbols(self):
        symbol_set = set()
        self.get_dependent_symbols_shared(symbol_set)
        return symbol_set

    @abc.abstractmethod
    def get_dependent_symbols_shared(self, symbol_set):
        raise NotImplementedError()

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

    def __hash__(self):
        return hash((self.__class__, self.expr))

    def __eq__(self, other):
        if type(self) is type(other):
            return self.expr == other.expr
        else:
            return False
    # ---

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
    __slots__ = ["exprv", "static_hash"]

    @abc.abstractproperty
    def OP_STR(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    def __hash__(self):
        static_hash = self.static_hash
        if static_hash is None:
            raise TypeError("%r relies on pre-hashing" % self.__class__)
        return static_hash

    def __eq__(self, other):
        if type(self) is type(other):
            return set(self.exprv) == set(other.exprv)
        else:
            return False

    def __init__(self, *args):
        super().__init__()
        self.static_hash = None
        self.exprv = []
        self.extend_expr(args)

    def add_expr(self, expr):
        self.exprv.append(expr)
        return expr

    def extend_expr(self, exprv):
        for expr in exprv:
            self.add_expr(expr)

    def calculate_static_hash(self):
        self.static_hash = None

        sources = [self.__class__]
        for expr in self.exprv:
            expr.calculate_static_hash()
            sources.append(expr)
        # --

        self.static_hash = hash(tuple(sources))
    # --- end of calculate_static_hash (...) ---

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

    def get_dependent_symbols_shared(self, symbol_set):
        for expr in self.exprv:
            expr.get_dependent_symbols_shared(symbol_set)

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
        elif len(expr.exprv) == 1:
            return expr.exprv[0]
        else:
            return expr
    # --- end of join_simplified_subexpr (...) ---

    def move_negation_inwards(self):
        self.exprv = [e.move_negation_inwards() for e in self.exprv]
        return self
    # --- end of move_negation_inwards (...) ---

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

    def calculate_static_hash(self):
        pass
    # --- end of calculate_static_hash (...) ---

    def visit(self, visitor):
        return visitor.visit_symbol(self)

    def expand_symbols_shared(
        self, symbol_name_map, constants, symbols_names_missing
    ):
        return self

    def simplify(self):
        return self

    def move_negation_inwards(self):
        # must return self
        return self
    # --- end of move_negation_inwards (...) ---

    @abc.abstractmethod
    def get_value(self, symbol_value_map):
        raise NotImplementedError()

    def _evaluate_value(self, value):
        if isinstance(value, symbol.TristateKconfigSymbolValue):
            return value
        elif value:
            return symbol.TristateKconfigSymbolValue.y
        else:
            # FIXME: not correct -- empty string, integer 0
            return symbol.TristateKconfigSymbolValue.n

    def evaluate(self, symbol_value_map):
        return self._evaluate_value(
            self.get_value(symbol_value_map)
        )
    # --- end of evaluate (...) ---

    def __repr__(self):
        return "{c.__qualname__}<{s.expr}>".format(s=self, c=self.__class__)

    def gen_func_str(self, indent=None):
        yield (indent, self.EXPR_FMT.format(self.expr))

# --- end of _UnaryValueExpr ---


class Expr_Constant(_UnaryValueExpr):
    """Expression that represents a constant value.

    @ivar expr:  constant value
    @type expr:  undef
    """
    __slots__ = []
    _instances = {}

    def get_dependent_symbols_shared(self, symbol_set):
        pass

    def get_value(self, symbol_value_map):
        return self.expr
    # --- end of evaluate (...) ---

    def _find_solution(self, expr_values, sol_cache):
        return self.evaluate(None) in expr_values

# --- end of Expr_Constant ---


class Expr_Symbol(_UnaryValueExpr):
    """Expression that references a Kconfig symbol.

    @ivar expr: Kconfig symbol
    @type expr: L{AbstractKconfigSymbol}
    """
    __slots__ = []
    _instances = {}

    def get_dependent_symbols_shared(self, symbol_set):
        symbol_set.add(self.expr)

    def get_value(self, symbol_value_map):
        try:
            return symbol_value_map[self.expr]
        except KeyError:
            return symbol.TristateKconfigSymbolValue.n
    # --- end of evaluate (...) ---

    def _find_solution(self, expr_values, sol_cache):
        return sol_cache.push_symbol(
            self.expr,
            self.expr.normalize_and_validate_set(expr_values)[1]
        )

# --- end of Expr_Symbol ---


class Expr_SymbolName(_UnaryExpr):
    """Expression that references a Kconfig symbol by name.

    @ivar expr: Kconfig symbol name
    @type expr: C{str}
    """
    __slots__ = []
    EXPR_FMT = "{0!s}"

    def visit(self, visitor):
        return visitor.visit_symbol(self)

    def calculate_static_hash(self):
        pass

    def get_dependent_symbols_shared(self, symbol_set):
        pass

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

    def move_negation_inwards(self):
        # must return self
        return self
    # --- end of move_negation_inwards (...) ---

    def gen_func_str(self, indent=None):
        yield (indent, self.EXPR_FMT.format(self.expr))

    def _find_solution(self, expr_values, sol_cache):
        raise TypeError()

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

    def calculate_static_hash(self):
        # both of these are no-ops
        self.lsym.calculate_static_hash()
        self.rsym.calculate_static_hash()

    def visit(self, visitor):
        return visitor.visit_symbol_cmp(self)

    def add_expr(self, expr):
        raise TypeError()

    def __hash__(self):
        return hash((self.__class__, self.lsym, self.rsym))

    def __eq__(self, other):
        if type(self) is type(other):
            return (self.lsym == other.lsym) and (self.rsym == other.rsym)
        else:
            return False

    def __str__(self):
        return self.EXPR_FMT.format(self.lsym, self.rsym)

    def gen_func_str(self, indent=None):
        yield (indent, self.EXPR_FMT.format(self.lsym, self.rsym))

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

    def get_dependent_symbols_shared(self, symbol_set):
        self.lsym.get_dependent_symbols_shared(symbol_set)
        self.rsym.get_dependent_symbols_shared(symbol_set)

    def evaluate(self, symbol_value_map):
        loper = self.lsym.get_value(symbol_value_map)
        roper = self.rsym.get_value(symbol_value_map)

        if self.OP_EVAL(loper, roper):
            return symbol.TristateKconfigSymbolValue.y
        else:
            return symbol.TristateKconfigSymbolValue.n
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

    def move_negation_inwards(self):
        # must return self
        return self
    # --- end of move_negation_inwards (...) ---

    def _solve_symbol_x_symbol(self, expr_value, sol_cache, lsym, rsym):
        raise NotImplementedError("symbol X symbol")

    def _solve_symbol_x_constant(self, expr_value, sol_cache, lsym, rsym):
        raise NotImplementedError("symbol X constant")

    def _solve_constant_x_symbol(self, expr_value, sol_cache, lsym, rsym):
        raise NotImplementedError("constant X symbol")

    def _solve_constant_x_constant(self, expr_value, sol_cache, lsym, rsym):
        return bool(self.evaluate(None)) == bool(expr_value)

    def _find_solution(self, expr_values, sol_cache):
        expr_value = bool(max(expr_values))
        lsym = self.lsym
        rsym = self.rsym

        if isinstance(self.lsym, Expr_Symbol):
            if isinstance(rsym, Expr_Symbol):
                return self._solve_symbol_x_symbol(
                    expr_value, sol_cache, lsym, rsym
                )

            elif isinstance(rsym, Expr_Constant):
                return self._solve_symbol_x_constant(
                    expr_value, sol_cache, lsym, rsym
                )

            else:
                raise TypeError("rsym", type(self.rsym))

        elif isinstance(self.lsym, Expr_Constant):
            if isinstance(self.rsym, Expr_Symbol):
                return self._solve_constant_x_symbol(
                    expr_value, sol_cache, lsym, rsym
                )

            elif isinstance(self.rsym, Expr_Constant):
                return self._solve_constant_x_constant(
                    expr_value, sol_cache, lsym, rsym
                )

            else:
                raise TypeError("rsym", type(self.rsym))

        else:
            raise TypeError("lsym", type(self.lsym))
    # ---

# ---


class Expr_SymbolEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}={1!s}"
    OP_EVAL = operator.__eq__

    # def __eq__  allow swapped lsym,rsym

    def _solve_symbol_x_constant(self, expr_value, sol_cache, lsym, rsym):
        if expr_value:
            return lsym._find_solution({rsym.expr, }, sol_cache)
        else:
            return lsym._find_solution(
                self.EXPR_VALUES_YMN - {rsym.expr, }, sol_cache
            )

    def _solve_constant_x_symbol(self, expr_value, sol_cache, lsym, rsym):
        return self._solve_symbol_x_constant(expr_value, sol_cache, rsym, lsym)

# ---


class Expr_SymbolNEQ(_Expr_SymbolValueComparison):
    __slots__ = []

    EXPR_FMT = "{0!s}!={1!s}"
    OP_EVAL = operator.__ne__

    # def __eq__  allow swapped lsym,rsym

    def _solve_symbol_x_constant(self, expr_value, sol_cache, lsym, rsym):
        if expr_value:
            return lsym._find_solution(
                self.EXPR_VALUES_YMN - {rsym.expr, }, sol_cache
            )
        else:
            return lsym._find_solution({rsym.expr, }, sol_cache)

    def _solve_constant_x_symbol(self, expr_value, sol_cache, lsym, rsym):
        return self._solve_symbol_x_constant(expr_value, sol_cache, rsym, lsym)
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

    def visit(self, visitor):
        return visitor.visit_not(self)

    def calculate_static_hash(self):
        self.expr.calculate_static_hash()

    def expand_symbols_shared(
        self, symbol_name_map, constants, symbols_names_missing
    ):
        self.expr = self.expand_subexpr_symbols_shared(
            self.expr, symbol_name_map, constants, symbols_names_missing
        )
        return self
    # --- end of expand_symbols_shared (...) ---

    def get_dependent_symbols_shared(self, symbol_set):
        self.expr.get_dependent_symbols_shared(symbol_set)

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

    def move_negation_inwards(self):
        subexpr = self.expr

        if isinstance(subexpr, Expr_Not):
            # double negation
            return subexpr.expr.move_negation_inwards()

        elif isinstance(subexpr, Expr_And):
            expr_repl = Expr_Or()
            expr_repl.extend_expr((Expr_Not(e) for e in subexpr.exprv))
            return expr_repl.move_negation_inwards()

        elif isinstance(subexpr, Expr_Or):
            expr_repl = Expr_And()
            expr_repl.extend_expr((Expr_Not(e) for e in subexpr.exprv))
            return expr_repl.move_negation_inwards()

        elif isinstance(
            subexpr,
            (_Expr_SymbolValueComparison, _UnaryValueExpr, Expr_SymbolName)
        ):
            subexpr_repl = subexpr.move_negation_inwards()
            self.expr = subexpr_repl
            return self

        else:
            raise AssertionError("expr")
    # --- end of move_negation_inwards (...) ---

    def gen_func_str(self, indent=None):
        yield (indent, "NOT(")
        yield from self.expr.gen_func_str(indent=("%s   " % (indent or "")))
        yield (indent, ")")

    def _find_solution(self, expr_values, sol_cache):
        # assert that expr_values contains either a single "n"
        # or any combination of "y", "m"
        #  FIXME: or use __invert__(), !m == m?
        if symbol.TristateKconfigSymbolValue.n in expr_values:
            return self.expr._find_solution(
                self.EXPR_VALUES_YM, sol_cache
            )
        else:
            return self.expr._find_solution(
                self.EXPR_VALUES_N, sol_cache
            )

# ---


class Expr_And(_SelfConsumingMultiExpr):
    __slots__ = []

    OP_STR = " && "

    def visit(self, visitor):
        return visitor.visit_and(self)

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

    def _find_solution(self, expr_values, sol_cache):
        for subexpr in self.exprv:
            if not subexpr._find_solution(expr_values, sol_cache):
                return False
        return True
    # ---

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

    def gen_func_str(self, indent=None):
        yield (indent, "AND(")
        for expr in self.exprv:
            yield from expr.gen_func_str(indent=("%s   " % (indent or "")))
        yield (indent, ")")

# --- end of Expr_And ---


class Expr_Or(_SelfConsumingMultiExpr):
    __slots__ = []

    OP_STR = " || "

    def visit(self, visitor):
        return visitor.visit_or(self)

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

    def gen_func_str(self, indent=None):
        yield (indent, "OR(")
        for expr in self.exprv:
            yield from expr.gen_func_str(indent=("%s   " % (indent or "")))
        yield (indent, ")")

    def _find_solution(self, expr_values, sol_cache):
        # for each subexpr
        #    collection solutions in a new sol_cache
        # with each existing solution, merge alternatives

        sub_solutions = []
        for subexpr in self.exprv:
            sub_sol = SolutionCache()
            if subexpr._find_solution(expr_values, sub_sol):
                sub_solutions.append(sub_sol)
            # --
        # --

        return sol_cache.merge_alternatives(sub_solutions)
    # ---

# --- end of Expr_Or ---


def Expr_Impl(expr_premise, expr_conclusion):
    return Expr_Or(Expr_Not(expr_premise), expr_conclusion)
# --- end of Expr_Impl ---


class Expr_CnfVar(_UnaryValueExpr):
    _instances = {}

    def get_value(self, symbol_value_map):
        return self.expr
# ---


class ExprVisitor(loggable.AbstractLoggable):

    @abc.abstractmethod
    def visit_not(self, expr):
        raise NotImplementedError()

    @abc.abstractmethod
    def visit_and(self, expr):
        raise NotImplementedError()

    @abc.abstractmethod
    def visit_or(self, expr):
        raise NotImplementedError()

    @abc.abstractmethod
    def visit_symbol(self, expr):
        raise NotImplementedError()

    @abc.abstractmethod
    def visit_symbol_cmp(self, expr):
        raise NotImplementedError()

    @abc.abstractmethod
    def recur_visit_expr(self, expr):
        """Recursively processes a single expression of any type."""
        raise NotImplementedError()

    def __call__(self, expr):
        expr.calculate_static_hash()
        return self.recur_visit_expr(expr)

# --- end of ExprVisitor ---


class CNFVisitor(ExprVisitor):
    """
    @ivar clauses:       set of disjunctive clauses
    @type clauses:       C{set} of (C{frozenset} of C{int})

    @ivar cnfvar_map:    a expr to cnfvar mapping
    @type cnfvar_map:    C{dict} :: L{Expr} => C{int}

    @ivar symbol_vars:   a cnfvar to symbol expr mapping
    @type symbol_vars:   C{dict} :: C{int} => L{Expr}

    @ivar expr_vars:     a cnfvar to expr mapping
    @type expr_vars:     C{dict} :: C{int} => L{Expr}

    Condition:  each cnfvar must appear in either expr_vars or symbol_vars,
                but not both: union(expr_vars'keys, symbol_vars'keys) is empty

    @ivar _var_counter:  cnfvar generator
    @type _var_counter:  genexpr
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.clauses = set()
        self.cnfvar_map = {}
        self.symbol_vars = {}
        self.expr_vars = {}
        self._var_counter = itertools.count(1)

    def iter_clauses(self):
        """Generates clauses as list of literals.

        @return: disjunctive clause (sorted)
        @rtype:  C{list} of C{int}
        """
        for clause in self.clauses:
            yield sorted(clause, key=abs)

    def get_clauses(self):
        """Returns a list of all clauses.

        @return: cnf (sorted)
        @rtype:  C{list} of (C{list} of C{int})
        """
        return sorted(self.iter_clauses())   # key=?

    def get_numvars(self):
        """
        @return: number of cnfvars
        @rtype:  C{int}
        """
        return len(self.cnfvar_map)

    if __debug__:
        def push_clause(self, clause):
            """
            Adds a clause to the cnf, __debug__ variant of push_clause().

            @raises AssertionError:  if any literal in clause appears
                                     in both its positive and negative form
            """
            clause_set = frozenset(clause)
            assert all((-x not in clause_set) for x in clause_set)
            self.clauses.add(clause_set)
    else:
        def push_clause(self, clause):
            """Adds a clause to the cnf.

            @param clause:  cnfvars
            @type  clause:  iterable/genexpr/... of C{int}

            @return:  None (implicit)
            """
            self.clauses.add(frozenset(clause))

    def push_clauses(self, clauses):
        """Adds zero or more clauses to the cnf.

        @param clause:  iterable of cnfvar iterables
        @type  clause:  iterable/genexpr/... of (iterable/... of C{int})

        @return:  None (implicit)
        """
        self.clauses.update(map(frozenset, clauses))

    def itranslate_assignment_to_expr(self, assignment):
        """Generator that translates a cnfvar assignment back to
        symbols/constants/symbol comparisons and filters out substitution
        variables.

        @raises: AssertionError if any cnfvar==0
                 (hidden when running w/ "python -O")

        @raises: KeyError if cnfvar is unknown

        @param assignment:  iterable of cnfvars
        @type  assignment:  iterable of C{int}

        @return: 2-tuple (expression truth value, expression)
        @rtype:  2-tuple (C{bool}, L{Expr})
        """
        _get_sym_expr = self.symbol_vars.__getitem__
        _get_expr = self.expr_vars.__getitem__

        for cnfvar in assignment:
            assert cnfvar

            key = abs(cnfvar)
            try:
                # cnfvar is symbol-like?
                expr = _get_sym_expr(key)
            except KeyError:
                # if cnfvar is not a symbol, then it gets filtered out,
                # but it must exist, i.e. be mapped to a expr
                try:
                    _get_expr(key)
                except KeyError:
                    raise KeyError(cnfvar) from None
            else:
                yield ((cnfvar > 0), expr)
        # --
    # --- end of itranslate_assignment_to_expr (...) ---

    def translate_assignment_to_expr(self, assignment):
        """Translates a cnfvar assignment back to symbols/constants/symbol
        comparisons and filters out substitution variables.

        @param assignment:  iterable of cnfvars
        @type  assignment:  iterable of C{int}

        @return: list of 2-tuples (expression truth value, expression)
        @rtype:  C{list} of 2-tuple(C{bool}, L{Expr})
        """
        return list(self.itranslate_assignment_to_expr(assignment))
    # --- end of translate_assignment_to_expr (...) ---

    def _translate_cnfvar(self, cnfvar):
        """Translates a cnfvar back to its expression.

        This method is different to translate_assignment([...]) in that it
        (a) makes no conclusions about the expressions truth value and
        (b) replaces substitution variables with Expr_CnfVar expressions.

        @param cnfvar:  cnfvar
        @type  cnfvar:  C{int}

        @return:  expression
        @rtype:   L{Expr}
        """
        if not cnfvar:
            raise ValueError(cnfvar)

        key = abs(cnfvar)

        # symbol?
        try:
            expr = self.symbol_vars[key]
        except KeyError:
            pass
        else:
            return Expr_Not(expr) if cnfvar < 0 else expr

        # any other expr?  substitution var
        expr = self.expr_vars[key]
        substvar = Expr_CnfVar.get_instance("Z_%d" % key)
        return Expr_Not(substvar) if cnfvar < 0 else substvar
    # --- end of _translate_cnfvar (...) ---

    def itranslate_clauses_to_expr(self, clauses=None):
        """Generator that converts cnfvar clauses to Expr_Or objects.

        @param clauses:  cnf;
                         May be None, in which case this object's clauses
                         are processed.
        @type  clauses:  C{None} or iterable of (iterable of C{int})

        @return:  expression OR(<literal>)
        @rtype:   L{Expr_Or}
        """
        if clauses is None:
            clauses = self.iter_clauses()

        for clause in clauses:
            expr = Expr_Or()
            expr.extend_expr(
                (self._translate_cnfvar(e) for e in clause)
            )
            yield expr
        # --
    # ---

    def translate_to_expr(self, clauses=None):
        """Converts cnfvar clauses to a Expr_And(<Expr_Or(<literal>)>) object.

        The result can be used for printing out the cnf-converted expression.
        It should not be fed a CNFVisitor again!

        @param clauses:  cnf;
                         May be None, in which case this object's clauses
                         are processed.
        @type  clauses:  C{None} or iterable of (iterable of C{int})

        @return:  expression AND(<OR(<literal>)>)
        @rtype:   L{Expr_And} a | a.exprv: C{list} of L{Expr_Or}
        """
        expr = Expr_And()
        expr.extend_expr(
            self.itranslate_clauses_to_expr(clauses=clauses)
        )
        return expr
    # --- end of translate_to_expr (...) ---

    def _get_new_var_for_expr(self, expr):
        """Creates a new cnfvar and maps it to expr.
        Does not map expr to the cnfvar, this must be done afterwards.

        @param expr:  expression
        @type  expr:  L{Expr}

        @return:  new cnfvar
        @rtype:   C{int}
        """
        cnfvar = next(self._var_counter)
        self.cnfvar_map[expr] = cnfvar
        return cnfvar

    def get_new_var_for_expr(self, expr):
        """Creates a new cnfvar for a non-symbol expression.
        Maps the expression to this cnfvar in self.expr_vars.

        @param expr:  expression
        @type  expr:  L{Expr}

        @return:  new cnfvar
        @rtype:   C{int}
        """
        cnfvar = self._get_new_var_for_expr(expr)
        self.expr_vars[cnfvar] = expr
        return cnfvar

    def get_new_var_for_symbol(self, symbol_expr):
        """Creates a new cnfvar for a symbol-like expression.
        Maps the expression to this cnfvar in self.symbol_vars.

        @param expr:  symbol expression
        @type  expr:  L{Expr}

        @return:  new cnfvar
        @rtype:   C{int}
        """
        cnfvar = self._get_new_var_for_expr(symbol_expr)
        self.symbol_vars[cnfvar] = symbol_expr
        return cnfvar

    def get_new_var_for_symbol_cmp(self, symbol_cmp_expr):
        """Creates a new cnfvar for a symbol comparison expression.
        Maps the expression to this cnfvar in self.symbol_vars.

        @param expr:  symbol comparison expression
        @type  expr:  L{Expr}

        @return:  new cnfvar
        @rtype:   C{int}
        """
        return self.get_new_var_for_symbol(symbol_cmp_expr)

    def recur_visit_expr(self, expr):
        cnfvar = self.cnfvar_map.get(expr, None)
        if cnfvar is None:
            cnfvar = expr.visit(self)
            assert cnfvar is not None
            assert expr in self.cnfvar_map
        # --

        return cnfvar
    # --- end of recur_visit_expr (...) ---

    def recur_visit_exprv(self, exprv):
        return [self.recur_visit_expr(e) for e in exprv]  # or set/frozenset
    # --- end of recur_visit_exprv (...) ---

# --- end of CNFVisitor ---


class TseitinVisitor(CNFVisitor):
    """
    Expr to CNF converter that uses the Tseitin (Tseytin) transformation.

    This method avoids exponential growth of the formula by substitute
    the output of expressions for an additional variable.
    The result is an equisatisfiable expression, where the additional
    variables should be discarded when unencoding satisfying assignments.
    """

    def visit_and(self, expr):
        # A = OR(F_0,...,F_n)
        #  -->
        #  AND(
        #     OR(-F_0, ..., -F_n, A)
        #     OR(F_0, -A)
        #     ...
        #     OR(F_N, -A)
        #  )
        subvars = self.recur_visit_exprv(expr.exprv)
        cnfvar = self.get_new_var_for_expr(expr)

        clause = set()
        clause.update((-v for v in subvars))
        clause.add(cnfvar)
        self.push_clause(clause)

        self.push_clauses(
            ({subvar, -cnfvar} for subvar in subvars)
        )

        return cnfvar
    # --- end of visit_and (...) ---

    def visit_or(self, expr):
        # A = OR(F_0,...,F_n)
        #  -->
        #  AND(
        #     OR(F_0, ..., F_n, -A)
        #     OR(-F_0, A)
        #     ...
        #     OR(-F_N, A)
        #  )
        subvars = self.recur_visit_exprv(expr.exprv)
        cnfvar = self.get_new_var_for_expr(expr)

        clause = set()
        clause.update(subvars)
        clause.add(-cnfvar)
        self.push_clause(clause)

        self.push_clauses(
            ({-subvar, cnfvar} for subvar in subvars)
        )

        return cnfvar
    # --- end of visit_or (...) ---

    def visit_not(self, expr):
        # A = NOT(F)
        #  -->
        #  AND(
        #     OR(-F, -A)
        #     OR(F, A)
        #  )
        subvar = self.recur_visit_expr(expr.expr)
        cnfvar = self.get_new_var_for_expr(expr)

        self.push_clause({-subvar, -cnfvar})
        self.push_clause({subvar, cnfvar})

        return cnfvar
    # --- end of visit_not (...) ---

    def visit_symbol(self, expr):
        cnfvar = self.cnfvar_map.get(expr, None)
        if cnfvar is None:
            cnfvar = self.get_new_var_for_symbol(expr)
            assert cnfvar is not None

        return cnfvar
    # --- end of visit_symbol (...) ---

    def visit_symbol_cmp(self, expr):
        # not modelling symbol comparison.
        cnfvar = self.cnfvar_map.get(expr, None)
        if cnfvar is None:
            cnfvar = self.get_new_var_for_symbol_cmp(expr)
            assert cnfvar is not None

        return cnfvar
    # --- end of visit_symbol_cmp (...) ---

# --- end of TseitinVisitor ---
