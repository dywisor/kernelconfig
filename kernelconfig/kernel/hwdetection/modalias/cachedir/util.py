# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from .... import kversion

__all__ = [
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
