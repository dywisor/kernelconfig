# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os.path
import shlex
import sys

from .abc import sources as _sources_abc
from .abc import exc
from . import sourcedef
from . import sourcetype
from . import sourceenv


__all__ = ["ConfigurationSources"]


class ConfigurationSources(_sources_abc.AbstractConfigurationSources):

    def __init__(self, install_info, source_info, **kwargs):
        super().__init__(**kwargs)
        self.senv = sourceenv.ConfigurationSourcesEnv(
            logger=self.logger,  # ref
            install_info=install_info,
            source_info=source_info
        )

    def iter_available_sources_info(self):
        # fs lookup is done sources env, dispatch
        return self.senv.iter_available_sources_info()

    def load_source(self, source_name):
        # FIXME: missing in abc
        try:
            source = self.get_source(source_name)

        except exc.ConfigurationSourceNotFound:
            return (None, None)

        except exc.ConfigurationSourceError:
            return (None, sys.exc_info())

        else:
            return (source, None)
    # ---

    def load_available_sources(self):
        sources_loaded = []
        sources_failed = {}

        for source_name, source_info in self.iter_available_sources_info():
            #  source_info discarded
            source, source_exc_info = self.load_source(source_name)

            if source_exc_info is not None:
                assert source_name not in sources_failed
                sources_failed[source_name] = source_exc_info

            elif source is None:
                # false positive
                pass

            else:
                sources_loaded.append(source.name)
        # --

        return (sources_loaded, sources_failed)
    # --- end of load_available_sources (...) ---

    def _create_curated_source_def_by_name_from_files(
        self, source_key, source_def_file, source_script_file
    ):
        self.logger.debug("Initializing curated source %s", source_key)

        source_def = sourcedef.CuratedSourceDef.new_from_ini(
            conf_source_env=self.senv,
            name=source_key,
            parent_logger=self.logger,
            source_def_file=source_def_file,
            source_script_file=source_script_file
        )

        try:
            source_type = source_def.get_source_type()

        except exc.ConfigurationSourceMissingType:
            # failed to detect source type
            if source_def_file:
                # raising same, but new exception? FIXME
                raise exc.ConfigurationSourceMissingType(
                    "source {} has unknown type".format(source_key)
                ) from None
            else:
                raise exc.ConfigurationSourceNotFound(source_key) from None

        except KeyError:
            # if there is no source type matching source_type_name,
            #   then the type has to be guessed
            #   however, this should have already been done
            #   ('if not source_def.get("type")'),
            #   so it indicates an error here
            #
            raise exc.ConfigurationSourceInvalidError(
                "{}: could not detect source type".format(source_key)
            ) from None
        # --

        if source_type.is_source():
            # type of source is source => error
            raise exc.ConfigurationSourceInvalidError(
                "{}: type of source must not be 'source'".format(source_key)
            )

        elif source_type.source_subtype:
            # couldfix - shouldfix
            raise exc.ConfigurationSourceInvalidError(
                "{}: subtypes are not supported: {}".format(
                    source_key, source_type.source_subtype
                )
            )

        elif source_type.source_cls is None:
            # if source_cls is None, then the type has no class and
            # it cannot be handled here.
            # (this should be an redundant case, since source_cls==None
            # implies a no source_type or a "source" source_type)
            #
            raise exc.ConfigurationSourceInvalidError(
                "{}: has no source type class".format(source_key)
            )
        # --

        self.logger.debug("%s is a %s source", source_key, source_type)

        return (source_def, source_type)
    # --- end of _create_curated_source_def_by_name_from_files (...) ---

    def _create_source_by_name_from_files(
        self, source_key, source_def_file, source_script_file
    ):
        source_def, source_type = (
            self._create_curated_source_def_by_name_from_files(
                source_key, source_def_file, source_script_file
            )
        )

        if not source_def.arch:
            # Debatable if this is an init-time or
            # a get_configuration_basis()-time error.
            #
            # It makes no difference where the error is raised, and there is
            # simply no point in creating unusable source objects,
            # so fail early.
            raise exc.ConfigurationSourceArchNotSupported(
                source_key,
                archs=(
                    name for _, name
                    in self.senv.source_info.iter_target_arch_dedup()
                ),
                supported_archs=source_def.get("architectures")
            )

        # --

        return source_type.source_cls.new_from_def(
            name=source_key,
            conf_source_env=self.senv,
            source_def=source_def,
            parent_logger=self.logger
        )
    # --- end of _create_source_by_name_from_files (...) ---

    def create_source_by_name(self, source_name):
        source_key = self.get_source_name_key(source_name)
        self.logger.info("Trying to locate curated source %s", source_key)

        sfiles = self.senv.get_source_def_files(source_key)
        if any(sfiles):
            return self._create_source_by_name_from_files(
                source_key, sfiles.def_file, sfiles.script_file
            )
        else:
            self.logger.warning(
                "Could not locate curated source %s", source_key
            )

            # redundant,
            #  _create_source_by_name_from_files() would handle this, too
            raise exc.ConfigurationSourceNotFound(source_key)
    # --- end of create_source_by_name (...) ---

    def get_source_from_settings(self, subtype, args, data):
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

        conf_source = self.get_source(source_name)
        return (conf_source, conf_args)
    # ---

    def get_configuration_source_from_settings(self, settings):
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

        source_type = None  # set below
        source_args = None
        # source_data is already set

        if os.path.isabs(source_def[0]):
            # implicit file
            source_type = sourcetype.get_source_type("local_file")
            source_args = source_def

        else:
            source_args = source_def[1:]
            try:
                source_type = sourcetype.get_source_type(source_def[0])
            except KeyError:
                source_type = None

            if source_type is None:
                self.logger.debug(
                    "Trying to guess type of %s", source_def[0]
                )

                # then the type is implicit, and we have to "guess":
                #
                # (a) is source_def[0] the name of a curated source?
                source_key = self.get_source_name_key(source_def[0])
                if source_key in self:
                    # (a1) ... that is maybe already loaded?
                    is_curated_source = True

                else:
                    # (a2) ... for which def/script files can be found?
                    try:
                        sfiles = self.senv.get_source_def_files(source_key)
                    except ValueError:
                        is_curated_source = False
                    else:
                        is_curated_source = any(sfiles)
                # --

                if is_curated_source:
                    self.logger.debug("%s is a curated source", source_def[0])

                    # could return directly from
                    # _create_source_by_name_from_files(...) here,
                    # but that requires duplicated checks (source_data)
                    source_type = sourcetype.get_source_type("source")
                    source_args = source_def

                else:
                    # (b) file path of any type?
                    #  note that relative paths are not supported here
                    #  unless they begin with file://,
                    #  and absolute paths starting with "/" have already
                    #  been handled
                    scheme, scheme_sep, rem = source_def[0].partition("://")

                    if scheme_sep:
                        self.logger.debug("%s is a file source", source_def[0])
                        source_type = sourcetype.get_source_type("file")
                        source_args = source_def
                # -- end if try detect

                if source_type is None:
                    # then guessing was not successful
                    self.logger.warning(
                        "could not guess source type of %s", source_def[0]
                    )
                    raise exc.ConfigurationSourceNotFound(source_def[0])
            # -- end if source_type is None
        # --

        if source_type.is_source():
            # calling convention different from source_cls.new_from*
            #
            # Note that already loaded sources will be re-used here,
            # possibly ignoring the file search results from the
            # guess-type block above.
            #
            return self.get_source_from_settings(
                source_type.source_subtype, source_args, source_data
            )

        elif source_type.source_type is None:
            raise NotImplementedError(
                "missing source cls for type {}".format(source_type)
            )
        else:
            return source_type.source_cls.new_from_settings(
                conf_source_env=self.senv,
                subtype=source_type.source_subtype,
                args=source_args, data=source_data,
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
