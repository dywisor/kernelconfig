# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

__all__ = [
    "identity",
    "iter_dedup",
    "get_rev_map",
    "get_revlist_map",
]


def identity(item):
    """Returns the input object as-is."""
    return item
# --- end of identity (...) ---


def iter_dedup(iterable, *, key=None):
    """
    Iterates over objects and filters out duplicates
    as determined by the 'key' function, which must return a hashable object.

    @param   iterable:  iterable of objects
    @keyword key:       key func or None for identity, defaults to None
    """
    keyfunc = identity if key is None else key
    seen = set()
    for item in iterable:
        item_key = keyfunc(item)
        if item_key not in seen:
            seen.add(item_key)
            yield item
# --- end of iter_dedup (...) ---


def get_rev_map(d):
    """
    Returns an reversed map of d :: key -> value,
    where each value is mapped to its key.

    This function should only be used if the values are unique,
    otherwise the result is undefined.
    See get_revlist_map() for a variant that addresses this issue.
    """
    return {v: k for k, v in d.items()}
# --- end of get_rev_map (...) ---


def get_revlist_map(d):
    """
    Returns a reversed map of d :: key -> value,
    where each value is mapped to a list of keys.

    Example:
        d = {0: 1, 1: 1, 2: 1, 3: 2}
        get_revlist(d)      =>  {1: 2, 2: 3}  (possibly)
        get_revlist_map(d)  =>  {1: [0,1,2], 2: [3]}
    """
    dout = {}
    for k, v in d.items():
        if v in dout:
            dout[v].append(k)
        else:
            dout[v] = [k]
    return dout
# --- end of get_revlist_map (...) ---
