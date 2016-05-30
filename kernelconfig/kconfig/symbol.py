# kernelconfig -- Kconfig symbol types
# -*- coding: utf-8 -*-

import enum
import numbers

from .abc.symbol import AbstractKconfigSymbol

__all__ = [
    "TristateKconfigSymbolValue",
    "TristateKconfigSymbol",
    "BooleanKconfigSymbol",
    "StringKconfigSymbol",
    "IntKconfigSymbol",
    "HexKconfigSymbol",
    "UndefKconfigSymbol"
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
        return self.__class__(2 - self.value)

    __invert__ = __neg__

    def __str__(self):
        return self.name

# --- end of TristateKconfigSymbolValue ---


class TristateKconfigSymbol(AbstractKconfigSymbol):
    __slots__ = []
    type_name = "tristate"

    @classmethod
    def normalize_and_validate(cls, value):
        # FIXME: handle "value is True" specially?
        if isinstance(value, numbers.Number):
            # this may raise a ValueError
            return TristateKconfigSymbolValue(value)
        else:
            raise ValueError(value)
    # ---

    def format_value(self, value):
        if not value:
            return self.format_value_is_not_set()
        else:
            return "{name}={value!s}".format(name=self.name, value=value)
    # ---
# --- end of TristateKconfigSymbol ---


class BooleanKconfigSymbol(TristateKconfigSymbol):
    __slots__ = []
    type_name = "boolean"

    @classmethod
    def normalize_and_validate(cls, value):
        normval = super().normalize_and_validate(value)

        if normval == TristateKconfigSymbolValue.m:
            raise ValueError(value)

        return normval
    # --- end of normalize_and_validate (...) ---

# --- end of BooleanKconfigSymbol --


class StringKconfigSymbol(AbstractKconfigSymbol):
    __slots__ = []
    type_name = "string"

    VALUE_FMT_STR = "{name}={value!s}"

    @classmethod
    def normalize_and_validate(cls, value):
        return value  # which will be converted to str when necessary
    # --- end of normalize_and_validate (...) ---

    def format_value(self, value):
        if value is None:
            return self.format_value_is_not_set()
        else:
            # FIXME: escape quotes in value
            return self.VALUE_FMT_STR.format(name=self.name, value=value)
    # ---

# --- end of StringKconfigSymbol ---


class IntKconfigSymbol(StringKconfigSymbol):
    __slots__ = []
    type_name = "int"

    VALUE_FMT_STR = "{name}={value:d}"

    @classmethod
    def normalize_and_validate(cls, value):
        return int(value)
    # --- end of normalize_and_validate (...) ---

# --- end of IntKconfigSymbol ---


class HexKconfigSymbol(IntKconfigSymbol):
    __slots__ = []
    type_name = "hex"

    VALUE_FMT_STR = "{name}={value:#x}"
# --- end of HexKconfigSymbol ---


class UndefKconfigSymbol(StringKconfigSymbol):
    __slots__ = []
    type_name = "undef"

    @classmethod
    def normalize_and_validate(cls, value):
        raise ValueError(value)
    # --- end of normalize_and_validate (...) ---
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
