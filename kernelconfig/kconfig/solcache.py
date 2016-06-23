# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import itertools

from .abc import solcache as _solcache_abc


__all__ = ["SolutionCache", "merge_solutions"]


class SolutionCache(_solcache_abc.AbstractSymbolExprSolutionCache):
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
