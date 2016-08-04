# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

__all__ = ["MakeArgs"]


class MakeArgs(list):
    # TODO: config sources mk.py would be a potential consumer of this class

    @classmethod
    def fmt_var(cls, name, value):
        return "{0!s}={1!s}".format(name, value)

    def add(self, name, value):
        self.append(self.fmt_var(name, value))

    def addv(self, iterable):
        for name, value in iterable:
            self.add(name, value)
# ---
