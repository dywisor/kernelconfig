# kernelconfig -- abstract description of Kconfig-related classes
# -*- coding: utf-8 -*-

import abc


__all__ = ["AbstractSymbolExprSolutionCache"]


class AbstractSymbolExprSolutionCache(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def push_symbol(self, sym, values):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_solutions(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def merge(self, sol_cache):
        raise NotImplementedError()

    @abc.abstractmethod
    def merge_alternatives(self, alternatives):
        raise NotImplementedError()
