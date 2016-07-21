# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import fnmatch
import re

from ....abc import loggable
from ....util import accudict
from ....util import pumpmatch

__all__ = ["ModuleConfigOptionsScannerStrategy"]


def _fnmatch_any(name, patterns, *, _fnmatch=fnmatch.fnmatch):
    for pattern in patterns:
        if _fnmatch(name, pattern):
            return True
    return False
# --- end of _fnmatch_any (...) ---


class ModuleNameConfigOptionsPumpPattern(pumpmatch.PumpPattern):

    IGNORABLE_AFFIXES = frozenset(("FS", "HW"))

    def __init__(self, pattern, *, fillchars="_", flags=re.I):
        super().__init__(
            pattern=pattern, fillchars=fillchars, flags=flags
        )

    def match_cost(self, match, mparts):
        # word match cost:
        #
        #    1 point for having a match
        #   (k points for 'precise' match: omitted vowels, fillchars?)
        #    2 extra points for being at a word boundary
        #      (no suffix and/or no prefix)
        rating = 1
        if not mparts.prefix_word or not mparts.suffix_word:
            rating += 2
        # --

        # prefix cost:
        #
        #   12 points for no prefix
        # <=12 points for having an "ignorable" prefix
        #    4 points for having a prefix that ends with a fillchar
        #    0 points, otherwise
        if not mparts.prefix_word:
            rating += 12

        elif not mparts.prefix_sep:
            pass

        elif mparts.prefix in self.IGNORABLE_AFFIXES:
            rating += 10

        else:
            rating += 4
        # --

        # suffix cost:
        #
        #   10 points for no suffix
        # <=10 points for having an "ignorable" suffix
        #    4 points for having a suffix that starts with a fillchar
        #    0 points, otherwise
        if not mparts.suffix_word:
            rating += 10

        elif not mparts.suffix_sep:
            pass

        elif mparts.suffix in self.IGNORABLE_AFFIXES:
            # upper not necessary
            rating += 9

        else:
            rating += 4
        # --

        return rating
    # --- end of match_cost (...) ---

# --- end of ModuleNameConfigOptionsPumpPattern ---


class ModuleConfigOptionsScannerStrategy(loggable.AbstractLoggable):

    @classmethod
    def new_default(cls):
        return cls()
    # ---

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # module=>options override
        self._module_const_mapping = accudict.SetAccumulatorDict()
        # false positives:
        #  * modules which are just object names
        self._modules_reject = set()
        #  * specific invalid option,module mappings
        self._module_options_reject = accudict.SetAccumulatorDict()
    # --- end of __init__ (...) ---

    def _accudict_add_demux_value(self, accu_dict, key, value):
        # if value is a string, add it to the AccumulatorDict
        # otherwise assume a sequence of values and add each of them
        # to the AccumulatorDict
        if isinstance(value, str):
            accu_dict.add(key, value)
        else:
            accu_dict.addv(key, value)

    def add_module_override(self, module_name, option_name):
        self._accudict_add_demux_value(
            self._module_const_mapping, module_name, option_name
        )

    def add_reject_module(self, module_name):
        self._modules_reject.add(module_name)
    # ---

    def add_reject_option_for_module(self, module_name, option_name):
        self._accudict_add_demux_value(
            self._module_options_reject, module_name, option_name
        )
    # ---

    def pick_config_options(self, modules_options_origin_map):
        return {
            module: options
            for module, options
            in self.iter_pick_config_options(modules_options_origin_map)
            if options
        }
    # ---

    def iter_pick_config_options(self, modules_options_origin_map):
        module_const_mapping = self._module_const_mapping
        pick_config_options_for_module = self._pick_config_options_for_module

        yield from module_const_mapping.items()

        for module, options_origin_map in modules_options_origin_map.items():
            if module not in module_const_mapping:
                options = pick_config_options_for_module(
                    module, options_origin_map
                )
                yield (module, options)
            # --
    # --- end of iter_pick_config_options (...) ---

    def _pick_config_options_for_module(self, module_name, options_origin_map):
        if module_name in self._modules_reject:
            return None

        else:
            options_reject = self._module_options_reject.get(module_name)
            if options_reject:
                optmap = {
                    option: options_origin_map[option]
                    for option in options_origin_map
                    if not _fnmatch_any(option, options_reject)
                }
            else:
                optmap = dict(options_origin_map)
            # --

            if len(optmap) > 1:
                # TODO
                # There is more than one config option that could possibly
                # lead to enabling <module_name>.
                # In many cases, but not all, this is a conflict!
                #
                # Possible strategies:
                #
                # * "selects" subset
                #    identify options that are connected
                #    by "selects"-type dependencies.
                #    The result is ideal IFF this set equals set(optmap).
                #    Return this set (finding out which option would select
                #    all others is not worth the computing time).
                #
                # * "fnmatch-prefer"
                #    iterate over a list of pattern lists,
                #    compare patterns against relative dirpaths.
                #    The first pattern list with any matches forms the
                #    resulting set of config options.
                #
                # * "module name <> option match"
                #    if there is a config option whose lowercase name
                #    matches the module name, return that option
                #    (possibly apply further normalizations)
                #
                # * "dirpath <> option match"
                #    return all config options whose lowercase name
                #    matches basename(dirpath)
                #
                self.logger.debug(
                    (
                        'unresolved config option conflict for %s, '
                        'discarding module'
                    ),
                    module_name
                )

                matcher = ModuleNameConfigOptionsPumpPattern(module_name)
                matches = matcher & optmap
                self.logger.warning(
                    (
                        'unresolved config option conflict for %s '
                        'has the following match list: %r'
                    ),
                    module_name, matches
                )

                return None
            # --

            return list(optmap)
    # ---

# --- end of ModuleConfigOptionsScannerStrategy ---
