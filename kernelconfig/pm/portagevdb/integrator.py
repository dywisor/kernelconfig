# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...abc import informed
from ...util import tmpdir as _tmpdir

from . import overlay
from . import base
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

    def eval_config_check(self):
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

        return {
            pkg_info.cpv: config_check_eval_env.eval_config_check(pkg_info)
            for pkg_info in overlays.iter_packages()
        }
    # --- end of eval_config_check (...) ---

# --- end of PMIntegration ---
