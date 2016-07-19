# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

__all__ = ["normalize_module_name"]


def normalize_module_name(name):
    return name.lower().replace("-", "_") if name else name
# --- end of normalize_module_name (...) ---
