# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

__all__ = ["get_parameter_format_vars_from_parsed_args"]


def _gen_format_vars_from_items(items):
    for key, value in items:
        yield (key, ("" if value is None else value))
# ---


def get_parameter_format_vars_from_parsed_args(parsed_args):
    """
    Converts an argparse namespace object to a dict of format variables.

    This method is used by _util._argconfig and source.locfile and therefore
    kept separately in this module (locfile does not use argconfig).

    The input is a argparse namespace as returned by e.g.
    NonExitingArgumentParser.parse_args(),
    it gets converted to a dict where each key is prefixed with "param_".

    None-values are replaced with an empty str, this is by convention.

    The format vars can be converted to environment variables by
    uppercasing the keys and str-converting the values.

    @param parsed_args:  parsed args namespace object

    @return:  format variables dict
    @type:    C{dict} :: C{str} => C{object}
    """
    return {
        "param_{}".format(key.lower()): value
        for key, value in _gen_format_vars_from_items(
            vars(parsed_args).items()
        )
    }
# ---
