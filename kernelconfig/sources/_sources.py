# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import enum
import os.path
import shlex

from ..abc import loggable
from ..util import fspath
from ..util import tmpdir

from .abc import sources as _sources_abc
from . import source as _source


__all__ = ["ConfigurationSourceType", "ConfigurationSources"]


@enum.unique
class ConfigurationSourceType(enum.IntEnum):
    (
        s_unknown,
        s_file,
        s_command,
        s_make,
        s_script,
        s_source
    ) = range(6)
# ---


class ConfigurationSourcesEnv(loggable.AbstractLoggable):
    def __init__(self, *, logger, install_info, source_info):
        super().__init__(logger=logger)
        self.install_info = install_info
        self.source_info = source_info
        self._files_dir = None
        self._tmpdir = None

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

    def get_tmpdir(self):
        tmpdir_obj = self._tmpdir
        if tmpdir_obj is None:
            tmpdir_obj = tmpdir.Tmpdir()
            self._tmpdir = tmpdir_obj
        return tmpdir_obj
# ---


class ConfigurationSourcesBase(_sources_abc.AbstractConfigurationSources):

    @abc.abstractproperty
    def SOURCE_TYPE_KEYWORDS(cls):
        raise NotImplementedError()

    def __init__(self, install_info, source_info, **kwargs):
        super().__init__(**kwargs)
        self.senv = ConfigurationSourcesEnv(
            logger=self.logger,  # ref
            install_info=install_info,
            source_info=source_info
        )

    def create_source_by_name(self, source_name):
        raise NotImplementedError("curated sources")

    def get_configuration_source_from_settings(self, settings):
        def join_subtype_and_args(subtype, args):
            return args if subtype is None else ([subtype] + args)
        # ---

        def read_settings():
            source_def = []

            data_gen = settings.iter_section("source", skip_comments=True)

            for line in data_gen:
                assert line
                if line[-1] == "\\":
                    source_def.append(line[:-1].strip())
                else:
                    source_def.append(line.strip())
                    break
            # --

            source_data = list(data_gen)

            return (" ".join(source_def), source_data)
        # ---

        source_def_str, source_data = read_settings()
        if not source_def_str:
            assert not source_data
            return self.senv.source_info.get_filepath(".config")

        source_def = shlex.split(source_def_str)

        source_cls = None
        source_args = None
        # source_data is already set
        source_subtype = None

        # fixme: file uri
        if os.path.isabs(source_def[0]):
            # implicit file
            source_cls = _source.LocalFileConfigurationSource
            source_args = source_def

        else:
            source_args = source_def[1:]

            source_type_name = source_def[0].lower()
            source_type, source_subtype = (
                self.SOURCE_TYPE_KEYWORDS.get(source_type_name)
            )

            if source_type is None:
                assert source_subtype is None
                # then the type is implicit, and we have to "guess":
                #
                # (a) is source_def[0] the name of a curated source?
                #
                # (b) is source_def[0] the name of a defconfig target?
                #
                # (c) file path of any type?
                #
                raise NotImplementedError("guess typeof", source_def)

            elif source_type is ConfigurationSourceType.s_file:
                source_cls = _source.FileConfigurationSource

            elif source_type is ConfigurationSourceType.s_command:
                source_cls = _source.CommandConfigurationSource

            elif source_type is ConfigurationSourceType.s_make:
                # make command w/ target source_subtype
                source_cls = _source.MakeConfigurationSource

            elif source_type is ConfigurationSourceType.s_source:
                source_cls = None

            elif source_type is ConfigurationSourceType.s_script:
                # embedded script w/ lang source_subtype
                source_cls = _source.ScriptConfigurationSource
            # --
        # --

        if source_cls is None:
            raise NotImplementedError(
                "unknown source type {}".format(source_type)
            )

        return source_cls.new_from_settings(
            conf_source_env=self.senv,
            subtype=source_subtype, args=source_args, data=source_data,
            parent_logger=self.logger
        )
    # --- end of get_configuration_source_from_settings (...) ---

    def get_configuration_basis_from_settings(self, settings):
        conf_source, conf_args = (
            self.get_configuration_source_from_settings(settings)
        )

        return conf_source.get_configuration_basis(conf_args)
    # --- end of get_configuration_basis_from_settings (...) ---

# --- end of ConfigurationSourcesBase ---


class ConfigurationSources(ConfigurationSourcesBase):

    SOURCE_TYPE_KEYWORDS = {
        "file":         (ConfigurationSourceType.s_file, None),

        "cmd":          (ConfigurationSourceType.s_command, None),
        "command":      (ConfigurationSourceType.s_command, None),

        "mk":           (ConfigurationSourceType.s_make, None),
        "make":         (ConfigurationSourceType.s_make, None),
        "defconfig":    (ConfigurationSourceType.s_make, "defconfig"),

        "script":       (ConfigurationSourceType.s_script, None),
        "sh":           (ConfigurationSourceType.s_script, "sh"),

        "source":       (ConfigurationSourceType.s_source, None)
    }
