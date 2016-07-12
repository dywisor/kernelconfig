# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

__all__ = ["get_parameter_format_vars_from_parsed_args"]


def _gen_format_vars_from_items(items):
    for key, value in items:
        yield (key, ("" if value is None else value))
# ---


def get_parameter_format_vars_from_parsed_args(parsed_args):
    return {
        "param_{}".format(key.lower()): value
        for key, value in _gen_format_vars_from_items(
            vars(parsed_args).items()
        )
    }
# ---
