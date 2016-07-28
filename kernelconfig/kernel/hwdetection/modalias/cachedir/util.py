# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from .... import kversion

__all__ = [
    "MakeArgs",
    "create_kernelversion_noerr",
]


def create_kernelversion_noerr(
    version_string, *,
    constructor=kversion.KernelVersion.new_from_version_str
):
    # TODO: this should be moved to kernel.kversion
    try:
        return constructor(version_string)
    except ValueError:
        return None
# ---


class MakeArgs(list):
    # TODO: config sources mk.py would be a potential consumer of this class

    def fmt_var(self, name, value):
        return "{0!s}={1!s}".format(name, value)

    def add(self, name, value):
        self.append(self.fmt_var(name, value))

    def addv(self, iterable):
        for name, value in iterable:
            self.add(name, value)
# ---
