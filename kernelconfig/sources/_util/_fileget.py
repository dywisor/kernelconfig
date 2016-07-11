# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ..abc import exc
from ...util import fileget as _orig_fileget


__all__ = ["get_file", "get_file_write_to_file"]


def get_file(url, data=None, **kwargs):
    try:
        return _orig_fileget.get_file(url, data=data, **kwargs)

    except (OSError, IOError):
        raise exc.ConfigurationSourceFileGetError(url) from None
# ---


def get_file_write_to_file(filepath, url, data=None, **kwargs):
    try:
        return _orig_fileget.get_file_write_to_file(
            filepath, url, data=data, **kwargs
        )
    except (OSError, IOError):
        raise exc.ConfigurationSourceFileGetError(url) from None
# ---
