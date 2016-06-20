# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os

from . import _base


class InstallInfo(_base.DefaultInstallInfo):

    @classmethod
    def new_instance(self):
        prjroot = os.getenv("KERNELCONFIG_PRJROOT")
        if not prjroot:
            raise Exception("KERNELCONFIG_PRJROOT is not set.")

        return super().new_instance(
            sys_config_dir = self.add_dirprefix(
                prjroot, ["local/config", "config"]
            ),

            sys_data_dir = self.add_dirprefix(
                prjroot, ["local/data", "files/data"]
            )
        )
