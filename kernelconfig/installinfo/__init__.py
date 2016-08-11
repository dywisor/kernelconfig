# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

__all__ = ["get_install_info"]


from . import _base
from . import _info


class _InstallInfoStruct(object):
    _install_info = None

    @classmethod
    def get_install_info(cls):
        install_info = cls._install_info

        if install_info is None:
            if hasattr(_info, "INSTALL_INFO"):
                install_info = _info.INSTALL_INFO

            elif hasattr(_info, "InstallInfo"):
                install_info = _info.InstallInfo.new_instance()

            elif (
                _base.DefaultModuleInstallInfo.check_pym_is_installinfo(_info)
            ):
                install_info = (
                    _base.DefaultModuleInstallInfo.new_instance(_info)
                )

            else:
                raise Exception("cannot get nor instantiate install info!")
            # --

            cls._install_info = install_info
        # --

        return install_info
    # --- end of get_install_info (...) ---

# --- end of _InstallInfoStruct ---


get_install_info = _InstallInfoStruct.get_install_info
