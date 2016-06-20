# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc

from ..util import multidir
from ..util import fspath

__all__ = []


class InstallInfoBase(object, metaclass=abc.ABCMeta):

    add_dirprefix = staticmethod(fspath.dirprefix)
    add_dirsuffix = staticmethod(fspath.dirsuffix)
    get_user_home = staticmethod(fspath.get_home_dir)
    get_user_config_dir = staticmethod(fspath.get_user_config_dir)

    @abc.abstractclassmethod
    def new_instance(cls):
        # note that this will raise NotImplementedError before abc kicks in
        raise NotImplementedError()

    @abc.abstractmethod
    def get_settings_file(self, filename):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_include_files(self, filename_pattern):
        raise NotImplementedError()

    @abc.abstractmethod
    def copy(self):
        raise NotImplementedError()

# --- end of InstallInfoBase ---


class DefaultInstallInfo(InstallInfoBase):

    CONFDIR_NAME = "kernelconfig"

    @classmethod
    def new_instance(cls, sys_config_dir, sys_data_dir):
        def to_dirlist(arg):
            if not arg:
                return None
            elif isinstance(arg, str):
                return [arg]
            else:
                return list(arg)
        # ---

        sys_config_dirs = to_dirlist(sys_config_dir)
        sys_data_dirs = to_dirlist(sys_data_dir)  # unused
        user_config_dir = cls.get_user_config_dir(cls.CONFDIR_NAME)

        settings_dirs = multidir.MultiDirEntry()
        # data_dirs = multidir.MultiDirEntry()

        if user_config_dir:
            settings_dirs.add_path(user_config_dir)
        # --

        if sys_config_dirs:
            settings_dirs.add_pathv(sys_config_dirs)
        # --

        # initially, include_file_dirs is a copy of all paths
        # from settings_dirs suffixed with "/include"
        include_file_dirs = settings_dirs.get_child("include")

        return cls(
            sys_config_dirs=sys_config_dirs,
            user_config_dir=user_config_dir,
            sys_data_dirs=sys_data_dirs,
            settings_dirs=settings_dirs,
            include_file_dirs=include_file_dirs
        )
    # --- end of new_instance (...) ---

    def __init__(
        self, *,
        sys_config_dirs, user_config_dir, sys_data_dirs,
        settings_dirs, include_file_dirs
    ):
        super().__init__()
        self.sys_config_dirs = sys_config_dirs
        self.user_config_dir = user_config_dir
        self.sys_data_dirs = sys_data_dirs

        self.settings_dirs = settings_dirs
        self.include_file_dirs = include_file_dirs
    # --- end of __init__ (...) ---

    def copy(self):
        return self.__class__(
            sys_config_dirs=self.sys_config_dirs.copy(),
            user_config_dir=self.user_config_dir,
            sys_data_dirs=self.sys_data_dirs.copy(),
            settings_dirs=self.settings_dirs.copy(),
            include_file_dirs=self.include_file_dirs.copy()
        )
    # --- end of copy (...) ---

    def get_settings_file(self, filename):
        return self.settings_dirs.get_file_path(filename)

    def get_include_files(self, filename_pattern):
        return sorted(
            self.include_file_dirs.iglob_check_type(filename_pattern),
            key=lambda kv: kv[0]
        )
# --- end of DefaultInstallInfo ---
