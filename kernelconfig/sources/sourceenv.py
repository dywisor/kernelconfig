# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import re
import stat

from ..abc import informed
from ..util import fspath
from ..util import tmpdir

from ._util import _format


__all__ = ["ConfigurationSourcesEnv", "SourceDefFiles"]


SourceDefFiles = collections.namedtuple(
    "SourceDefFiles", "def_file script_file"
)


class ConfigurationSourcesEnv(informed.AbstractInformed):
    """
    Configuration sources environment that is shared between
    the ConfigurationSources container  and all configuration source objects.

    It provides some basic information, e.g. where to find source def files,
    and centralizes some core functionality such as the temporary (root) dir,
    the static string formatter and environment variables for subprocesses.

    @cvar SOURCE_DEF_FILE_SUFFIX:  source definition file name suffix,
                                   including a leading dot char ".".
                                   Should be treated read-only.
    @type SOURCE_DEF_FILE_SUFFIX:  C{str}

    @cvar SOURCE_DEF_FILE_NAME:    regular expression for matching
                                   source definition file paths or names
                                   and extracting information such as
                                   the source's name
                                   (name, dirname, basename, suffix)
                                   Should be treated read-only,
                                   includes the regexp compile-time value
                                   of SOURCE_DEF_FILE_SUFFIX.
    @type SOURCE_DEF_FILE_NAME:    compiled regexp

    @ivar source_info:
    @ivar install_info:

    @ivar _tmpdir:    shared tmpdir, config sources should request
                      a subdirectory with get_tmpdir().get_new_subdir()
                      or individual files with get_tmpdir().open_new_file()
    @type _tmpdir:    L{TmpdirView}

    @ivar _fmt_vars:  shared 'static' format variables (e.g. "arch"),
                      can be accessed with get_format_vars()
                      all keys must be lowercase strings,
                      referencing these vars is case insensitive
                      when get_str_formatter() is used
                      lazy-init, initially None.
    @type _fmt_vars:  C{dict} :: C{str} => C{object}

    @ivar _env_vars:  shared 'static' environment variables (e.g. "ARCH"),
                      can be accessed with get_env_vars()
                      all keys are uppercase,
                      but mixed- and lowercase keys may be added.
                      lazy-init, initially None.
    @type _env_vars:  C{dict} :: C{str} => C{str}|C{None}
    """

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
        super().__init__(
            logger=logger, install_info=install_info, source_info=source_info
        )
        self._tmpdir = None
        self._fmt_vars = None
        self._env_vars = None

    def get_files_dir(self):
        """
        Returns a multi directory view of all directories where
        config sources are stored (/might be stored/).

        @return:  config source directories, as multi dir
        @rtype:   subclass of L{MultiDirEntryBase}
        """
        return self.install_info.get_config_source_dirs()

    def get_filepath(self, name, *additional_relpath_components):
        """
        Returns the first-matching path to the requested file,
        found in any of the config source directories.

        @param name:  name of the file
                      when additional_relpath_components is also given,
                      first directory relpath element
        @type  name:  C{str}

        @param additional_relpath_components:  var-args list of additional
                                               path components, last element
                                               is the file's name
        @type  additional_relpath_components:  var-args C{list} of C{str}

        @return:  path to existing file or None
        @rtype:   C{str} or C{None}
        """
        return self.get_files_dir().get_filepath(
            fspath.join_relpaths_v(name, additional_relpath_components)
        )

    def get_config_file_path(self, name):
        """
        Returns the first-matching path to the requested .config file,
        found in the "files" subdir of any of the config source directories.

        @param name:  name of the .config file
        @type  name:  C{str}

        @return:  path to existing file or None
        @rtype:   C{str} or C{None}
        """
        return self.get_filepath("files", name)

    def get_source_def_files(self, name):
        """
        Returns the a tuple of first-matching source def, source script files,
        found in any of the config source directories.

        The lookup is performed individually (per file),
        allowing to find the files in separate directories
        (e.g. source def in /etc, script in ~/.config).

        @param name:  name of the curated source,
                      will be converted to lowercase before searching for files
        @type  name:  C{str}

        @return: 2-tuple of path to existing file or None
                 (source def file, source script file)
        @rtype:  2-tuple of C{str}|C{None}
        """
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
        """
        Searches in the config source directories
        for possible configuration sources.

        At this point it is unknown whether the found config sources
        would actually load and be supported.

        @keyword refresh:  whether to refresh the search directories'
                           scandir cache before searching.
                           Defaults to None.
        @type    refresh:  C{bool}

        @return:  source def files info,
                  named 2-tuple(s) (def_file, script_file).
                  Items may be None, but at least one item is set.
        @rtype:   L{SourceDefFiles},
                  a named 2-tuple (C{str}|C{None}, C{str}|C{None})
        """
        def entry_is_reg_file(entry, *, _isreg=stat.S_ISREG):
            return entry.stat_info and _isreg(entry.stat_info.st_mode)
        # ---

        # Create a list of first-matching fs entries found in any of
        # config source directory.
        # Each entry is a named 2-tuple (path, stat info).
        # entries :: name => EntryInfo
        entries = self.get_files_dir().scandir_flatten(refresh=refresh)

        # entry_names_processed keeps track of which entry names have already
        # been processed, to avoid modifying entries during iteration
        entry_names_processed = set()

        # loop over all names that could be source definition files,
        # process accompanying script files
        #  (match <name>.def, process <name>.def, <name>)
        #
        for match in filter(
            None,
            map(self.SOURCE_DEF_FILE_NAME.match, entries)
        ):
            def_entry = entries[match.string]

            # one way or another, this .def entry is about to be processed
            entry_names_processed.add(match.string)

            # if stat info available and is a file
            if entry_is_reg_file(def_entry):
                # then entry is a source def file

                name = match.group("name")

                # is there also a script for the .def entry?
                # initially, no
                script_path = None
                # but take a peek at entries
                if name in entries:
                    # then it is processed here
                    #  note that if def_entry is not a file (e.g. a dir),
                    #  "name" can still be a def-less script source
                    script_entry = entries[name]
                    entry_names_processed.add(name)

                    # script must be a file,
                    # but does not have to be executable
                    if entry_is_reg_file(script_entry):
                        script_path = script_entry.path
                # --

                yield (name, SourceDefFiles(def_entry.path, script_path))
            # -- end if
        # -- end for

        # drop processed names from entries
        for key in entry_names_processed:
            del entries[key]

        # loop over the remaining entries, they may be script-only sources
        for name, script_entry in entries.items():
            if entry_is_reg_file(script_entry):
                # could check for executability here
                yield (name, SourceDefFiles(None, script_entry.path))
    # --- end of iter_available_sources_info (...) ---

    def get_tmpdir(self):
        """Returns the shared tmpdir.

        Configuration sources should request private subdirectories
        with <tmpdir>.get_new_subdir(),
        or private files with <tmpdir>.open_new_file().

        @return:  shared tmpdir
        @rtype:   L{TmpdirView}
        """
        tmpdir_obj = self._tmpdir
        if tmpdir_obj is None:
            tmpdir_obj = tmpdir.Tmpdir()
            self._tmpdir = tmpdir_obj
        return tmpdir_obj

    def _create_base_vars(self):
        """
        Creates the dict of "base" variables that will be available
        in both the format and the subprocess environment variables dicts.

        @return:  new dict of base vars
        @rtype:   C{dict} :: C{str} => C{object}
        """
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
        """
        Returns the dict of "base" vars.

        This may or may not involve creation of a new dict,
        the returned dict should be copied before doing any modifications.

        @return:  shared dict of base vars
        @rtype:   C{dict} :: C{str} => C{object}
        """
        # base vars do not get cached
        return self._create_base_vars()
    # --- end of _get_base_vars (...) ---

    def _create_format_vars(self):
        """
        Creates the dict of "str-format" variables.

        @return:  new dict of format vars
        @rtype:   C{dict} :: C{str} => C{object}
        """
        return {
            k: v
            for k, v in self._get_base_vars().items()
            if v is not None
        }
    # --- end of _create_format_vars (...) ---

    def get_format_vars(self):
        """
        Returns the dict of "str-format" vars.

        This may or may not involve creation of a new dict,
        the returned dict should be copied before doing any modifications.

        @return:  shared dict of format vars
        @rtype:   C{dict} :: C{str} => C{object}
        """
        fmt_vars = self._fmt_vars
        if fmt_vars is None:
            fmt_vars = self._create_format_vars()
            self._fmt_vars = fmt_vars
        return fmt_vars
    # --- end of get_format_vars (...) ---

    def get_str_formatter(self):
        """Returns a new str formatter that uses the "str-format" vars.

        @return:  new str formatter
        @rtype:   L{ConfigurationSourceStrFormatter}
        """
        return _format.ConfigurationSourceStrFormatter(self)

    def _create_env_vars(self):
        """
        Creates the dict of "subprocess environment" variables.

        @return:  new dict of subprocess env vars
        @rtype:   C{dict} :: C{str} => C{str}|C{None}
        """
        # keep None and non-str values, see subproc.merge_env_dicts_add_item()
        return {
            k.upper(): v
            for k, v in self._get_base_vars().items()
        }
    # --- end of _create_env_vars (...) ---

    def get_env_vars(self):
        """
        Returns the dict of "subprocess environment" vars.

        This may or may not involve creation of a new dict,
        the returned dict should be copied before doing any modifications.

        @return:  shared dict of subprocess env vars
        @rtype:   C{dict} :: C{str} => C{str}|C{None}
        """
        env_vars = self._env_vars
        if env_vars is None:
            env_vars = self._create_env_vars()
            self._env_vars = env_vars
        return env_vars
    # --- end of get_env_vars (...) ---

# ---
