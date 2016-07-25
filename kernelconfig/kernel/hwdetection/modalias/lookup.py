# This file is part of kernelconfig.
# -*- coding: utf-8 -*-


from .abc import lookup as _lookup_abc
from . import _kmod


def _get_lookup_cls(*candidates):
    for candidate in candidates:
        if candidate is None:
            pass
        else:
            assert issubclass(candidate, _lookup_abc.AbstractModaliasLookup)
            if candidate.AVAILABLE:
                return candidate
    # --

    return _lookup_abc.UnavailableModaliasLookup
# ---


ModaliasLookup = _get_lookup_cls(
    _kmod.KmodModaliasLookup,
)


__all__ = ["ModaliasLookup"]
