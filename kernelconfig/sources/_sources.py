# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import enum
import os.path
import shlex

from .abc import sources as _sources_abc
from .abc import exc
from . import source as _source
from . import sourcedef

from ._util import sourceenv


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

    def get_name(self):
        return self.name[2:]

    __str__ = get_name

# ---


class ConfigurationSourcesBase(_sources_abc.AbstractConfigurationSources):

    @abc.abstractproperty
    def SOURCE_TYPE_KEYWORDS(cls):
        raise NotImplementedError()

    def __init__(self, install_info, source_info, **kwargs):
        super().__init__(**kwargs)
        self.senv = sourceenv.ConfigurationSourcesEnv(
            logger=self.logger,  # ref
            install_info=install_info,
            source_info=source_info
        )

    def _create_source_by_name_from_files(
        self, source_name, source_def_file, source_script_file
    ):
        self.logger.debug("Initializing curated source %s", source_name)

        source_def = sourcedef.CuratedSourceDef.new_from_ini(
            conf_source_env=self.senv,
            name=source_name,
            parent_logger=self.logger,
            source_def_file=source_def_file
        )

        source_type_name = source_def.get("type", "").strip()
        if not source_type_name:
            # autodetect
            if source_script_file:
                source_type_name = "script"

            # failing that, pick the most appropriate exception type
            elif source_def_file:
                raise exc.ConfigurationSourceInvalidError(
                    "source {} with unknown type and no script file".format(
                        source_name
                    )
                )
            else:
                raise exc.ConfigurationSourceNotFound(source_name)
        # --

        # add "scriptfile" if not already in source_def (but possibly None)
        source_def.setdefault("scriptfile", source_script_file)

        source_type, source_subtype, source_cls = (
            self.get_source_type(source_type_name)
        )

        if source_type is ConfigurationSourceType.s_source:
            # type of source is source => error
            raise exc.ConfigurationSourceInvalidError(
                "{}: type of source must not be 'source'".format(source_name)
            )

        elif source_subtype:
            # couldfix - shouldfix
            raise exc.ConfigurationSourceInvalidError(
                "{}: subtypes are not supported: {}".format(
                    source_name, source_subtype
                )
            )

        elif source_type is None or source_cls is None:
            # if source_type is None, then the type has to be guessed
            #   however, this should have already been done
            #   ('if not source_def.get("type")'),
            #   so it indicates an error here
            #
            # if source_cls is None, then the type has no class and
            # it cannot be handled here.
            # (this should be an redundant case, since source_cls==None
            # implies a source_type of either None or "source")
            #
            raise exc.ConfigurationSourceInvalidError(
                "{}: could not detect source type".format(source_name)
            )
        # --

        self.logger.debug("%s is a %s source", source_name, source_type)
        return source_cls.new_from_def(
            name=source_name,
            conf_source_env=self.senv,
            source_def=source_def,
            parent_logger=self.logger
        )
    # --- end of _create_source_by_name_from_files (...) ---

    def create_source_by_name(self, source_name):
        self.logger.info("Trying to locate curated source %s", source_name)

        source_def_file = self.senv.get_source_definition_file(source_name)
        source_script_file = self.senv.get_source_script_file(source_name)

        if source_def_file or source_script_file:
            return self._create_source_by_name_from_files(
                source_name, source_def_file, source_script_file
            )
        else:
            self.logger.warning(
                "Could not locate curated source %s", source_name
            )

            # redundant,
            #  _create_source_by_name_from_files() would handle this, too
            raise exc.ConfigurationSourceNotFound(source_name)
    # --- end of create_source_by_name (...) ---

    def create_source_by_name_from_settings(self, subtype, args, data):
        if data:
            raise exc.ConfigurationSourceInvalidError(
                "curated source does not accept data"
            )
        # --

        if subtype is not None:
            source_name = subtype
            conf_args = args
        elif args:
            source_name = args[0]
            conf_args = args[1:]
        else:
            raise exc.ConfigurationSourceInvalidError(
                "missing curated source name"
            )
        # --

        conf_source = self.create_source_by_name(source_name)
        return (conf_source, conf_args)
    # ---

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
            source_type, source_subtype, source_cls = (
                self.get_source_type(source_def[0])
            )

            if source_type is None:
                # then the type is implicit, and we have to "guess":
                #
                # (a) is source_def[0] the name of a curated source?
                #
                # (b) is source_def[0] the name of a defconfig target?
                #
                # (c) file path of any type?
                #
                # TODO
                raise NotImplementedError("guess typeof", source_def)

            elif source_type is ConfigurationSourceType.s_source:
                # calling convention different from source_cls.new_from*
                return self.create_source_by_name_from_settings(
                    source_subtype, source_args, source_data
                )

            elif source_cls is None:
                raise NotImplementedError(
                    "missing source cls for type {}".format(source_type)
                )
        # --

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

    def get_source_type(self, source_type_name):
        slow = source_type_name.lower()

        try:
            source_type_entry = self.SOURCE_TYPE_KEYWORDS[slow]
        except KeyError:
            source_type_entry = (None, None)

        source_type, source_subtype = source_type_entry

        source_cls = None

        if source_type is None:
            assert source_subtype is None
            source_cls = None

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

        else:
            raise NotImplementedError(
                "unknown source type {}".format(source_type)
            )

        return (source_type, source_subtype, source_cls)
    # --- end of get_source_type (...) ---

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
