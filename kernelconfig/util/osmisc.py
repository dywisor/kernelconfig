# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import shutil

from . import fspath


__all__ = [
    "get_cpu_count",
    "get_free_space",
    "get_free_space_m",
    "which",
    "which_sbin",
    "envbool_nonempty",
]


if hasattr(os, "cpu_count"):
    # Python >= 3.4
    get_cpu_count = os.cpu_count  # pylint: disable=E1101

elif hasattr(os, "sched_getaffinity"):
    # Python 3.3
    def get_cpu_count():
        return len(os.sched_getaffinity(0))

else:
    # Python < 3.3
    #  Since the minimum Python version is 3.3, this block is not implemented.

    def get_cpu_count():
        # try multiprocessing.cpu_count(), catch NotImplementedError
        raise NotImplementedError()
# --


def get_free_space(filepath):
    # Python >= 3.3: shutil.disk_usage()
    return shutil.disk_usage(filepath).free
    # vfs_info = os.statvfs(filepath)
    # return (vfs_info.f_frsize * vfs_info.f_bavail)
# --- end of get_free_space (...) ---


def get_free_space_m(filepath):
    return get_free_space(filepath) // (1024 * 1024)
# --- end of get_free_disk_space_m (...) ---


which = shutil.which


def which_sbin(prog, *, path=None, **kwargs):
    def concat_lookup_path(parts):
        # dedup: iter_dedup(*<<p.split(":") for p in parts>>)
        return ":".join(filter(None, parts))
    # --

    path_parts = [
        (path if path is not None else os.environ.get("PATH", os.defpath))
    ]

    path_parts.extend(
        fspath.dirsuffix(["/usr/local", "/usr", "/"], "sbin")
    )

    return which(prog, path=concat_lookup_path(path_parts), **kwargs)
# --- end of which_sbin (...) ---


def envbool_nonempty(env_varname, fallback=None, *, env=None):
    """
    Returns True if env_varname is set in env (or os.environ) and not empty,
    False if it is set to the empty str,
    and fallback or None if it is not set.

    Mostly identical to bool(env.get(env_varname, fallback)),
    except that fallback does not get converted to bool by this function.

    @param   env_varname:
    @type    env_varname:  C{str}
    @keyword fallback:     fallback value in case then env_varname is not set
    @type    fallback:     undefined
    @keyword env:          env dict, defaults to None (-> os.environ)
    @type    env:

    @return:  True/False/fallback
    @rtype:   C{bool} | undefined
    """
    try:
        value = (os.environ if env is None else env)[env_varname]
    except KeyError:
        return fallback
    else:
        return bool(value)
# --- end of envbool_nonempty (...) ---
