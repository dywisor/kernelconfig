# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import json
import logging

from ...abc import loggable

from . import sysfs_scan
from . import modulesmap
from . import modalias
from .modalias import modulesdir


__all__ = ["HWDetect"]


class HWDetectFileFormatError(ValueError):
    pass


class HWDetect(loggable.AbstractLoggable):
    """
    This class provides methods that suggest config options
    based on information from /sys.
    """

    def create_modules_dir(self, modules_dir_arg):
        """
        Creates a modules dir object or takes ownership of an existing object.

        @param modules_dir_arg:  modules dir arg;
                                  False, None, str or modules dir object

        @return:  modules dir object
        @rtype:   subclass of L{AbstractModulesDir}
        """
        if isinstance(modules_dir_arg, modulesdir.AbstractModulesDir):
            # could copy object
            modules_dir_arg.set_logger(parent_logger=self.logger)
            return modules_dir_arg

        elif modules_dir_arg is False:
            return self.create_loggable(modulesdir.NullModulesDir())

        elif modules_dir_arg is None:
            # highly kmod-specific
            return None

        elif modules_dir_arg is True:
            raise NotImplementedError("auto-set modules dir")

        elif isinstance(modules_dir_arg, str):
            return self.create_loggable(
                modulesdir.ModulesDir, modules_dir_arg
            )

        else:
            raise ValueError(modules_dir_arg)
    # --- end of create_modules_dir (...) ---

    def __init__(self, install_info, source_info, modules_dir=None, **kwargs):
        """Constructor.

        @param   install_info:
        @param   source_info:
        @keyword modules_dir:   directory containing files necessary for
                                modalias => module name translation.
                                Defaults to None.
        @type    modules_dir:   subclass of L{AbstractModulesDir} or C{None}
        """
        super().__init__(**kwargs)
        self.install_info = install_info
        self.source_info = source_info

        self.modules_map = self.create_loggable(
            modulesmap.ModulesMap, self.source_info
        )

        self.modalias_map = self.create_loggable(
            modalias.ModaliasLookup,
            mod_dir=self.create_modules_dir(modules_dir)
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
        modalias_map = self.get_modalias_map()
        if modalias_map.lazy_init():
            return self.translate_module_names_to_config_options(
                self.get_modalias_map().lookup_v(modaliases)
            )
        else:
            self.logger.info(
                "Mapping module aliases to modules is not available"
            )
            return (modaliases, None)
    # --- end of translate_modalias_to_config_options (...) ---

    def detect_modules_via_driver_symlink(self):
        # get driver names from "driver" symlinks in /sys
        #
        #  This information source has no special requirements except that
        #  drivers need to be already loaded for (ideally) all devices.
        #
        #  drivers_origin_map is a dict :: driver => {origin}
        self.logger.info("Detecting hardware: loaded drivers")
        drivers_origin_map = sysfs_scan.scan_drivers()
        self.logger.debug(
            "Discovered %d modules via drivers",
            len(drivers_origin_map)
        )
        return drivers_origin_map
    # --- end of detect_modules_via_driver_symlink (...) ---

    def _detect_modules_via_modalias_from_list(self, arg):
        modalias_map = self.get_modalias_map()
        if modalias_map.lazy_init():
            self.logger.info("Detecting hardware: modalias")
            modalias_origin_map = self.get_modalias_map().lookup_v(arg)
            self.logger.debug(
                "Discovered %d modules via modalias",
                len(modalias_origin_map)
            )
            return modalias_origin_map
        else:
            self.logger.info(
                "Skipping modalias-based hardware detection: no modules dir"
            )
            return None
    # --- end of _detect_modules_via_modalias_from_list (...) ---

    def detect_modules_via_modalias(self):
        # get driver names from "modalias" files in /sys
        #
        #  This information source is always available,
        #  but needs a modules.alias file
        #  (and other files from /lib/modules/*/).
        #
        # Since kernelconfig does not implement modules.alias file
        # handling in any way yet (cmdline, cached creation, ...),
        # this feature should be considered as highly experimental,
        # the information comes from an uncontrolled source.
        #

        # scan /sys only if a modalias_map is available,
        # _detect_modules_via_modalias_from_list() will call lazy-init again
        # (which will be a no-op/no-act then)
        modalias_map = self.get_modalias_map()
        if modalias_map.lazy_init():
            return self._detect_modules_via_modalias_from_list(
                sysfs_scan.scan_modalias()
            )

        else:
            self.logger.info(
                "Skipping modalias-based hardware detection: no modules dir"
            )
            return None
    # --- end of detect_modules_via_modalias (...) ---

    def _detect_modules_merge_info_sources(self, driver_list, modalias_list):
        """
        @return: 3-tuple (
                   all detected modules,
                   modules for which no config options could be found,
                   config options
                 )
        @rtype:  3-tuple (C{set}, C{list}, C{list}) (item type C{str})
        """
        # create a combined set of modules to lookup
        # * from driver symlinks
        # * from modalias
        modules_to_lookup = set()
        for modules_input in filter(
            None,
            (driver_list, modalias_list)
        ):
            modules_to_lookup.update(modules_input)

        self.logger.debug("Found %d modules", len(modules_to_lookup))

        # translate the modules set into options
        modules_missing, options = (
            self.translate_module_names_to_config_options(modules_to_lookup)
        )

        if modules_missing and not options:
            self.logger.warning(
                "Could not successfully detect at least one kernel module"
            )
        else:
            self.logger.info("Found %d config options", len(options))

        return (modules_to_lookup, modules_missing, options)
    # --- end of _detect_modules_merge_info_sources (...) ---

    def detect_modules(self):
        """
        @return: 3-tuple (
                   all detected modules,
                   modules for which no config options could be found,
                   config options
                 )
        @rtype:  3-tuple (C{set}, C{list}, C{list}) (item type C{str})
        """
        drivers_origin_map = self.detect_modules_via_driver_symlink()
        modalias_origin_map = self.detect_modules_via_modalias()

        return self._detect_modules_merge_info_sources(
            drivers_origin_map, modalias_origin_map
        )
    # --- end of detect_modules (...) ---

    def detect_modules_from_hwdetect_file(self, hwdetect_file):
        """
        @return: 3-tuple (
                   all detected modules,
                   modules for which no config options could be found,
                   config options
                 )
        @rtype:  3-tuple (C{set}, C{list}, C{list}) (item type C{str})
        """
        hwinfo = self.read_hwdetect_file(hwdetect_file)

        self.logger.info("Detecting hardware: drivers")
        driver_list = hwinfo["driver"]
        self.logger.debug(
            "Discovered %d modules via drivers",
            len(driver_list)
        )

        modalias_list = self._detect_modules_via_modalias_from_list(
            hwinfo["modalias"]
        )

        return self._detect_modules_merge_info_sources(
            driver_list, modalias_list
        )
    # --- end of detect_modules_from_hwdetect_file (...) ---

    def read_hwdetect_file(self, hwdetect_file):
        self.logger.info("Loading hwcollect file %r", hwdetect_file)

        # handling compressed files would be possible, too, see util.fileio
        with open(hwdetect_file, "rt", encoding="ascii") as fh:
            json_data = json.load(fh)

        if "version" not in json_data:
            raise HWDetectFileFormatError("missing file format version")

        data = {}
        file_format_version = json_data["version"]
        self.logger.debug(
            "hwcollect file format version is %s", file_format_version
        )

        if file_format_version == 1:
            # json_data->driver is a list of str, filter out empty values
            data["driver"] = [w for w in json_data["driver"] if w]

            # json_data->modalias is a list of str, filter out empty values
            data["modalias"] = [w for w in json_data["modalias"] if w]

        else:
            raise HWDetectFileFormatError(
                "unknown file format version: {}".format(file_format_version)
            )
        # --

        return data
    # --- end of read_hwdetect_file (...) ---

# --- end of HWDetect ---
