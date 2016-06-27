# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import enum
import functools
import os.path
import shlex

from ..abc import loggable
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
        self._tmpdir = None

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

    def get_configuration_basis_from_settings(self, settings):
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

        # fixme: file uri
        if os.path.isabs(source_def[0]):
            # implicit file
            return self.get_configuration_basis_from_file(
                None, source_def, source_data
            )
        # --

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
            return self.get_configuration_basis_from_file(
                source_subtype, source_def[1:], source_data
            )

        elif source_type is ConfigurationSourceType.s_command:
            return self.get_configuration_basis_from_command(
                source_subtype, source_def[1:], source_data
            )

        elif source_type is ConfigurationSourceType.s_make:
            # make command w/ target source_subtype
            return self.get_configuration_basis_from_make(
                source_subtype, source_def[1:], source_data
            )

        elif source_type is ConfigurationSourceType.s_source:
            return self.get_configuration_basis_from_source(
                source_subtype, source_def[1:], source_data
            )

        elif source_type is ConfigurationSourceType.s_script:
            # embedded script w/ lang source_subtype
            return self.get_configuration_basis_from_script(
                source_subtype, source_def[1:], source_data
            )

        else:
            raise NotImplementedError(
                "unknown source type {}".format(source_type)
            )
    # --- end of get_configuration_basis_from_settings (...) ---

    @abc.abstractmethod
    def get_configuration_basis_from_file(self, subtype, args, data):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_configuration_basis_from_command(self, subtype, args, data):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_configuration_basis_from_make(self, subtype, args, data):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_configuration_basis_from_source(self, subtype, args, data):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_configuration_basis_from_script(self, subtype, args, data):
        raise NotImplementedError()

# --- end of ConfigurationSourcesBase ---


def _meth_no_subtype(unbound_method):
    def wrapper(self, subtype, args, data):
        if subtype is not None:
            raise ValueError("methpd does not accept a subtype")
        return unbound_method(self, subtype, args, data)

    return functools.update_wrapper(wrapper, unbound_method)
# ---


def _meth_no_data(unbound_method):
    def wrapper(self, subtype, args, data):
        if data:
            raise ValueError("methpd does not accept data")
        return unbound_method(self, subtype, args, data)

    return functools.update_wrapper(wrapper, unbound_method)
# ---


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

    def create_source_by_name(self, source_name):
        raise NotImplementedError("curated sources")

    @_meth_no_data
    @_meth_no_subtype
    def get_configuration_basis_from_file(self, subtype, args, data):
        # FIXME:  file may be a relpath (-> installinfo//multdir)
        #         or a remote path (-> urllib)
        #         Use a FileConfigurationSource object
        return args[0]

    @_meth_no_data
    @_meth_no_subtype
    def get_configuration_basis_from_command(self, subtype, args, data):
        raise NotImplementedError()

    @_meth_no_data
    def get_configuration_basis_from_make(self, subtype, args, data):
        src = self.create_loggable(
            _source.MakeConfigurationSource,
            None
        )
        return src.get_configuration_basis(self.senv, subtype, args)
    # ---

    @_meth_no_data
    @_meth_no_subtype
    def get_configuration_basis_from_source(self, subtype, args, data):
        raise NotImplementedError()

    def get_configuration_basis_from_script(self, subtype, args, data):
        raise NotImplementedError()
