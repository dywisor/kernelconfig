# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import logging

import pycosat

from ...abc import loggable
from .. import symbolexpr

__all__ = ["ConfigResolver"]


class ConfigResolver(loggable.AbstractLoggable):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cnf_builder = None

    def encode_decisions(self, decisions):
        if decisions:
            raise NotImplementedError("TODO: non-empty decisions")
        return []

    def get_cnf_builder(self):
        cnf_builder = self._cnf_builder
        if cnf_builder is None:
            cnf_builder = self.create_loggable(symbolexpr.TseitinVisitor)
            assert cnf_builder is not None
            self._cnf_builder = cnf_builder
        # --

        return cnf_builder
    # --- end of get_cnf_builder (...) ---

    def get_cnf(self, decisions):
        cnf_builder = self._cnf_builder
        if cnf_builder is None:
            raise AssertionError(
                "cnf must be built before calling get_cnf()"
            )
        # --

        cnf = cnf_builder.get_clauses()  # returns a new list
        cnf.extend(self.encode_decisions(decisions))
        return cnf
    # --- end of get_cnf (...) ---

    def load_dependencies(self, kconfig_symbols):
        _get_symbol_expr = symbolexpr.Expr_Symbol.get_instance
        _get_impl_expr = symbolexpr.Expr_Impl

        cnf_builder = self.get_cnf_builder()

        # @lambda log_num(num_symbols_processed, *, **priv_kwargs)
        #   logs that num_symbols_processed have been processed so far
        #
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Composing dependency CNF")
            if hasattr(kconfig_symbols, "__len__"):
                # number of symbols known in advance, log as "k/n symbols"
                log_num = (
                    lambda k,
                    *, _nsyms=len(kconfig_symbols), _f=self.logger.debug:
                    _f("%6d / %6d symbols", k, _nsyms)
                )
            else:
                # number of symbols unknown in advance, log as "k symbols"
                log_num = (
                    lambda k, *, _f=self.logger.debug: _f("%6d symbols", k)
                )
            # --
        else:
            log_num = lambda k: None
        # --

        for k, sym in enumerate(kconfig_symbols):
            if not (k % 500):
                # k+1 would already include sym, which gets processed below
                log_num(k)

            if sym.dir_dep is not None:
                # sym depends on <X>
                #  sym => <X>
                cnf_builder(
                    _get_impl_expr(_get_symbol_expr(sym), sym.dir_dep)
                )
            # --

            if sym.rev_dep is not None:
                # sym selected by <X>
                #  <X> => sym
                cnf_builder(
                    _get_impl_expr(sym.rev_dep, _get_symbol_expr(sym))
                )
            # --
        else:
            log_num(k+1)
        # -- end for sym

        self.logger.debug("Done loading dependencies")
    # --- end of load_dependencies (...) ---

    def itersolve(self, decisions):
        cnf = self.get_cnf(decisions)
        cnf_builder = self._cnf_builder
        for sat_assignment in pycosat.itersolve(cnf):
            yield cnf_builder.translate_assignment_to_expr(sat_assignment)

# --- end of ConfigResolver ---
