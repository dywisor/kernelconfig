# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import re

__all__ = ["check_ebuild_file_uses_config_check"]


# def _check_ebuild_file_uses_config_check_str_in(ebuild_filepath):
#     with open(ebuild_filepath, "rt") as fh:
#         for line in fh:
#             if "CONFIG_CHECK" in line:
#                 return True
#
#     return False
# # ---


def _check_ebuild_file_uses_config_check_re(ebuild_filepath):
    expr = re.compile('CONFIG_CHECK')

    with open(ebuild_filepath, "rt") as fh:
        for line in fh:
            if expr.search(line):
                return True

    return False
# ---


check_ebuild_file_uses_config_check = \
    _check_ebuild_file_uses_config_check_re
