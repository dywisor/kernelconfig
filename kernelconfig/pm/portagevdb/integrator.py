# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...abc import informed
from ...util import accudict
from ...util import tmpdir as _tmpdir

from . import overlay
from . import base
from . import util
from . import _ebuildenv

__all__ = ["PMIntegration"]


class PMIntegration(informed.AbstractInformed):

    def __init__(
        self, install_info, source_info,
        tmpdir=None, parent_tmpdir=None,
        port_iface=None,
        **kwargs
    ):
        super().__init__(
            install_info=install_info, source_info=source_info, **kwargs
        )
        self._tmpdir = _tmpdir.get_tmpdir_or_view(tmpdir, parent_tmpdir)

        self._overlays = self.create_source_informed(
            overlay.TemporaryOverlayUnion, self._tmpdir.dodir("overlays")
        )

        self.portage_tmpdir = self._tmpdir.get_subdir("tmp")

        if port_iface is None:
            self.port_iface = self.create_loggable(base.PortageInterface)
        else:
            self.port_iface = port_iface
        # --
    # --- end of __init__ (...) ---

    def enqueue_installed_packages(self):
        port_iface = self.port_iface
        overlays = self._overlays

        any_package_added = False
        for cpv in port_iface.find_all_cpv_inheriting_linux_info():
            pkg_info = port_iface.get_package_info(cpv)

#            # does *not* work: will ignore chromium,
#            #                  for which CONFIG_CHECK is set in an eclass
#            if not util.check_ebuild_file_uses_config_check(
#                pkg_info.orig_ebuild_file
#            ):
#                self.logger.debug(
#                    "Ignoring package %s: does not use CONFIG_CHECK",
#                    pkg_info.cpv
#                )
#                continue

            if overlays.add_package(pkg_info):
                any_package_added = True
            else:
                self.logger.warning(
                    (
                        "Failed to enqueue package '%s' "
                        "for CONFIG_CHECK re-evaluation"
                    ),
                    cpv
                )
        # --

        return any_package_added
    # --- end of enqueue_installed_packages (...) ---

    def _create_config_check_map_from_accu(self, config_check_accu_map):
        # dict: config_option => (dict :: value => cpv)
        #   ==> dict: config_option => value

        # build the actual config_check map, which is a normal dict
        config_check_map = {}
        for config_option, node in config_check_accu_map.items():
            if not node:
                raise AssertionError("empty config_check_accu_map node")

            elif len(node) == 1:
                value = next(iter(node))
                assert value is True or value is False
                config_check_map[config_option] = value

            else:
                assert True in node and False in node

                # both True and False suggested for config_option
                self.logger.warning(
                    "Conflicting recommendations for config option %s",
                    config_option
                )
                self.logger.warning(
                    "want enabled: %s", ", ".join(node[True])
                )
                self.logger.warning(
                    "want disabled: %s", ", ".join(node[False])
                )
                self.logger.warning(
                    "Recommendation for %s will be ignored",
                    config_option
                )
            # --
        # --

        return config_check_map
    # --- end of _create_config_check_map_from_accu (...) ---

    def eval_config_check(self):
        """
        @return: dict where keys are config option names,
                 and values indicate whether an option should be enabled
                 or disabled
        @rtype:  C{dict} :: C{str} => C{bool}
        """
        overlays = self._overlays

        if overlays.is_empty():
            self.logger.info("No packages found - nothing to do")
            return None
        # --

        overlays.setup(self.port_iface)
        config_check_eval_env = self.create_informed(
            _ebuildenv.ConfigCheckEbuildEnv,
            tmpdir=self.portage_tmpdir
        )
        config_check_eval_env.setup(self.port_iface)

        config_check_accu_map = accudict.DictAccumulatorDict()
        for cpv, config_check_submap in (
            config_check_eval_env.iter_eval_config_check(
                overlays.iter_packages()
            )
        ):
            if config_check_submap:
                for config_option, value in config_check_submap.items():
                    config_check_accu_map.add(config_option, (value, cpv))
        # --

        return self._create_config_check_map_from_accu(config_check_accu_map)
    # --- end of eval_config_check (...) ---

    def get_package_build_time_config_check(self):
        any_package_found = False

        config_check_accu_map = accudict.DictAccumulatorDict()
        for cpv, config_check_str in self.port_iface.zipmap_get_var(
            self.port_iface.find_all_cpv_inheriting_linux_info(),
            "CONFIG_CHECK"
        ):
            if config_check_str:
                config_check_submap = util.parse_config_check(
                    config_check_str, logger=self.logger
                )
                if config_check_submap:
                    for config_option, value in config_check_submap.items():
                        config_check_accu_map.add(config_option, (value, cpv))

                    # unlikely enqueue_installed_packages(),
                    # only packages with non-empty CONFIG_CHECK
                    # count towards "any package found"
                    any_package_found = True
            # --
        # --

        if not any_package_found:
            self.logger.info("No packages with non-empty CONFIG_CHECK found!")
            return None
        else:
            return self._create_config_check_map_from_accu(
                config_check_accu_map
            )
    # --- end of get_package_build_time_config_check (...) ---

# --- end of PMIntegration ---
