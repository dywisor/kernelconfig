# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import enum
import itertools

import toposort

from ..abc import loggable
from . import symbolexpr
from . import symbol


__all__ = []


@enum.unique
class ConfigValueDecisionState(enum.IntEnum):
    undecided = 1
    default = 2
    half_decided = 3
    decided = 4


class ConfigResolveError(Exception):
    pass


class ConfigOptionDecidedError(ConfigResolveError):
    pass


class ConfigUnresolvableError(ConfigResolveError):
    pass


class ConfigValueNode(object):
    __slots__ = ["value", "status"]

    def __init__(self, value, status):
        self.value = value
        self.status = status
    # ---

    def _transition(self, new_state, value):
        if new_state < self.status:
            raise ConfigOptionDecidedError(
                "cannot reset symbol w/ state < old_state"
            )

        elif new_state == self.status:
            if self.value != value:
                raise ConfigOptionDecidedError(
                    (
                        'cannot reset symbol w/ state == old_state, '
                        'value != old_value'
                    )
                )
            else:
                raise ConfigOptionDecidedError("reset same value")

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

    EXPR_VALUES_N = symbolexpr.Expr.EXPR_VALUES_N
    EXPR_VALUES_M = symbolexpr.Expr.EXPR_VALUES_M
    EXPR_VALUES_Y = symbolexpr.Expr.EXPR_VALUES_Y
    EXPR_VALUES_YM = symbolexpr.Expr.EXPR_VALUES_YM

    def __init__(self, default_config, decisions, **kwargs):
        super().__init__(**kwargs)
        self.dep_graph = {}
        self.dep_order = None
        self.value_nodes = None
        self.decisions = decisions
        self._prepare(default_config, decisions)

    def iter_update_config(self):
        # sort output
        for sym_group in self.dep_order:
            for sym in sorted(sym_group, key=lambda s: s.name):
                vnode = self.value_nodes[sym]
                if vnode.status >= ConfigValueDecisionState.half_decided:
                    yield (sym, vnode.value)

    def iter_symbol_groups_upto(self, max_level):
        for k, sym_group in enumerate(self.dep_order):
            if k >= max_level:
                break

            yield (k, sym_group)
        # --

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
        def create_node(sym):
            try:
                defval = default_config[sym]
            except KeyError:
                return ConfigValueNode(
                    symbol.TristateKconfigSymbolValue.n,
                    ConfigValueDecisionState.undecided
                )
            else:
                return ConfigValueNode(
                    (
                        symbol.TristateKconfigSymbolValue.n
                        if defval is None else defval
                    ),
                    ConfigValueDecisionState.default
                )
            # -- end try
        # ---

        return {sym: create_node(sym) for sym in self.dep_graph}
    # ---

    def _prepare(self, default_config, decision_symbols):
        self.expand_graph(default_config)
        self.expand_graph(decision_symbols)
        self.value_nodes = self._create_value_nodes(default_config)
        self.dep_order = self._create_deporder()
    # ---

    def _resolve(self, decisions, max_level):
        first_grp = True

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

                self.expand_decision_level(k, sym_group, decisions)
            # --
        else:
            self.logger.debug("Stopping at depth-most level")
        # --
    # --- end of _resolve (...) ---

    def resolve(self):
        return self._resolve(self.decisions, len(self.dep_order))

    def pick_solution(self, solutions):
        _TristateKconfigSymbolValue = symbol.TristateKconfigSymbolValue

        solutions_redux = []
        for solution in solutions:
            solution_redux = {}

            for sym, values in solution.items():
                sym_value_node = self.value_nodes[sym]

                if sym_value_node.value in values:
                    # greedily prefer that value,
                    #  resulting in a no-change for sym
                    pass

                elif sym_value_node.status >= ConfigValueDecisionState.decided:
                    # discard solution that would override previous
                    # decisions
                    self.logger.debug(
                        "Discarding decision-conflicting solution %r",
                        solution
                    )
                    break

                else:
                    # pick value from set
                    solution_redux[sym] = None

                    # this a "modified min()", it does not allow "n"
                    for pref_val in (
                        _TristateKconfigSymbolValue.m,
                        _TristateKconfigSymbolValue.y
                    ):
                        if pref_val in values:
                            solution_redux[sym] = pref_val
                            break
                    # --

                    if solution_redux[sym] is None:
                        # discard "n" solution
                        self.logger.debug(
                            "Discarding n decision %r", solution
                        )
                        break
                # --
            # -- end for solution

            if not solution_redux:
                # empty change is the minimal solution
                return True

            solutions_redux.append(solution_redux)
        # -- end for solutions

        if not solutions_redux:
            return None
        else:
            # pick a solution
            # possible measurements:
            #  * number of symbol to be set
            #      due to the recursive nature,
            #      this is not necessarily meaningful.
            #
            #  * the number of symbols possibly involved
            #      (recursion lookahead)
            #
            #  * the level at which recursion needs to start
            #
            return sorted(solutions_redux, key=len)[0]
    # --- end of pick_solution (...) ---

    def accumulate_upward_decisions(self, sym_group, decisions_at_this_level):
        _TristateKconfigSymbolValue = symbol.TristateKconfigSymbolValue
        want_expr_ym = self.EXPR_VALUES_YM
        want_expr_y = self.EXPR_VALUES_Y

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

            if sym_value is _TristateKconfigSymbolValue.n:
                pass

            elif sym.dir_dep is None:
                pass

            else:
                if symbol.is_tristate_symbol(sym):
                    if sym_value is _TristateKconfigSymbolValue.y:
                        want_expr_values = want_expr_y
                    else:
                        want_expr_values = want_expr_ym

                else:
                    # also: sym_value is tristate "m"
                    want_expr_values = want_expr_ym
                # --

                solvable, solutions = sym.dir_dep.find_solution(
                    want_expr_values
                )
                if not solvable:
                    raise ConfigUnresolvableError("symbol", sym.name)

                if accumulated_solutions is True:
                    accumulated_solutions = solutions
                else:
                    accumulated_solutions_next = merge_solutions(
                        accumulated_solutions, solutions
                    )
                    if not accumulated_solutions_next:
                        raise ConfigUnresolvableError(
                            "group", decisions_at_this_level
                        )

                    accumulated_solutions = accumulated_solutions_next
                    del accumulated_solutions_next
                # -- end if <merge solutions>
            # -- end if <find solutions>
        # -- end for decision symbol

        return accumulated_solutions
    # --- end of accumulate_upward_decisions (...) ---

    def expand_decision_level(self, level, sym_group, decisions):
        _TristateKconfigSymbolValue = symbol.TristateKconfigSymbolValue
        _is_tristate_symbol = symbol.is_tristate_symbol

        def check_upper_bound(sym, sym_value, dep_value):
            return (
                dep_value and (
                    not _is_tristate_symbol(sym)
                    or dep_value >= sym_value
                )
            )

        decisions_at_this_level = {
            sym: val for sym, val in decisions.items() if sym in sym_group
        }

        # find solutions
        solutions = self.accumulate_upward_decisions(
            sym_group, decisions_at_this_level
        )

        # resolve solutions
        #   pick a "minimal" one
        #   recursively apply that solution (up to this level - 1)
        if not solutions:
            raise ConfigUnresolvableError(
                "no solutions", decisions_at_this_level
            )

        elif solutions is True:
            # abort upwards propagation
            pass

        else:
            recur_decisions = self.pick_solution(solutions)
            if recur_decisions is True:
                pass

            elif recur_decisions:
                self._resolve(recur_decisions, level)

            else:
                raise ConfigUnresolvableError(
                    "no solution found", decisions_at_this_level
                )
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
        #         apply that decision
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

                if sym_value is _TristateKconfigSymbolValue.n:
                    self.logger.debug("Disabling %s", sym.name)
                    sym_value_node.mark_decided(sym_value)

                else:
                    dep_eval = sym.evaluate_dir_dep(symbol_value_map)

                    if check_upper_bound(sym, sym_value, dep_eval):
                        self.logger.debug(
                            "Setting %s to %s", sym.name, sym_value
                        )
                        sym_value_node.mark_decided(sym_value)

                    else:
                        raise AssertionError(
                            "not resolved", sym.name,
                            "dep-val", dep_eval,
                            "deps", str(sym.dir_dep)
                        )
                # -- end if

            elif (
                sym_value_node.value is not _TristateKconfigSymbolValue.n
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
                    dep_eval = sym.evaluate_dir_dep(symbol_value_map)
                    if not check_upper_bound(
                        sym, sym_value_node.value, dep_eval
                    ):
                        self.logger.debug(
                            "Propagating value %s to symbol %s (from %s)",
                            dep_eval, sym.name, sym_value_node.value
                        )
                        sym_value_node.mark_value_propagated(dep_eval)

                # -- end if propagate_syms
            # -- end if sym decision or propagate?
        # -- end for sym
    # --- end of expand_decision_level (...) ---

# --- end of ConfigGraph ---
