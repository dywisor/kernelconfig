# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc

from ..abc import choices as _choices_abc
from .. import symbol


__all__ = [
    "TristateConfigDecision",
    "BooleanConfigDecision",
    "StringConfigDecision",
    "IntConfigDecision",
]


class _BooleanAlikeConfigDecision(
    _choices_abc.AbstractRestrictionSetConfigDecision
):
    __slots__ = []

    def get_decisions(self):
        if self.values is None:
            return None
        else:
            # [y,m,n]
            return sorted(self.values, reverse=True)

    def disable(self, source=None):
        return self.update_restrictions(
            [symbol.TristateKconfigSymbolValue.n], source=source
        )

    def builtin(self, source=None):
        return self.update_restrictions(
            [symbol.TristateKconfigSymbolValue.y], source=source
        )

# --- end of _BooleanAlikeConfigDecision ---


class _ValueConfigDecision(_choices_abc.AbstractValueConfigDecision):
    __slots__ = []

    @abc.abstractproperty
    def EXTEND_VALUE_TYPES(cls):
        raise NotImplementedError()

    def disable(self, source=None):
        # bypasses value check
        return self.do_set_value(
            symbol.TristateKconfigSymbolValue.n, source=source
        )

    def module(self, source=None):
        return self.operation_not_supported("module", source=source)

    def builtin(self, source=None):
        # take over .default?
        return self.operation_not_supported("builtin", source=source)

    def builtin_or_module(self, source=None):
        return self.operation_not_supported(
            "builtin_or_module", source=source
        )

    def check_append_or_add(self, value, source=None):
        # 3-tuple (can_op, prev_val, normval)
        try:
            normval = self.typecheck_value(value)
        except ValueError:
            self.logger.error("Invalid value: %r", value)
            return (False, None, None)

        if not isinstance(normval, self.EXTEND_VALUE_TYPES):
            self.logger.error(
                "add/append value must be %s: %r",
                self.EXTEND_VALUE_TYPES, normval
            )
            return (False, None, None)

        elif self.value is symbol.TristateKconfigSymbolValue.n:
            self.logger.error(
                "cannot add/append %r to disabled option", normval
            )
            return (False, self.value, normval)

        elif self.value is not None:
            return (True, self.value, normval)

        elif self.default is symbol.TristateKconfigSymbolValue.n:
            return (True, None, normval)

        else:
            return (True, self.default, normval)
    # --- end of check_append_or_add (...) ---

# --- end of _ValueConfigDecision ---


class TristateConfigDecision(_BooleanAlikeConfigDecision):
    __slots__ = []

    def module(self, source=None):
        return self.update_restrictions(
            [symbol.TristateKconfigSymbolValue.m], source=source
        )

    def builtin_or_module(self, source=None):
        return self.update_restrictions(
            [
                symbol.TristateKconfigSymbolValue.y,
                symbol.TristateKconfigSymbolValue.m
            ],
            source=source
        )

# --- end of TristateConfigDecision ---


class BooleanConfigDecision(_BooleanAlikeConfigDecision):
    __slots__ = []

    def module(self, source=None):
        return self.operation_not_supported("module", source=source)

    def builtin_or_module(self, source=None):
        return self.builtin(source=source)

# --- end of BooleanConfigDecision ---


class IntConfigDecision(_ValueConfigDecision):
    __slots__ = []

    EXTEND_VALUE_TYPES = int

    def typecheck_value(self, value):
        return self.symbol.normalize_and_validate(
            int(value, 0) if isinstance(value, str) else value
        )

    def append(self, value, source=None):
        return self.operation_not_supported("append", source=source)

    def add(self, value, source=None):
        can_op, prev_val, normval = self.check_append_or_add(
            value, source=source
        )

        if not can_op:
            return False
        else:
            # (tristate "n" or 0) is 0
            return self.do_set_value(
                (prev_val or 0) + normval, source=source
            )

# --- end of IntConfigDecision ---


class StringConfigDecision(_ValueConfigDecision):
    __slots__ = []

    EXTEND_VALUE_TYPES = str

    def append(self, value, source=None):
        can_op, prev_val, normval = self.check_append_or_add(
            value, source=source
        )
        if not can_op:
            return False

        elif not prev_val:
            return self.do_set_value(normval, source=source)

        else:
            self.logger.debug(
                "Appending %r to decision %r", normval, prev_val
            )
            self.value = "%s %s" % (prev_val, normval)
            return True
    # --- end of append (...) ---

    def add(self, value, source=None):
        can_op, prev_val, normval = self.check_append_or_add(
            value, source=source
        )
        if not can_op:
            return False

        # dedup input
        normval_words = set(normval.split())

        if not prev_val:
            return self.do_set_value(" ".join(normval_words), source=source)

        else:
            prev_words = set(prev_val.split())
            new_words = [w for w in normval_words if w not in prev_words]

            if new_words:
                add_str = " ".join(new_words)

                self.logger.debug(
                    "Adding %r to decision %r", add_str, prev_val
                )
                self.value = "%s %s" % (prev_val, add_str)
                return True

            elif self.value is None:
                # then prev_val originates from self.default,
                # and the decision has to be made
                self.logger.debug(
                    "Setting decision to %r (from default)", prev_val
                )
                return True

            else:
                self.logger.debug("Keeping decision %r", prev_val)
                return True
    # --- end of add (...) ---

# --- end of StringConfigDecision ---
