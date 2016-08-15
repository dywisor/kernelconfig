# kernelconfig -- Kconfig symbol types
# -*- coding: utf-8 -*-

import re
import enum
import numbers

from .abc import symbol as _symbol_abc

__all__ = [
    "KconfigSymbolValueType",
    "TristateKconfigSymbolValue",
    "TristateKconfigSymbol",
    "BooleanKconfigSymbol",
    "StringKconfigSymbol",
    "IntKconfigSymbol",
    "HexKconfigSymbol",
    "UndefKconfigSymbol",
    "unpack_value_str",
    "is_boolean_symbol",
    "is_stringlike_symbol",
    "is_tristate_symbol",
]


class TristateKconfigSymbolValue(enum.IntEnum):
    n = 0
    m = 1
    y = 2

    def __and__(self, other):
        return min(self, other) if isinstance(other, int) else NotImplemented

    def __or__(self, other):
        return max(self, other) if isinstance(other, int) else NotImplemented

    def __neg__(self):
        # pylint: disable=E1101
        return self.__class__(2 - self.value)

    __invert__ = __neg__

    def __str__(self):
        # pylint: disable=E1101
        return self.name

# --- end of TristateKconfigSymbolValue ---


class KconfigSymbolDefault(_symbol_abc.AbstractKconfigDepObject):
    __slots__ = []

    def evaluate_vis_dep(self, symbol_value_map):
        if self.vis_dep is None:
            return TristateKconfigSymbolValue.y
        else:
            return self.vis_dep.evaluate(symbol_value_map)

    def evaluate_dir_dep(self, symbol_value_map):
        if self.dir_dep is None:
            return None
        else:
            return self.dir_dep.evaluate(symbol_value_map)

# --- end of KconfigSymbolDefault ---


class _KconfigSymbol(_symbol_abc.AbstractKconfigSymbol):
    # pylint: disable=W0223
    __slots__ = []

    VALUE_FMT_STR = "{name}={value!s}"

    DEP_VALUE_REINTERPRET_MAP = {}
    DEP_VALUE_REINTERPRET_M_AS_Y = {
        TristateKconfigSymbolValue.m: TristateKconfigSymbolValue.y
    }

    def evaluate_dir_dep(self, symbol_value_map):
        if self.dir_dep is None:
            trival = TristateKconfigSymbolValue.y
        else:
            trival = self.dir_dep.evaluate(symbol_value_map)

        return self.DEP_VALUE_REINTERPRET_MAP.get(trival, trival)
    # --- end of evaluate_dir_dep (...) ---

    def evaluate_vis_dep(self, symbol_value_map):
        if self.vis_dep is None:
            trival = TristateKconfigSymbolValue.y
        else:
            trival = self.vis_dep.evaluate(symbol_value_map)

        return self.DEP_VALUE_REINTERPRET_MAP.get(trival, trival)
    # --- end of evaluate_vis_dep (...) ---

    def get_visible_default_expr(self, symbol_value_map):
        # pylint: disable=E1133
        if not self.defaults:
            return (None, None)

        for sym_default in self.defaults:
            vis_val = sym_default.evaluate_vis_dep(symbol_value_map)
            if vis_val:
                return (sym_default, vis_val)
        # -- end for

        return (None, None)
    # --- end of get_visible_default_expr (...) ---

    @classmethod
    def supports_defaults(cls):
        # in principle, dir_dep contains the default value
        # However, the methods available for evaluating deps/finding a solution
        # degenerate that value to tristate.
        # So, generally, "defaults" are not supported, except for tristate.
        return False

    def evaluate_default(self, symbol_value_map):
        # provided for all classes,
        # whether their defaults should participate in config resolving or not
        sym_default, vis_val = self.get_visible_default_expr(symbol_value_map)
        if sym_default is None:
            return None

        else:
            dir_dep_val = sym_default.evaluate_dir_dep(symbol_value_map)
            return (dir_dep_val, vis_val)
    # --- end of evaluate_default (...) ---

    @classmethod
    def get_value_fmt_arg(cls, value):
        return value

    def format_value(self, value, name_convert=None):
        if not value:
            return self.format_value_is_not_set(name_convert=name_convert)
        else:
            return self.VALUE_FMT_STR.format(
                name=(
                    self.name if name_convert is None
                    else name_convert(self.name)
                ),
                value=self.get_value_fmt_arg(value)
            )

# --- end of _KconfigSymbol ---


class TristateKconfigSymbol(_KconfigSymbol):
    __slots__ = []
    type_name = "tristate"

    @classmethod
    def supports_defaults(cls):
        return True

    @classmethod
    def normalize_and_validate(cls, value, lenient=False):
        # FIXME: handle "value is True" specially?
        if isinstance(value, numbers.Number):
            # this may raise a ValueError
            return TristateKconfigSymbolValue(value)
        else:
            raise ValueError(value)
    # ---

    @classmethod
    def check_value_within_vis_range(cls, vis_value, value):
        if not vis_value:
            return False
        else:
            return value <= vis_value

    def get_lkconfig_value_repr(self, value):
        return int(value)

# --- end of TristateKconfigSymbol ---


class BooleanKconfigSymbol(TristateKconfigSymbol):
    __slots__ = []
    type_name = "boolean"

    DEP_VALUE_REINTERPRET_MAP = _KconfigSymbol.DEP_VALUE_REINTERPRET_M_AS_Y

    @classmethod
    def normalize_and_validate(cls, value, lenient=False):
        normval = super().normalize_and_validate(value)

        if normval == TristateKconfigSymbolValue.m:
            if lenient:
                return TristateKconfigSymbolValue.y
            else:
                raise ValueError(value)

        return normval
    # --- end of normalize_and_validate (...) ---

    @classmethod
    def check_value_within_vis_range(cls, vis_value, value):
        if not vis_value:
            return False
        elif value is TristateKconfigSymbolValue.m:
            return False
        else:
            return value <= vis_value

# --- end of BooleanKconfigSymbol ---


class StringKconfigSymbol(_KconfigSymbol):
    __slots__ = []
    type_name = "string"

    VALUE_FMT_STR = "{name}=\"{value!s}\""

    DEP_VALUE_REINTERPRET_MAP = _KconfigSymbol.DEP_VALUE_REINTERPRET_M_AS_Y

    # apparently, the only char that actually gets escaped in Makefile
    # variables is #, the (un)escaping of quotes ("') is done by the shell
    _SPECIAL_CHARS = re.escape("#")

    UNESCAPE_CHR_REGEXP = re.compile(r'\\([{}])'.format(_SPECIAL_CHARS))
    ESCAPE_CHR_REGEXP = re.compile(r'[{}]'.format(_SPECIAL_CHARS))

    @classmethod
    def unescape_value(cls, inval):
        return cls.UNESCAPE_CHR_REGEXP.sub(r'\1', inval)
    # ---

    @classmethod
    def escape_value(cls, inval):
        return cls.ESCAPE_CHR_REGEXP.sub(r'\\\1', inval)
    # ---

    @classmethod
    def normalize_and_validate(cls, value, lenient=False):
        return value  # which will be converted to str when necessary
    # --- end of normalize_and_validate (...) ---

    @classmethod
    def get_value_fmt_arg(cls, value):
        return cls.escape_value(value)

    @classmethod
    def check_value_within_vis_range(cls, vis_value, value):
        if not vis_value:
            return False
        elif value is TristateKconfigSymbolValue.m:
            return False
        else:
            return True

    def get_lkconfig_value_repr(self, value):
        return value

# --- end of StringKconfigSymbol ---


class IntKconfigSymbol(_KconfigSymbol):
    __slots__ = []
    type_name = "int"

    VALUE_FMT_STR = "{name}={value:d}"

    DEP_VALUE_REINTERPRET_MAP = _KconfigSymbol.DEP_VALUE_REINTERPRET_M_AS_Y

    @classmethod
    def normalize_and_validate(cls, value, lenient=False):
        return int(value)
    # --- end of normalize_and_validate (...) ---

    @classmethod
    def check_value_within_vis_range(cls, vis_value, value):
        if not vis_value:
            return False
        elif value is TristateKconfigSymbolValue.m:
            return False
        else:
            return True

    def get_lkconfig_value_repr(self, value):
        if value is TristateKconfigSymbolValue.n:
            return value
        else:
            return str(value)

# --- end of IntKconfigSymbol ---


class HexKconfigSymbol(IntKconfigSymbol):
    __slots__ = []
    type_name = "hex"

    VALUE_FMT_STR = "{name}={value:#x}"

    def get_lkconfig_value_repr(self, value):
        if value is TristateKconfigSymbolValue.n:
            return value
        else:
            return hex(value)

# --- end of HexKconfigSymbol ---


class UndefKconfigSymbol(StringKconfigSymbol):
    __slots__ = []
    type_name = "undef"

    @classmethod
    def normalize_and_validate(cls, value, lenient=False):
        raise ValueError(value)
    # --- end of normalize_and_validate (...) ---

    def get_lkconfig_value_repr(self, value):
        raise ValueError(value)

# --- end of UndefKconfigSymbol ---


@enum.unique
class KconfigSymbolValueType(enum.Enum):
    # to avoid name collisions, prefix value types with "v_"
    v_unknown = UndefKconfigSymbol
    v_tristate = TristateKconfigSymbol
    v_boolean = BooleanKconfigSymbol
    v_string = StringKconfigSymbol
    v_int = IntKconfigSymbol
    v_hex = HexKconfigSymbol

    def __str__(self):
        return self.value.type_name  # pylint: disable=E1101
# --- end of KconfigSymbolValueType ---


def unpack_value_str(inval):
    """Converts a str value from dubious sources to a value suitable
    for storing in a kconfig symbol X value dict.
    Also detects the type of the value.

    @raises: ValueError if inval is faulty

    @param inval:  input value
    @type  inval:  necessarily C{str}

    @return: 2-tuple (value type, value),
             the value type can also be used for creating kconfig symbols
    @rtype:  2-tuple (
               L{KconfigSymbolValueType},
               C{str}|C{int}|L{TristateKconfigSymbolValue})
    """
    _vtype = KconfigSymbolValueType

    if not inval:
        raise ValueError()

    elif inval == "n":
        # tristate or boolean value
        # or inval in {"n", "m", "y"}: getattr(_, inval)
        return (_vtype.v_tristate, TristateKconfigSymbolValue.n)
    elif inval == "m":
        return (_vtype.v_tristate, TristateKconfigSymbolValue.m)
    elif inval == "y":
        return (_vtype.v_tristate, TristateKconfigSymbolValue.y)

    elif inval[0] in "\"'" and inval[0] == inval[-1] and len(inval) > 1:
        # string value (always quoted)
        return (
            _vtype.v_string,
            StringKconfigSymbol.unescape_value(inval[1:-1])
        )

    else:
        # could be int w/ base 10
        try:
            intval = int(inval, 10)
        except ValueError:
            pass
        else:
            return (_vtype.v_int, intval)

        # otherwise, could be int w/ base 16
        try:
            intval = int(inval, 0x10)
        except ValueError:
            pass
        else:
            return (_vtype.v_hex, intval)

        # unknown value
        raise ValueError(inval)
# --- end of unpack_value_str (...) ---


def is_boolean_symbol(sym):
    return sym.__class__ is BooleanKconfigSymbol
# --- end of is_boolean_symbol (...) ---


def is_stringlike_symbol(sym):
    return isinstance(sym, (StringKconfigSymbol, IntKconfigSymbol))
# --- end of is_stringlike_symbol (...) ---


def is_tristate_symbol(sym):
    return sym.__class__ is TristateKconfigSymbol
# --- end of is_tristate_symbol (...) ---
