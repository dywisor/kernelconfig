# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ..abc import choices as _choices_abc
from .. import symbol
from . import decision
from .. import depgraph

__all__ = ["ConfigChoices"]


class ConfigChoices(_choices_abc.AbstractConfigChoices):

    DECISION_CLS_MAP = {
        symbol.TristateKconfigSymbol: decision.TristateConfigDecision,
        symbol.BooleanKconfigSymbol:  decision.BooleanConfigDecision,
        symbol.StringKconfigSymbol:   decision.StringConfigDecision,
        symbol.IntKconfigSymbol:      decision.IntConfigDecision,
        symbol.HexKconfigSymbol:      decision.IntConfigDecision
    }

    def __init__(self, config_dict, **kwargs):
        if not kwargs.get("parent_logger"):
            kwargs["parent_logger"] = getattr(config_dict, "logger", None)

        super(ConfigChoices, self).__init__(**kwargs)
        self.config = config_dict
        self.decisions = {}
    # --- end of __init__ (...) ---

    def resolve(self):
        eff_decisions = {}

        for sym, dec in self.decisions.items():
            values = dec.get_decisions()
            if values:
                # FIXME: limitation,  and forth-and-back set conversion
                #          decisions need to be sets
                eff_decisions[sym] = set(values)

            elif values is None:
                # this means that a decision object has been created in the
                # past, but it did not get used at all or the operation
                # it was requested to perform failed
                pass

            else:
                # this means that the values have been restricted to the
                # empty set, in which case no config can be created
                raise NotImplementedError("decision is empty")
        # --

        dgraph = self.create_loggable(
            depgraph.ConfigGraph,
            self.config.get_kconfig_symbols(),
            self.config, eff_decisions
        )
        dgraph.resolve()

        cfg_dict = self.config.get_new_config_dict(update=True)
        for sym, value in dgraph.iter_update_config():
            cfg_dict[sym] = value

        return cfg_dict, set(dgraph.decisions)
    # --- end of resolve (...) ---

    def commit(self):
        cfg_dict, decision_syms = self.resolve()
        self.config._incorporate_changes(cfg_dict, decision_syms)
    # --- end of commit (...) ---

    def get_or_create_decision_for_symbol(self, kconfig_symbol):
        try:
            return self.decisions[kconfig_symbol]
        except KeyError:
            pass

        decision_cls = self.DECISION_CLS_MAP.get(kconfig_symbol.__class__)
        if decision_cls is None:
            raise TypeError("no decision cls for %s" % kconfig_symbol)

        try:
            default = self.config.get_symbol_value(kconfig_symbol)
        except KeyError:
            default = None

        decision_obj = self.create_loggable(
            decision_cls, kconfig_symbol, default
        )
        self.decisions[kconfig_symbol] = decision_obj
        return decision_obj
    # --- end of get_or_create_decision_for_symbol (...) ---

    def get_or_create_decision(self, config_option):
        try:
            kconfig_symbol = self.get_symbol(config_option)
        except KeyError:
            self.logger.error("option does not exist: %s", config_option)
            return None

        return self.get_or_create_decision_for_symbol(kconfig_symbol)
    # --- end of get_or_create_decision (...) ---

    def discard_symbol(self, kconfig_symbol, source=None):
        try:
            self.decisions.pop(kconfig_symbol)
        except KeyError:
            return False
        else:
            return True
    # --- end of discard_symbol (...) ---

    def discard(self, config_option, source=None):
        try:
            kconfig_symbol = self.get_symbol(config_option)
        except KeyError:
            self.logger.warning("option does not exist: %s", config_option)
            return False

        return self.discard_symbol(kconfig_symbol, source=source)
    # --- end of discard (...) ---

    def get_symbol(self, config_option):
        return self.config.normalize_key(config_option)
    # --- end of get_symbol (...) ---

# --- end of ConfigChoices ---
