# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import enum
import itertools

import toposort

from ..abc import loggable
from . import symbol


__all__ = []


@enum.unique
class ConfigValueDecisionState(enum.IntEnum):
    undecided = 1
    default = 2
    half_decided = 3
    decided = 4


class ConfigValueNode(object):
    __slots__ = ["value", "status"]

    def __init__(self, value=None, status=ConfigValueDecisionState.undecided):
        self.value = value
        self.status = ConfigValueDecisionState.undecided
    # ---

    def _transition(self, new_state, value):
        if new_state < self.status:
            raise AssertionError("cannot reset symbol w/ state < old_state")

        elif new_state == self.status:
            if self.value != value:
                raise AssertionError(
                    "cannot reset symbol w/ state == old_state, value != old_value"
                )

        else:
            self.status = new_state
            self.value = value
    # --

    def mark_decided(self, value):
        self._transition(ConfigValueDecisionState.decided, value)

    def mark_value_propagated(self, value):
        self._transition(ConfigValueDecisionState.half_decided, value)

# ---



def merge_solutions(sol_list_a, sol_list_b):
    def merge_sol_dict(a, b):
        d = {}
        for sym, values in a.items():
            if sym in b:
                entry = values & b[sym]
            else:
                entry = values  # ref

            if entry:
                d[sym] = entry
            else:
                return None
        # --

        for sym in b:
            if sym not in d:
                d[sym] = b[sym]  # ref
        # --

        return d
    # ---

    solutions = []
    for sol_a, sol_b in itertools.product(sol_list_a, sol_list_b):
        sol_res = merge_sol_dict(sol_a, sol_b)
        if sol_res is not None:
            solutions.append(sol_res)

    return solutions
# ---



class ConfigGraph(loggable.AbstractLoggable):

    def __init__(self, default_config, decisions, **kwargs):
        super().__init__(**kwargs)
        self.dep_graph = {}
        self.dep_order = None
        self.value_nodes = None
        self.decisions = decisions
        self._prepare(default_config, decisions)

    def iter_symbol_groups_upto(self, max_level):
        for k, sym_group in enumerate(self.dep_order):
            if k >= max_level:
                break

            yield (k, sym_group)
        # --

    def get_symbol_level(self, sym):
        for k, sym_group in enumerate(self.dep_order):
            if sym in sym_group:
                return k

    def iter_symbols_upto(self, max_level):
        for k, sym_group in self.iter_symbol_groups_upto(max_level):
            yield from iter(sym_group)

    def expand_graph(self, kconfig_symbols):
        empty_set = set()
        dep_graph = self.dep_graph  # ref

        syms_in_need_of_expansion = set(kconfig_symbols)
        while syms_in_need_of_expansion:
            syms_next = set()
            for sym in syms_in_need_of_expansion:
                if sym.dir_dep is not None:
                    sym_deps = sym.dir_dep.get_dependent_symbols()

                    dep_graph[sym] = sym_deps
                    syms_next.update(sym_deps)
                else:
                    dep_graph[sym] = empty_set  # ref
                # --
            # -- end for

            syms_in_need_of_expansion = syms_next.difference(dep_graph)
        # -- end while
    # --- end of expand_graph (...) ---

    def _create_deporder(self):
        return list(toposort.toposort(self.dep_graph))

    def _create_value_nodes(self, default_config):
        def gen_node_parts():
            for sym in self.dep_graph:
                try:
                    defval = default_config[sym]
                except KeyError:
                    yield (
                        sym,
                        symbol.TristateKconfigSymbolValue.n,
                        ConfigValueDecisionState.undecided
                    )
                else:
                    yield (
                        sym,
                        (
                            symbol.TristateKconfigSymbolValue.n
                            if defval is None else defval
                        ),
                        ConfigValueDecisionState.default
                    )
                # --
            # --
        # ---

        return {
            sym: ConfigValueNode(val, st)
            for sym, val, st in gen_node_parts()
        }
    # ---

    def _prepare(self, default_config, decision_symbols):
        self.expand_graph(default_config)
        self.expand_graph(decision_symbols)
        self.value_nodes = self._create_value_nodes(default_config)
        self.dep_order = self._create_deporder()
    # ---

    def _resolve(self, decisions, max_level):
        first_grp = True
        upper_sym_group = set()

        for k, sym_group in enumerate(self.dep_order):
            if k >= max_level:
                self.logger.debug("Stopping at level %2d", (k+1))
                break

            if (
                not first_grp
                or any((sym in sym_group for sym in decisions))
            ):
                if first_grp:
                    self.logger.debug(
                        "Starting resolving at level %2d/%2d",
                        (k+1), min(max_level, len(self.dep_order))
                    )
                    first_grp = False
                # --

                self.expand_decision_level(
                    k, upper_sym_group, sym_group, decisions
                )
            # --

            upper_sym_group = sym_group
        else:
            self.logger.debug("Stopping at depth-most level")
        # --

    def resolve(self):
        return self._resolve(self.decisions, len(self.dep_order))

    def accumulate_upward_decisions(self, sym_group, decisions_at_this_level):
        want_expr_ym = {
            symbol.TristateKconfigSymbolValue.m,
            symbol.TristateKconfigSymbolValue.y
        }

        want_expr_y = {
            symbol.TristateKconfigSymbolValue.y,
        }

        accumulated_solutions = True

        # foreach decision symbol sym at this level loop
        #
        #    if sym value should be set to n
        #        nop
        #
        #    else if sym has no deps
        #        nop
        #
        #    else
        #        find a dep-solution so that sym can be set
        #
        #        if there is no solution
        #            unresolvable - error
        #
        #        else
        #            merge solution with previous solution, if any
        #            if merged solution empty
        #                unresolvable - error
        #        end if
        #    end if
        #
        #    decide value later.
        # end loop
        for sym in decisions_at_this_level:
            sym_value = decisions_at_this_level[sym]

            if sym_value is symbol.TristateKconfigSymbolValue.n:
                pass

            elif sym.dir_dep is None:
                pass

            else:
                if sym_value is symbol.TristateKconfigSymbolValue.y:
                    want_expr_values = want_expr_y

                elif isinstance(sym_value, (str, int)):
                    # also: sym_value is tristate "m"
                    want_expr_values = want_expr_ym

                else:
                    raise NotImplementedError(sym_value)
                # --

                solvable, solutions = sym.dir_dep.find_solution(
                    want_expr_values
                )
                if not solvable:
                    raise NotImplementedError("not resolvable", sym.name)

                if accumulated_solutions is True:
                    accumulated_solutions = solutions
                else:
                    accumulated_solutions_next = merge_solutions(
                        accumulated_solutions, solutions
                    )
                    if not accumulated_solutions_next:
                        raise NotImplementedError("unresolvable group")

                    accumulated_solutions = accumulated_solutions_next
                    del accumulated_solutions_next
                # -- end if <merge solutions>
            # -- end if <find solutions>
        # -- end for decision symbol

        return accumulated_solutions
    # --- end of accumulate_upward_decisions (...) ---

    def expand_decision_level(
        self, level, upper_sym_group, sym_group, decisions
    ):
        decisions_at_this_level = {
            sym: val for sym, val in decisions.items() if sym in sym_group
        }

        solutions = self.accumulate_upward_decisions(
            sym_group, decisions_at_this_level
        )

        # resolve solutions
        #   pick a "minimal" one
        #   recursively apply that solution (up to this level - 1)
        if not solutions:
            raise NotImplementedError("no solutions for this level")

        elif solutions is True:
            # abort upwards propagation
            pass

        else:
            if len(solutions) != 1:
                raise NotImplementedError("pick best solution out of many")

            # pick best and minimal solution
            solution = solutions[0]   # FIXME, obvy

            # FIXME: apply decisions_at_this_level before recursion
            #         otherwise, the symbols get set multiple times

            recur_decisions = {
                sym: min(values) for sym, values in solutions[0].items()
            }
            self._resolve(recur_decisions, level)
        # --

        # use of pre-loop calculate symbol X value map is ok, because
        # no symbol in sym_group depends on another symbol of this group,
        # only on symbols with less depth (level < this level),
        # and the loop below changes only symbols of this group
        #
        # Also, only symbols up to this level (exclusive)
        # are required in the map.
        symbol_value_map = {
            sym: self.value_nodes[sym].value
            for sym in self.iter_symbols_upto(level)
        }

        # foreach symbol at this level loop
        #
        #     if there is a decision for sym
        #         apply that decision  // FIXME: do that before recursion
        #
        #     else if sym depends on a decided symbol
        #          or sym depends on a half-decided symbol
        #          and the symbol is >controlling<
        #
        #         downwards-propagate "n","m" decision
        #
        #     else
        #         leave symbol as-is
        #
        #     end if
        # end loop
        for sym in sym_group:
            sym_value_node = self.value_nodes[sym]

            if sym in decisions_at_this_level:
                sym_value = decisions[sym]

                if sym_value is symbol.TristateKconfigSymbolValue.n:
                    self.logger.debug("Disabling %s", sym.name)
                    sym_value_node.mark_decided(sym_value)

                elif sym.dir_dep is None:
                    self.logger.debug("Setting %s to %s", sym.name, sym_value)
                    sym_value_node.mark_decided(sym_value)

                else:
                    dep_eval = sym.dir_dep.evaluate(symbol_value_map)

                    if (
                        dep_eval
                        and (
                            sym.__class__ is not symbol.TristateKconfigSymbolValue
                            or dep_eval >= sym_value
                        )
                    ):
                        self.logger.debug(
                            "Setting %s to %s", sym.name, sym_value
                        )
                        sym_value_node.mark_decided(sym_value)

                    else:
                        raise NotImplementedError(
                            "not resolved",
                            sym.name,
                            "dep-val", dep_eval,
                            "deps", str(sym.dir_dep)
                        )
                # -- end if

            elif (
                sym_value_node.value
                is not symbol.TristateKconfigSymbolValue.n
            ):
                # propagate n,m
                propagate_syms = set((
                    dep_sym for dep_sym in self.dep_graph[sym]
                    if (
                        self.value_nodes[dep_sym].status
                        >= ConfigValueDecisionState.half_decided
                    )
                ))

                if propagate_syms:
                    if (
                        sym.__class__ is symbol.TristateKconfigSymbol
                    ):
                        sym_value = sym_value_node.value
                    else:
                        sym_value = symbol.TristateKconfigSymbolValue.m

                    dep_eval = sym.dir_dep.evaluate(symbol_value_map)
                    if dep_eval < sym_value:
                        self.logger.debug(
                            "FIXME: downwards-propagate %s < %s for symbol %s",
                            dep_eval, sym_value, sym.name
                        )

                # --
        # --
