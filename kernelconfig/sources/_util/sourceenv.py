# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...abc import loggable
from ...util import fspath
from ...util import tmpdir


__all__ = ["ConfigurationSourcesEnv"]


class ConfigurationSourcesEnv(loggable.AbstractLoggable):
    def __init__(self, *, logger, install_info, source_info):
        super().__init__(logger=logger)
        self.install_info = install_info
        self.source_info = source_info
        self._files_dir = None
        self._tmpdir = None
        self._fmt_vars = None
        self._env_vars = None

    def get_files_dir(self):
        files_dir = self._files_dir
        if files_dir is None:
            files_dir = self.install_info.get_config_source_dirs()
            self._files_dir = files_dir
        return files_dir

    def get_file_path(self, name, *additional_relpath_components):
        return self.get_files_dir().get_file_path(
            fspath.join_relpaths_v(name, additional_relpath_components)
        )

    def get_config_file_path(self, name):
        return self.get_file_path("files", name)

    def get_source_definition_file(self, name):
        # FIXME: file name / suffix
        return self.get_file_path(name + ".def")

    def get_source_script_file(self, name):
        return self.get_file_path(name)

    def get_tmpdir(self):
        tmpdir_obj = self._tmpdir
        if tmpdir_obj is None:
            tmpdir_obj = tmpdir.Tmpdir()
            self._tmpdir = tmpdir_obj
        return tmpdir_obj

    def _create_base_vars(self):
        # FIXME: this is, at least partially,
        #        a dup of the interpreter's cmp vars
        #
        #        maybe add a get_base_vars() function to source_info?
        #
        base_vars = {}

        # at least in theory, source_info is just a SourceInfo
        # and not a KernelInfo object, so use hasattr() where appropriate
        source_info = self.source_info

        base_vars["srctree"] = source_info.srctree
        base_vars["s"] = source_info.srctree

        if hasattr(source_info, "kernelversion"):
            base_vars["kver"] = source_info.kernelversion
            base_vars["kmaj"] = source_info.kernelversion.version
            base_vars["kmin"] = source_info.kernelversion.sublevel
            base_vars["kpatch"] = source_info.kernelversion.patchlevel
            base_vars["kv"] = source_info.kernelversion.kv
        # --

        for attr_name in {"subarch", "arch", "karch", "srcarch"}:
            try:
                attr = getattr(source_info, attr_name)
            except AttributeError:
                pass
            else:
                base_vars[attr_name] = attr
        # --

        return base_vars
    # --- end of _create_base_vars (...) ---

    def _get_base_vars(self):
        # base vars do not get cached
        return self._create_base_vars()
    # --- end of _get_base_vars (...) ---

    def _create_format_vars(self):
        return {
            k: v
            for k, v in self._get_base_vars().items()
            if v is not None
        }
    # --- end of _create_format_vars (...) ---

    def get_format_vars(self):
        fmt_vars = self._fmt_vars
        if fmt_vars is None:
            fmt_vars = self._create_format_vars()
            self._fmt_vars = fmt_vars
        return fmt_vars
    # --- end of get_format_vars (...) ---

    def _create_env_vars(self):
        # keep None and non-str values, see subproc.merge_env_dicts_add_item()
        return {
            k.upper(): v
            for k, v in self._get_base_vars().items()
        }
    # --- end of _create_env_vars (...) ---

    def get_env_vars(self):
        env_vars = self._env_vars
        if env_vars is None:
            env_vars = self._create_env_vars()
            self._env_vars = env_vars
        return env_vars
    # --- end of get_env_vars (...) ---

# ---
