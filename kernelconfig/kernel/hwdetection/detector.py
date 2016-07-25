# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import logging

from ...abc import loggable

# from . import sysfs_scan
from . import modulesmap
from . import modalias


__all__ = ["HWDetect"]


class HWDetect(loggable.AbstractLoggable):

    def __init__(self, source_info, modules_dir=None, **kwargs):
        super().__init__(**kwargs)
        self.source_info = source_info

        self.modules_map = self.create_loggable(
            modulesmap.ModulesMap, self.source_info
        )

        self.modalias_map = self.create_loggable(
            modalias.ModaliasLookup, mod_dir=modules_dir
        )
    # --- end of __init__ (...) ---

    def get_modules_map(self):
        return self.modules_map

    def get_modalias_map(self):
        return self.modalias_map

    def translate_module_names_to_config_options(self, module_names):
        """
        Translates a sequence of kernel module names into config option names.

        @param module_names:  iterable containing kernel module names
        @type  module_names:  iterable of C{str}

        @return: 2-tuple (
                    list of modules that could not be translated,
                    deduplicated list of config options
                 )
        @rtype:  2-tuple (C{list} of C{str}, C{list} of C{str})
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            def log_module_not_found(module_name):
                self.logger.debug(
                    "config options for module %s: <not found>", module_name
                )

            def log_module_lookup_result(module_name, options):
                self.logger.debug(
                    "config options for module %s: %s",
                    module_name,
                    (", ".join(sorted(options)) if options else "<none>")
                )
            # ---
        else:
            def log_module_not_found(module_name):
                pass

            def log_module_lookup_result(module_name, options):
                pass
            # ---
        # --

        modules_map = self.get_modules_map()

        modules_not_translated = []
        options_translated = []
        # dedup options
        options_seen = set()

        for module_name in module_names:
            try:
                options = modules_map[module_name]
            except KeyError:
                log_module_not_found(module_name)
                modules_not_translated.append(module_name)
            else:
                log_module_lookup_result(module_name, options)
                for option in options:
                    if option not in options_seen:
                        options_translated.append(option)
                        options_seen.add(option)
        # -- end for

        return (modules_not_translated, options_translated)
    # --- end of translate_module_names_to_config_options (...) ---

    def translate_modalias_to_config_options(self, modaliases):
        """
        Translate a sequence of module aliases to config options.

        This is done by translating module aliases into module names first,
        and then module names to config options.

        The result is a 2-tuple (unresolved modules, resolved modules).
        Modalias identifiers for which no module could be found
        are quietly ignored.

        @param modaliases:  iterable containing kernel module names
        @type  modaliases:  iterable of C{str}

        @return: 2-tuple (
                    list of modules that could not be translated,
                    deduplicated list of config options
                 )
        @rtype:  2-tuple (C{list} of C{str}, C{list} of C{str})
        """
        return self.translate_module_names_to_config_options(
            self.modalias_map.lookup_v(modaliases)
        )
    # --- end of translate_modalias_to_config_options (...) ---

# --- end of HWDetect ---
