# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import enum

import toposort

from ..abc import loggable
from . import symbolexpr
from . import symbol
from . import solcache


__all__ = ["ConfigGraph"]


def reversed_enumerate(listlike):
    last_idx = len(listlike) - 1
    for k, item in enumerate(reversed(listlike)):
        yield (last_idx - k, item)


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
        self.input_decisions = decisions
        self.decisions = None
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
        def set_union(*input_sets):
            """Creates a union of all input sets
            and tries to ref-use sets if there is only one non-empty.

            Returns None if no non-empty input set was given,
            a reference to any of the input sets, or a new set.
            """
            have_own_output_set = False
            output_set = None

            for input_set in input_sets:
                if not input_set:
                    pass
                elif not output_set:
                    output_set = input_set
                elif have_own_output_set:
                    output_set.update(input_set)
                else:
                    output_set = output_set | input_set
                    have_own_output_set = True

            return output_set
        # --- end of set_union (...) ---

        def get_dep_syms(expr):
            nonlocal empty_set
            if expr is not None:
                return expr.get_dependent_symbols()
            else:
                return empty_set
        # --- end of get_dep_syms (...) ---

        empty_set = set()
        dep_graph = self.dep_graph  # ref

        syms_in_need_of_expansion = set(kconfig_symbols)
        while syms_in_need_of_expansion:
            syms_next = set()
            for sym in syms_in_need_of_expansion:
                sym_deps = get_dep_syms(sym.dir_dep)
                sym_vis_deps = get_dep_syms(sym.vis_dep)

                if sym.supports_defaults() and sym.defaults:
                    sym_def_deps = set()
                    for sym_default in sym.defaults:
                        sym_def_deps.update(get_dep_syms(sym_default.dir_dep))
                        sym_def_deps.update(get_dep_syms(sym_default.vis_dep))
                    # --
                else:
                    sym_def_deps = empty_set
                # --

                sym_all_deps = set_union(sym_deps, sym_vis_deps, sym_def_deps)
                if sym_all_deps:
                    dep_graph[sym] = sym_all_deps
                    syms_next.update(sym_all_deps)
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
        self.dep_order = self._create_deporder()
        self.value_nodes = self._create_value_nodes(default_config)
    # ---

    def _resolve_upwards_propagation(self, in_decisions):
        first_grp = True
        decisions = {}
        decisions_to_expand = in_decisions

        # "expand": upwards-propagate m,y decisions
        for k, sym_group in reversed_enumerate(self.dep_order):
            if not decisions_to_expand:
                self.logger.debug(
                    "Stopping at level %2d: nothing to expand", (k+1)
                )
                break
            # --

            decisions_at_this_level = {
                sym: val
                for sym, val in decisions_to_expand.items()
                if sym in sym_group
            }

            if decisions_at_this_level:
                if first_grp:
                    self.logger.debug(
                        "Starting upwards propagation at level %2d / %2d",
                        (k+1), len(self.dep_order)
                    )
                    first_grp = False
                # --

                # __debug__ FIXME - just use update()
                for sym, val in decisions_at_this_level.items():
                    if sym in decisions:
                        raise AssertionError("cannot re-add sym decision")
                    # --
                    decisions[sym] = val
                # --

                upward_decisions = {
                    sym: val
                    for sym, val in decisions_to_expand.items()
                    if sym not in sym_group
                }

                decisions_to_expand = self.expand_decision_level_upward(
                    k, sym_group, upward_decisions, decisions_at_this_level
                )
            # --
        else:
            self.logger.debug("Stopping upwards propagation at top level")
        # --

        if decisions_to_expand:
            raise AssertionError(
                "did not upwards-propagate all decisions",
                decisions_to_expand
            )
        # --

        return decisions
    # --- end of _resolve_upwards_propagation (...) ---

    def _resolve_downwards_propagation(self, decisions):
        first_grp = True

        # "reduce" and "set": set decisions, downwards-propagate n,m
        for k, sym_group in enumerate(self.dep_order):
            if (
                not first_grp
                or any((sym in sym_group for sym in decisions))
            ):
                if first_grp:
                    self.logger.debug(
                        "Starting resolving at level %2d / %2d",
                        (k+1), len(self.dep_order)
                    )
                    first_grp = False
                # --

                self.expand_decision_level_set_and_reduce(
                    k, sym_group, decisions
                )
            # --
        else:
            self.logger.debug("Stopping at depth-most level")
    # --- end of _resolve_downwards_propagation (...) ---

    def resolve(self):
        decisions = self._resolve_upwards_propagation(self.input_decisions)
        self._resolve_downwards_propagation(decisions)
        self.decisions = decisions

    def accumulate_solutions(self, sym_group, decisions_at_this_level):
        def merge_sym_solutions(dir_dep_sol, vis_dep_sol):
            if dir_dep_sol is True:
                return vis_dep_sol
            elif vis_dep_sol is True:
                return dir_dep_sol
            else:
                sol = dir_dep_sol.copy()
                if not sol.merge(vis_dep_sol):
                    return False
                else:
                    return sol
        # --- end of merge_sym_solutions (...) ---

        def find_defaults_solution(
            sym, want_vis_values, *, _SolutionCache=solcache.SolutionCache
        ):
            """
            Find a solution so that any of the symbol's defaults dir_dep
            evaluates to true and its vis_dep to any of want_vis_values.

            Returns whether at least one solution exists
            as well as all found solutions.

            @return:  (defaults solvable, defaults sol_cache)
            """
            nonlocal want_expr_ym

            if not sym.supports_defaults() or not sym.defaults:
                return (False, None)
            # --

            defaults_solutions = []
            for sym_default in sym.defaults:
                if sym_default.dir_dep is not None:
                    def_dir_dep_solvable, def_dir_dep_solutions = (
                        sym_default.dir_dep.find_solution(want_expr_ym)
                    )
                else:
                    def_dir_dep_solvable = True
                    def_dir_dep_solutions = True
                # --

                # ignore the default if its dir_dep is not solvable
                if def_dir_dep_solvable:
                    if sym_default.vis_dep is not None:
                        def_vis_dep_solvable, def_vis_dep_solutions = (
                            sym_default.vis_dep.find_solution(want_vis_values)
                        )
                    else:
                        def_vis_dep_solvable = True
                        def_vis_dep_solutions = True
                    # --

                    # likewise, ignore the default if vis_dep is not solvable
                    if def_vis_dep_solvable:
                        # AND-merge the solutions
                        # then, if still solvable, add to defaults_solutions
                        def_solutions = merge_sym_solutions(
                            def_dir_dep_solutions, def_vis_dep_solutions
                        )
                        if def_solutions:
                            defaults_solutions.append(def_solutions)
                        # --
                    # -- end if vis_dep solvable?
                # -- end if dir_dep solvable?
            # -- end for sym_default : find solutions

            if not defaults_solutions:
                # then no default exist,
                # at least none that should be considered by the depgraph
                return (False, None)

            elif len(defaults_solutions) == 1:
                # same as below, but shortcut the return
                return (True, defaults_solutions[0])

            else:
                # create a "merged alternatives" solution
                #  merged_solution := []
                #  for solution in defaults_solutions:
                #      merged_solution.extend(solution)
                #  .

                # dedup the empty solution (a.k.a "no change")
                have_empty_sol = False
                # keep track of whether there has been at least one
                # non-empty solution
                have_nonempty_sol = False

                sol_alternatives = []
                for sol_cache in defaults_solutions:
                    if sol_cache is True:
                        if not have_empty_sol:
                            # empty solution #1/2
                            sol_alternatives.append({})
                            have_empty_sol = True
                        # --

                    else:
                        for sol_dict in sol_cache.solutions:
                            if sol_dict:
                                # non-empty solution
                                sol_alternatives.append(sol_dict)
                                have_nonempty_sol = True
                            elif not have_empty_sol:
                                # empty solution #2/2
                                assert isinstance(sol_dict, dict)
                                sol_alternatives.append({})
                                have_empty_sol = True
                            # --
                        # --
                    # --
                # -- end for sol_cache

                assert sol_alternatives

                if have_nonempty_sol:
                    alt_sol = _SolutionCache()
                    alt_sol.solutions = sol_alternatives
                elif have_empty_sol:
                    alt_sol = True
                else:
                    raise AssertionError("neither empty nor nonempty solution")

                return (True, alt_sol)
        # --- end of find_defaults_solution (...) ---

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
            sym_values = decisions_at_this_level[sym]
            assert type(sym_values) is set  # FIXME: debug assert, remove
            min_sym_value = min(sym_values)

            if min_sym_value is _TristateKconfigSymbolValue.n:
                pass

            else:
                if symbol.is_tristate_symbol(sym):
                    # then sym_value must be <= vis
                    if min_sym_value is _TristateKconfigSymbolValue.y:
                        want_vis_values = want_expr_y
                    else:
                        want_vis_values = want_expr_ym

                else:
                    want_vis_values = want_expr_ym
                # --

                # FIXME: a single solution cache for both dir_dep and vis_dep
                #        would be sufficient
                #        Actually, that's how Expr._find_solution() works
                #
                if sym.dir_dep is not None:
                    dir_dep_solvable, dir_dep_solutions = (
                        sym.dir_dep.find_solution(want_expr_ym)
                    )
                    if not dir_dep_solvable:
                        raise ConfigUnresolvableError(
                            "symbol dir deps", sym.name
                        )
                    del dir_dep_solvable  # not used outside of this block
                else:
                    dir_dep_solutions = True
                # --

                if sym.vis_dep is not None:
                    vis_dep_solvable, vis_dep_solutions = (
                        sym.vis_dep.find_solution(want_vis_values)
                    )
                    if not vis_dep_solvable:
                        raise ConfigUnresolvableError(
                            "symbol vis deps", sym.name
                        )
                    del vis_dep_solvable  # not used outside of this block
                else:
                    vis_dep_solutions = True
                # --

                dep_solutions = merge_sym_solutions(
                    dir_dep_solutions, vis_dep_solutions
                )
                if not dep_solutions:
                    raise ConfigUnresolvableError(
                        "combined symbol deps", sym.name
                    )
                # --

                if accumulated_solutions is True:
                    accumulated_solutions = dep_solutions

                elif dep_solutions is True:
                    pass

                elif not accumulated_solutions.merge(dep_solutions):
                    raise ConfigUnresolvableError(
                        "group", decisions_at_this_level
                    )
                # -- end if <merge solutions>
            # -- end if <find solutions>
        # -- end for decision symbol

        if accumulated_solutions is True:
            return True
        else:
            return accumulated_solutions.get_solutions()
    # --- end of accumulate_solutions (...) ---

    def expand_decision_level_set_and_reduce(
        self, level, sym_group, decisions
    ):
        _TristateKconfigSymbolValue = symbol.TristateKconfigSymbolValue
        _is_tristate_symbol = symbol.is_tristate_symbol
        _is_stringlike_symbol = symbol.is_stringlike_symbol

        def check_value_within_vis_range(sym, sym_vis_dep_val, new_val):
            if not sym_vis_dep_val:
                return False

            elif (
                not _is_tristate_symbol(sym)
                and new_val == _TristateKconfigSymbolValue.m
            ):
                return False

            elif _is_stringlike_symbol(sym):
                return True

            else:
                return new_val <= sym_vis_dep_val
        # --- end of check_value_within_vis_range (...) ---

        def iter_pick_tristate_decision_value(value_candidates):
            if _TristateKconfigSymbolValue.m in value_candidates:
                yield _TristateKconfigSymbolValue.m

            if _TristateKconfigSymbolValue.y in value_candidates:
                yield _TristateKconfigSymbolValue.y

            if _TristateKconfigSymbolValue.n in value_candidates:
                yield _TristateKconfigSymbolValue.n
        # ---

        def iter_pick_boolean_decision_value(value_candidates):
            if _TristateKconfigSymbolValue.y in value_candidates:
                yield _TristateKconfigSymbolValue.y

            if _TristateKconfigSymbolValue.n in value_candidates:
                yield _TristateKconfigSymbolValue.n
        # ---

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
        #         leave symbol as-is, will be handled by oldconfig
        #
        #     else
        #         leave symbol as-is
        #
        #     end if
        # end loop
        for sym in sym_group:
            sym_value_node = self.value_nodes[sym]

            if sym in decisions:
                if (
                    sym_value_node.status >= ConfigValueDecisionState.default
                    and sym_value_node.value in decisions[sym]
                ):
                    self.logger.debug(
                        "Keeping %s=%s", sym.name, sym_value_node.value
                    )
                    sym_value_node.mark_decided(sym_value_node.value)

                else:
                    if _is_tristate_symbol(sym):
                        decision_iter = iter_pick_tristate_decision_value(
                            decisions[sym]
                        )

                    elif sym.__class__ is symbol.BooleanKconfigSymbol:
                        decision_iter = iter_pick_boolean_decision_value(
                            decisions[sym]
                        )

                    else:
                        decision_iter = iter(decisions[sym])
                    # --

                    dep_eval = None
                    for sym_value in decision_iter:
                        if sym_value is _TristateKconfigSymbolValue.n:
                            self.logger.debug("Disabling %s", sym.name)
                            sym_value_node.mark_decided(sym_value)
                            break

                        else:
                            if dep_eval is None:
                                dep_eval = sym.evaluate_vis_dep(
                                    symbol_value_map
                                )
                            # --

                            if check_value_within_vis_range(
                                sym, dep_eval, sym_value
                            ):
                                self.logger.debug(
                                    "Setting %s to %s", sym.name, sym_value
                                )
                                sym_value_node.mark_decided(sym_value)
                                break

                            else:
                                self.logger.debug(
                                    (
                                        'Cannot set symbol %s to %s, '
                                        'vis_deps evaluated to %s'
                                    ), sym.name, sym_value, dep_eval
                                )
                            # --
                        # --
                    else:
                        raise AssertionError(
                            "not resolved or no value candidates: {}".format(
                                sym.name
                            )
                        )
                    # -- end for
                # -- end if already set
            # -- end if sym decision
        # -- end for sym
    # --- end of expand_decision_level_set_and_reduce (...) ---

    def expand_decision_level_upward(
        self, level, sym_group, upward_decisions, decisions_at_this_level
    ):
        # find solutions
        solutions = self.accumulate_solutions(
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
            # no additional decisions
            upward_solution = {}

        else:
            upward_solution = self.pick_solution(upward_decisions, solutions)

            if not upward_solution and upward_decisions:
                raise AssertionError(
                    "decision filtered out while computing upward solution",
                    decisions_at_this_level, upward_solution, upward_decisions
                )
            # --
        # --

        return upward_solution
    # --- end of expand_decision_level_upward (...) ---

    def pick_solution(self, upward_decisions, solutions):
        vset_no = {symbol.TristateKconfigSymbolValue.n, }

        def create_decisions(solution):
            # create a new decisions dict,
            # rate its "weight"
            #
            #  lower weight means less impact (at the upper level)
            #
            dec = upward_decisions.copy()
            change_count = 0

            for sym, values in solution.items():
                sym_value_node = self.value_nodes[sym]

                # is there an existing decision for sym?
                if sym in dec:
                    # must be a further restriction
                    dec_values = dec[sym] & values
                    if not dec_values:
                        self.logger.debug(
                            (
                                'Discarding decision-conflicting solution %r'
                                ', conflicts with %s (%r)'
                            ), solution, sym.name, dec[sym]
                        )
                        return (None, None)
                    # --

                    dec[sym] = dec_values

                # is there a defconfig value for sym?
                elif sym_value_node.value in values:
                    # greedily prefer that value,
                    #  resulting in a no-change for sym

                    dec[sym] = {sym_value_node.value, }

                # has sym already been decided?
                elif sym_value_node.status >= ConfigValueDecisionState.decided:
                    raise AssertionError(
                        "in upwards mode, how can an upper node be decided?"
                    )
                    # discard solution that would override previous
                    # decisions
                    self.logger.debug(
                        "Discarding decision-conflicting solution %r",
                        solution
                    )
                    return (None, None)

                else:
                    dec_values = values - vset_no
                    if not dec_values:
                        # discard "n" solution
                        self.logger.debug(
                            "Discarding n decision %r", solution
                        )
                        return (None, None)
                    # --

                    dec[sym] = dec_values
                    change_count += 1
                # --
            # -- end for

            return (change_count, dec)
        # --- end of create_decisions (...) ---

        decision_solutions = []
        for solution in solutions:
            decisionv = create_decisions(solution)
            if decisionv[-1] is not None:
                decision_solutions.append(decisionv)
        # -- end for solutions

        if not decision_solutions:
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
            return sorted(decision_solutions, key=lambda xv: xv[0])[0][1]
    # --- end of pick_solution (...) ---

# --- end of ConfigGraph ---
