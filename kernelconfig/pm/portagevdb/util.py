# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import logging
import re

__all__ = [
    "check_ebuild_file_uses_config_check",
    "parse_config_check"
]


# lax expr
RE_CONFIG_CECK_ITEM = re.compile(
    r'^(?P<prefix>[\@\!\~]+)?(?P<config_option>[a-zA-Z0-9\_]+)$'
)


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


def parse_config_check(
    config_check_str, *, logger=None,
    _re_config_check_item=RE_CONFIG_CECK_ITEM
):
    """
    @return:  dict of config option name X want config option enabled
    @rtype:   dict :: C{str} => C{bool}
    """

    def parse_inner(config_check_str):
        nonlocal logger
        match_config_check_word = _re_config_check_item.match

        for word in config_check_str.split():
            match = match_config_check_word(word)
            if not match:
                logger.warning(
                    "Could not parse CONFIG_CHECK item %r", word
                )

            else:
                prefix = match.group("prefix")

                if "@" in prefix:
                    # "reworkmodules" -- undocumented, no example found
                    logger.warning(
                        "Skipping 'reworkmodules' CONFIG_CHECK item %r",
                        word
                    )
                else:
                    yield (
                        match.group("config_option"),
                        ("!" not in prefix)
                    )
    # --- end of parse_inner (...) ---

    if logger is None:
        logger = logging.getLogger("parse_config_check")

    config_options = collections.OrderedDict()
    for config_option, want_enabled in parse_inner(config_check_str):
        if config_option in config_options:
            # conflict!
            # if want_enabled matches the value of the existing entry: ok
            # otherwise: error, cannot recommended both
            #            CONFIG_A=ym and CONFIG_A=n at the same time
            logger.info(
                "config option appears twice in CONFIG_CHECK: %s",
                config_option
            )

            if config_options[config_option] == want_enabled:
                pass
            else:
                raise NotImplementedError(
                    "conflict in CONFIG_CHECK", config_option
                )

        else:
            config_options[config_option] = want_enabled
        # --
    # --

    return config_options
# --- end of parse_config_check (...) ---
