# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...util import fspath


__all__ = ["KernelconfigPortageIntegrationVars", "get_vars"]


class KernelconfigPortageIntegrationVars(object):
    """
    @ivar config_check_tmpfile_relpath:  path of the temporary file
                                         for sharing the value of CONFIG_CHECK
                                         between ebuild and kernelconfig,
                                         relative to a package's temp dir $T
    @type config_check_tmpfile_relpath:  C{str}
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        obj = cls._instance
        if obj is None:
            obj = cls()
            assert obj is not None
            cls._instance = obj   # or weakref
        # --

        return obj
    # ---

    def __init__(self):
        self.config_check_tmpfile_relpath = "kernelconfig_config_check"
    # ---

    def get_config_check_tmpfile_path(self, dirpath, *dir_elements):
        relpath_elements = list(dir_elements)
        relpath_elements.append(self.config_check_tmpfile_relpath)
        return fspath.join_relpaths_v(dirpath, relpath_elements)
    # ---

# ---


get_vars = KernelconfigPortageIntegrationVars.get_instance
