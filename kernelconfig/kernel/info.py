# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os

__all__ = ["KernelInfo"]


class KernelInfo(object):

    def __init__(self, srctree, arch, srcarch, kernelversion):
        super().__init__()
        self.srctree = srctree
        self.arch = arch
        self.srcarch = srcarch
        self.kernelversion = kernelversion
    # --- end of __init__ (...) ---

    def get_filepath(self, relpath=None):
        norm_relpath = (
            os.path.normpath(relpath).strip(os.path.sep)
            if relpath else None
        )
        if norm_relpath:
            return os.path.join(self.srctree, norm_relpath)
        else:
            return self.srctree
    # ---

    def setenv(self, dst_env=None):
        if dst_env is None:
            dst_env = os.environ

        for key, val in [
            ('ARCH', self.arch),
            ('SRCARCH', self.srcarch),
            ('srctree', self.srctree),
            ('KERNELVERSION', self.kernelversion)
        ]:
            if val is not None:
                dst_env[key] = val
            else:
                dst_env.pop(key, None)
            # --
        # --
    # --- end of setenv (...) ---

# --- end of KernelInfo ---
