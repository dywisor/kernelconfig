# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

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

# --- end of HWDetect ---
