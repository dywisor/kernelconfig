# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import functools

from ..abc import exc
from ...util import fileget as _orig_fileget


__all__ = ["get_file", "get_file_write_to_file"]


def _fileget_exception_rewrite(func):
    def wrapper(url, *args, **kwargs):
        try:
            return func(url, *args, **kwargs)

        except (OSError, IOError):
            raise exc.ConfigurationSourceFileGetError(url) from None
    # ---

    return functools.update_wrapper(wrapper, func)
# --- end of _fileget_exception_rewrite (...) ---


get_file = _fileget_exception_rewrite(_orig_fileget.get_file)
get_file_write_to_file = \
    _fileget_exception_rewrite(_orig_fileget.get_file_write_to_file)
