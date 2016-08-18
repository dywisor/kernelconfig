# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import re
import stat

from ..abc import loggable
from ..util import fspath
from ..util import tmpdir

from ._util import _format


__all__ = ["ConfigurationSourcesEnv"]


SourceDefFiles = collections.namedtuple(
    "SourceDefFiles", "def_file script_file"
)


class ConfigurationSourcesEnv(loggable.AbstractLoggable):

    SOURCE_DEF_FILE_SUFFIX = ".def"
    SOURCE_DEF_FILE_NAME = re.compile(
        (
            r'^(?:'
            r'(?P<name>(?P<dirname>.*[/])?(?P<basename>[^/]+))'
            r'(?P<suffix>{suffix})'
            r')$'
        ).format(suffix=SOURCE_DEF_FILE_SUFFIX)
    )

    def __init__(self, *, logger, install_info, source_info):
        super().__init__(logger=logger)
        self.install_info = install_info
        self.source_info = source_info
        self._tmpdir = None
        self._fmt_vars = None
        self._env_vars = None

    def get_files_dir(self):
        return self.install_info.get_config_source_dirs()

    def get_filepath(self, name, *additional_relpath_components):
        return self.get_files_dir().get_filepath(
            fspath.join_relpaths_v(name, additional_relpath_components)
        )

    def get_config_file_path(self, name):
        return self.get_filepath("files", name)

    def get_source_def_files(self, name):
        sname = name.lower()
        if sname.endswith(self.SOURCE_DEF_FILE_SUFFIX):
            raise ValueError(name)

        files_dir = self.get_files_dir()
        return SourceDefFiles(
            files_dir.get_filepath(sname + self.SOURCE_DEF_FILE_SUFFIX),
            files_dir.get_filepath(sname)
        )
    # --- end of get_source_def_files (...) ---

    def iter_available_sources_info(self, refresh=False):
        null_entry = (None, None)

        def entry_is_reg_file(entry, *, _isreg=stat.S_ISREG):
            return entry[1] and _isreg(entry[1].st_mode)
        # ---

        # entries :: name => entry object
        entries = self.get_files_dir().scandir_flatten(refresh=refresh)

        keys_to_del = set()
        for match in filter(
            None,
            map(self.SOURCE_DEF_FILE_NAME.match, entries)
        ):
            def_entry = entries[match.string]

            # one way or another, this .def entry about to be processed
            keys_to_del.add(match.string)

            # if stat info available and is a file
            if entry_is_reg_file(def_entry):
                # then entry is a source def file

                name = match.group("name")

                # is there also a script for the .def entry?
                if name in entries:
                    # then it is processed here
                    #  note that if def_entry is not a file (e.g. a dir),
                    #  "name" can still be a def-less script source
                    script_entry = entries[name]
                    keys_to_del.add(name)
                else:
                    script_entry = null_entry

                yield (
                    name,
                    SourceDefFiles(
                        def_entry[0],
                        (
                            script_entry[0] if entry_is_reg_file(script_entry)
                            else None
                        )
                    )
                )
            # -- end if
        # -- end for

        for key in keys_to_del:
            del entries[key]

        for name, script_entry in entries.items():
            if entry_is_reg_file(script_entry):
                # could check for executability here
                yield (name, SourceDefFiles(None, script_entry[0]))
    # --- end of iter_available_sources_info (...) ---

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

    def get_str_formatter(self):
        return _format.ConfigurationSourceStrFormatter(self)

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
