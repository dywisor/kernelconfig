# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc

import os    # format_info()
import stat  # format_info()

from ..util import multidir
from ..util import fspath

__all__ = []


class InstallInfoBase(object, metaclass=abc.ABCMeta):
    """
    InstallInfo objects describe where to find which
    of kernelconfig's 'data' files.

    This is the abstract base class.

    The location of these files depends on the installation type
    and are defined in the "_info" module (in this directory),
    which is created during building kernelconfig ("setup.py build").

    The "_info" module should import this module ("from . import _base"),
    and provide an concrete implementation
    of the InstallInfoBase or the DefaultInstallInfo class.

    See <prjroot>/files/installinfo/standalone.py for an example.
    """

    # a few fspath gelper functions
    add_dirprefix = staticmethod(fspath.dirprefix)
    add_dirsuffix = staticmethod(fspath.dirsuffix)
    get_user_home = staticmethod(fspath.get_home_dir)
    get_user_config_dir = staticmethod(fspath.get_user_config_dir)

    @classmethod
    def get_user_cache_dir(cls, name):
        return fspath.join_relpaths(cls.get_user_home(), ".cache", name)

    @abc.abstractclassmethod
    def new_instance(cls):
        """Creates a new installation info object.

        Intermediate/abstract classes may accept arguments here,
        but actual InstallInfo classes should not.

        @return:  new installation info object
        @rtype:   subclass of L{InstallInfoBase}
        """
        # note that this will raise NotImplementedError before abc kicks in
        raise NotImplementedError()

    @abc.abstractmethod
    def get_settings_file(self, filename):
        """Searches for a settings file and returns the absolute path to it.
        Returns anything false, e.g. None, if no file could be found.

        @param filename:  name of the settings file
                          can also be a relative path,
                          wildcard characters do not get expanded
        @type  filename:  C{str}

        @return:  absolute path to settings file or empty str or None
        @rtype:   C{str} or C{None}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_include_files(self, filename_pattern):
        """Searches for feature set files and
        returns a list of all file paths matching the given relpath pattern.

        @param filename_pattern:  a relative path,
                                  can contain wildcard characters
                                  and gets glob-expanded
        @type  filename_pattern:  C{str}

        @return:  list of absolute file paths,
                   possibly empty if no matches found
        @rtype:   C{list} of C{str}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_config_source_dirs(self):
        """
        Returns a multi dir object that provides access to config source files.

        @return:  multi dir object
        @rtype:   L{MultiDirEntry}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_script_file(self, filename):
        """Searches for a script file and returns its absolute path.
        Returns anything false, e.g. None, if no file could be found.

        There is no guarantee that the returned file path is executable,
        only that it is a regular file or a symlink to a regular file.

        @param filename:  name of the script,
                          can also be a relative path,
                          wildcard characters do not get expanded
        @type  filename:  C{str}

        @return:  absolute path to the script file or empty str or None
        @rtype:   C{str} or C{None}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_cache_dirs(self, name=None):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_cache_search_dirs(self, name=None, data_name=None):
        """
        @return:  new multi dir object
        @rtype:   L{MultiDirEntry}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def copy(self):
        """Creates and returns a copy of this installation info object.

        Certain data objects may be shared between the copy and the original,
        but modifications to the copy should not affect the original.

        @return: new copy of this object
        @rtype:  subclass of L{InstallInfoBase}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def format_info(self):
        """
        Creates a str describing the various filesystem paths used/referenced
        by this installation info object.

        @return:  fspath description
        @rtype:   C{str}
        """
        raise NotImplementedError()

# --- end of InstallInfoBase ---


class DefaultInstallInfo(InstallInfoBase):
    """
    A still-abstract concretion of InstallInfoBase
    that makes a few assumptions about the overall directory layout:

    * settings file can be found in the project-specific configuration dirs:
        get_user_config_dir("kernelconfig")
        or in one of the "system config directories"

        A typical directory list would be
        ["$HOME/.config/kernelconfig", "/etc/kernelconfig"]

    * feature set files can be found in the "include" subdirectory
      of the project-specific configuration dirs

      The list of include directories can be extended individually
      by calling <object>.include_file_dirs.add_path(<path>).

    * other data files can be found in the project-specific data dirs:
        one of the "system data directories"

        A typical directory list would be ["/usr/share/kernelconfig"].

    Derived classes must override the new_instance() class method
    and call super() with appropriate system config and system data
    directory paths.
    These paths must point to project-specific directories,
    e.g. "/etc/kernelconfig" and not just "/etc".
    The add_confdir_suffix() class method can be used for that purpose.

    @cvar CONFDIR_NAME:  name of the config subdirectory
    @type CONFDIR_NAME:  C{str}

    @ivar sys_config_dirs:    "system config directory" paths
    @type sys_config_dirs:    C{list} of C{str}
    @ivar user_config_dir:    project-specific user config directory
    @type user_config_dir:    C{str}
    @type user_cache_dir:     project-specific user cache directory
    @type user_cache_dir:     C{str}
    @ivar sys_data_dirs:      "system data directory" paths
    @type sys_data_dirs:      C{list} of C{str}

    @ivar data_dirs:          data files multi directory
    @type data_dirs:          L{MultiDirEntry}
    @ivar settings_dirs:      settings file multi directory
    @type settings_dirs:      L{MultiDirEntry}
    @ivar include_file_dirs:  feature set file multi directory
    @type include_file_dirs:  L{MultiDirEntry}
    @ivar conf_source_dirs:   config sources multi directory
    @type conf_source_dirs:   L{MultiDirEntry}
    @ivar cache_dirs:         project-specific cache directory
    @type cache_dirs:         L{MultiDirEntry}
    """

    CONFDIR_NAME = "kernelconfig"

    @classmethod
    def add_confdir_suffix(cls, dirpaths):
        """
        Suffixes each dir in dirpaths with "/" + project-specific confdir name.

        @param dirpaths:  directory paths
        @type  dirpaths:  C{list} of C{str}

        @return:  directory paths suffixed with ("/" + CONFDIR_NAME)
        @rtype:   C{list} of C{str}
        """
        return cls.add_dirsuffix(dirpaths, cls.CONFDIR_NAME)

    @abc.abstractclassmethod
    def new_instance(cls, sys_config_dir, sys_data_dir):
        """
        Derived classes should extend this method by calling
        super().new_instance(...) with appropriate
        sys_config_dir, sys_data_dir arguments.

        @param sys_config_dir:  path to the project-specific system config
                                directory
                                Can also be a list of directory paths,
                                or None if there are no such directories.
        @type  sys_config_dir:  C{str} or C{None} or C{list} of C{str}

        @param sys_data_dir:    path to the project-specific system data
                                directory
                                Can also be a list of directory paths,
                                or None if there are no such directories.
        @type  sys_data_dir:    C{str} or C{None} or C{list} of C{str}

        @return:  installation info object
        @rtype:   subclass of L{DefaultInstallInfo}
        """
        def to_dirlist(arg):
            if not arg:
                return None
            elif isinstance(arg, str):
                return [arg]
            else:
                return list(arg)
        # ---

        sys_config_dirs = to_dirlist(sys_config_dir)
        sys_data_dirs = to_dirlist(sys_data_dir)
        user_config_dir = cls.get_user_config_dir(cls.CONFDIR_NAME)
        user_cache_dir = cls.get_user_cache_dir(cls.CONFDIR_NAME)

        settings_dirs = multidir.MultiDirEntry()
        data_dirs = multidir.MultiDirEntry()
        cache_dirs = multidir.MultiDirEntry()

        if user_config_dir:
            settings_dirs.add_path(user_config_dir)
        # --

        if user_cache_dir:
            cache_dirs.add_path(user_cache_dir)
        # --

        if sys_config_dirs:
            settings_dirs.add_pathv(sys_config_dirs)
        # --

        if sys_data_dirs:
            data_dirs.add_pathv(sys_data_dirs)
        # --

        # initially, include_file_dirs is a copy of all paths
        # from settings_dirs suffixed with "/include"
        include_file_dirs = settings_dirs.get_child("include")

        # conf_source_dirs:
        # initially, "sources" subdir in any of the settings and data dirs
        conf_source_dirs = settings_dirs.get_child("sources")
        conf_source_dirs.append(data_dirs.get_child("sources"))

        return cls(
            sys_config_dirs=sys_config_dirs,
            user_config_dir=user_config_dir,
            user_cache_dir=user_cache_dir,
            sys_data_dirs=sys_data_dirs,
            settings_dirs=settings_dirs,
            include_file_dirs=include_file_dirs,
            conf_source_dirs=conf_source_dirs,
            cache_dirs=cache_dirs,
            data_dirs=data_dirs
        )
    # --- end of new_instance (...) ---

    def __init__(
        self, *,
        sys_config_dirs, user_config_dir, user_cache_dir, sys_data_dirs,
        settings_dirs, include_file_dirs, conf_source_dirs,
        cache_dirs, data_dirs
    ):
        super().__init__()
        self.sys_config_dirs = sys_config_dirs
        self.user_config_dir = user_config_dir
        self.user_cache_dir = user_cache_dir
        self.sys_data_dirs = sys_data_dirs

        self.settings_dirs = settings_dirs
        self.include_file_dirs = include_file_dirs
        self.conf_source_dirs = conf_source_dirs
        self.cache_dirs = cache_dirs
        self.data_dirs = data_dirs
    # --- end of __init__ (...) ---

    def copy(self):
        return self.__class__(
            sys_config_dirs=self.sys_config_dirs.copy(),
            user_config_dir=self.user_config_dir,
            user_cache_dir=self.user_cache_dir,
            sys_data_dirs=self.sys_data_dirs.copy(),
            settings_dirs=self.settings_dirs.copy(),
            include_file_dirs=self.include_file_dirs.copy(),
            conf_source_dirs=self.conf_source_dirs.copy(),
            cache_dirs=self.cache_dirs.copy(),
            data_dirs=self.data_dirs.copy()
        )
    # --- end of copy (...) ---

    def format_info(self):
        def gen_lines():
            indent = "  "

            for idx, (name, mdir) in enumerate([
                ("settings", self.settings_dirs),
                ("include", self.include_file_dirs),
                ("configuration sources", self.conf_source_dirs),
                ("cache", self.cache_dirs),
                ("data", self.data_dirs)
            ]):
                if idx:
                    yield ""

                yield "{0!s} directories:".format(name)
                have_any_dirpath = False
                for dirpath, stat_info in mdir.iter_paths():
                    have_any_dirpath = True
                    if not stat_info:
                        status_desc = "does not exist"
                    elif not stat.S_ISDIR(stat_info.st_mode):
                        status_desc = "not a dir"
                    else:
                        try:
                            ls_content = os.listdir(dirpath)
                        except OSError:
                            status_desc = "read error"
                        else:
                            status_desc = ("found" if ls_content else "empty")
                    # --

                    yield "{i}{0!s} ({1!s})".format(
                        dirpath, status_desc, i=indent
                    )
                # --

                if not have_any_dirpath:
                    yield "{i}(none)".format(i=indent)
            # --
        # ---

        return "\n".join(gen_lines())
    # --- end of format_info (...) ---

    def get_settings_file(self, filename):
        return self.settings_dirs.get_file_path(filename)

    def get_include_files(self, filename_pattern):
        return sorted((
            path for rel, path in self.include_file_dirs.iglob_check_type(
                filename_pattern
            )
        ))

    def get_config_source_dirs(self):
        return self.conf_source_dirs

    def get_script_file(self, filename):
        return self.data_dirs.get_file_path(
            fspath.join_relpath("scripts", filename)
        )

    def get_cache_dirs(self, name=None):
        if name:
            return self.cache_dirs.get_child(name, check_exist=False)
        else:
            return self.cache_dirs

    def get_cache_dir_path(self, name=None):
        return self.get_cache_dirs(name=name).get_path()

    def get_cache_search_dirs(
        self, name=None, data_name=None, *, check_exist=True
    ):
        """
        @return: new multidir object
        """
        search_dirs = multidir.MultiDirEntry()

        # cache_dirs: multidir entry
        if not self.cache_dirs:
            pass
        elif name:
            search_dirs.append(
                self.cache_dirs.get_child(name, check_exist=check_exist)
            )
        else:
            search_dirs.append(self.cache_dirs)

        # data_dirs: multidir entry
        #   data_name=None defaults to name
        if data_name is None:
            data_name = name

        if not self.data_dirs:
            pass
        elif data_name:
            search_dirs.append(
                self.data_dirs.get_child(data_name, check_exist=check_exist)
            )
        else:
            search_dirs.append(self.data_dirs)

        return search_dirs
    # --- end of get_cache_search_dirs (...) ---

# --- end of DefaultInstallInfo ---


class DefaultModuleInstallInfo(DefaultInstallInfo):

    @classmethod
    def new_instance(cls, py_module):
        return super().new_instance(
            sys_config_dir=py_module.sys_config_dir,
            sys_data_dir=py_module.sys_data_dir
        )
    # --- end of new_instance (...) ---

    @classmethod
    def check_pym_is_installinfo(self, py_module):
        return all((
            hasattr(py_module, attr_name)
            for attr_name in ("sys_config_dir", "sys_data_dir")
        ))
    # --- end of check_pym_is_installinfo (...) ---

# --- end of DefaultModuleInstallInfo (...) ---
