# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import shutil


__all__ = [
    "get_cpu_count",
    "get_free_space",
    "get_free_space_m",
]


if hasattr(os, "cpu_count"):
    # Python >= 3.4
    get_cpu_count = os.cpu_count

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
