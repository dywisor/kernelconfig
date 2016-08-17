# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os.path
import shlex

from .abc import sources as _sources_abc
from .abc import exc
from . import sourcedef
from . import sourcetype
from . import sourceenv


__all__ = ["ConfigurationSources"]


class ConfigurationSources(_sources_abc.AbstractConfigurationSources):
    """
    A collection of configuration sources.

    From the configuration sources container perspective,
    a configuration source has two (three) states:

    * loaded      -- configuration source has been loaded
                     (or, conf source object has been registered
                     with register_source())
    * available   -- configuration could be loaded
                     The necessary information (i.e. files) exists, but it
                     is unknown whether the source would load successfully
                     and whether it is supported (e.g. target architecture)
    * unavailable -- configuration source does exist

    Initially, no conf sources are loaded, but this class
    has enough information to create 'available' sources on demand.

    See also abc.sources.AbstractConfigurationSources.

    @ivar senv:  configuration source environment,
                 shared with all configuration sources
    @type senv:  L{ConfigurationSourcesEnv}
    """

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

    def _create_curated_source_def_by_name_from_files(
        self, source_key, source_def_file, source_script_file
    ):
        """
        This method should only be used by _create_source_by_name_from_files().
        It creates the source definition data from def_file/script_file
        and returns a 2-tuple (source def data, source type descriptor).

        At least one of source_def_file, source_script_file must be set
        to a not-None value. All not-None files should exist.

        @raises ConfigurationSourceNotFound:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceMissingType:
        @raises ConfigurationSourceError:

        @param source_key:          normalized source name
                                    (get_source_name_key())
        @param source_def_file:     source definition file or None
        @param source_script_file:  source script file or None

        @return:  2-tuple (def data, source type descriptor)
        @rtype:   2-tuple (L{CuratedSourceDef}, L{ConfigurationSourceType})
        """
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
        """
        This method should only be used by create_source_by_name().
        It loads the source definition data
        (see _create_curated_source_def_by_name_from_files()),
        and creates a configuration source object.

        At least one of source_def_file, source_script_file must be set
        to a not-None value. All not-None files should exist.

        @raises ConfigurationSourceNotFound:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceMissingType:
        @raises ConfigurationSourceError:

        @param source_key:          normalized source name
                                    (get_source_name_key())
        @param source_def_file:     source definition file or None
        @param source_script_file:  source script file or None

        @return:  configuration source object
        @rtype:   subclass of L{AbstractConfigurationSource}
        """
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

    def _get_curated_source_from_settings(self, subtype, args, data):
        """
        Condition: subtype||args -- subtype and args cannot be both empty

        @param subtype:  either None or name of the config source
        @param args:     mixed init_from_def(), get_configuration_basis() args
                         If subtype is empty, the first arg is used as
                         name of the curated source
        @param data:     data for init_from_def()
                         Note that sources-from-def usually do not accept data

        @return:  2-tuple (configuration source object, args remainder)
        @rtype:   2-tuple (L{AbstractConfigurationSource}, C{list} of C{str})
        """
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
        """Returns a configuration source.
        Its name and related information is read from the [source] section
        of the given pre-parsed settings file.

        Already loaded sources are considered,
        and newly created sources may be added to this container.
        ("curated sources" are added, but "settings-only" sources are not.)

        @param settings:  pre-parsed settings file
        @type  settings:  L{SettingsFileReader}
                          or C{dict} :: C{str} => C{list} of C{str}

        @return:  2-tuple (configuration source object, args)
                  or 2-tuple (True, None) if no source configured
        """
        def read_settings():
            """
            @return:  2-tuple (source definition line, source data)
            @rtype:   2-tuple (C{str}, C{list} of C{str})
            """
            # format of the settings file, [source] section:
            #
            #   [source]
            #   [<type>] <arg> [<arg>...]
            #   [<data line 1>]
            #   ...
            #   [<data line N>]
            #
            # * comment lines are ignored
            # * the first line may span over multiple lines,
            #   separated with a backslash char (line cont.)
            #
            # So basically, the non-comment, non-empty first line is the
            # "source definition" line, and all remaining lines are "data".
            #
            source_def = []

            data_gen = settings.iter_section("source", skip_comments=True)

            # handle backslash line continuation
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
            return self._get_curated_source_from_settings(
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

# --- end of ConfigurationSources ---
