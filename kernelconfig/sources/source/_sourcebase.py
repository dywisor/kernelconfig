# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os
import re
import subprocess

from ..abc import source as _source_abc
from ..abc import exc

from ...util import subproc
from ...util import fs

from .._util import _argconfig
from .._util import _format
from .._util import _formatvar


__all__ = [
    "ConfigurationSourceBase",
    "PhasedConfigurationSourceBase",
    "CommandConfigurationSourceBase",
]


class ConfigurationSourceBase(_source_abc.AbstractConfigurationSource):
    """
    Base class for configuration sources.
    Compared to AbstractConfigurationSource,
    it defines how to create configuration sources
    and adds more concrete functionality such as str formatting,
    arg parsing and automatic temporary files/directories.

    @cvar AUTO_OUTCONFIG_REGEXP:

    @cvar AUTO_TMPFILE_REGEXP:

    @cvar AUTO_TMPDIR_REGEXP:

    @ivar senv:  shared configuration source environment
    @type senv:  L{ConfigurationSourcesEnv}

    @ivar _str_formatter:  'static' str formatter
    @type _str_formatter:  L{ConfigurationSourceStrFormatter}

    @ivar fmt_vars:        'static' format variables
                           The attribute itself is readonly,
                           but its content can be modified (e.g. adding vars).
    @type fmt_vars:        C{dict} :: C{str} => C{str}

    @ivar auto_outconfig:  mapping of "outconfig" auto format vars,
                           initially None, see add_auto_var_outconfig()
    @type auto_outconfig:  C{None} or C{dict} :: C{str} => L{TmpOutfile}

    @ivar auto_tmpfiles:   mapping of "outfile" auto format vars,
                           initially None, see add_auto_var_tmpfile()
    @type auto_tmpfiles:   C{None} or C{dict} :: C{str} => L{TmpOutfile}

    @ivar auto_tmpdirs:    mapping of "tmpdir" auto format vars,
                           initially None, see add_auto_var_tmpdir()
    @type auto_tmpdirs:    C{None} or C{dict} :: C{str} => undef

    @ivar arg_parser:      argument parser used for parsing args
                           passed to get_configuration_basis()
                           (see do_parse_source_argv()),
                           and also used for creating the source's help message
    @type arg_parser:      C{None} or NonExitingArgumentParser
    """

    _id_expr = r'(?P<id>[0-9]+)'

    AUTO_OUTCONFIG_REGEXP = re.compile(
        r'^out(?:config)?{file_id}?$'.format(file_id=_id_expr)
    )

    AUTO_TMPFILE_REGEXP = re.compile(
        r'^tmp{file_id}?$'.format(file_id=_id_expr)
    )

    AUTO_TMPDIR_REGEXP = re.compile(
        r'^t{file_id}?$'.format(file_id=_id_expr)
    )

    del _id_expr

    @classmethod
    def new_from_settings(cls, conf_source_env, subtype, args, data, **kwargs):
        """
        Creates a new configuration source with information
        from the [source] section of a settings file.

        The settings-specific initialization of the config source
        is handled in init_from_settings(), this class method creates
        a new object from conf_source_env and **kwargs
        and redirects the remaining args to the init_from_*() method.

        @param conf_source_env:  configuration source environment
        @type  conf_source_env:  L{ConfigurationSourcesEnv}
        @param subtype:          source subtype,
                                 only meaningful for certain conf sources,
                                 e.g. "script"
        @type  subtype:          usually C{None} or C{str}
        @param args:             mixed constructor/get_configuration_basis()
                                 arguments
        @type  args:             C{list}|C{tuple} of C{str}
        @param data:             configuration source data
                                 (all lines in [source] after the first one)
        @type  data:             usually C{None} or C{list} of C{str}
        @param kwargs:           additional subclass-specific keyword arguments
                                 passed to __init__()

        @return:  2-tuple (configuration source, unused args)
        @rtype:   2-tuple (sub-of L{CommandConfigurationSourceBase}, iterable)
        """
        obj = cls(
            name=None,
            conf_source_env=conf_source_env,
            **kwargs
        )
        args_rem = obj.init_from_settings(subtype, args, data)
        obj.check_source_valid()
        return (obj, args_rem)
    # --- end of new_from_settings (...) ---

    @abc.abstractmethod
    def init_from_settings(self, subtype, args, data):
        """
        Initializes a newly created configuration source with information
        from the [source] section of a settings file.

        See also new_from_settings().

        Derived classes must implement this method.
        They may call super(), but the abstract implementation does not
        provide any functionality and returns the input args unmodified.

        @param subtype:          source subtype,
                                 only meaningful for certain conf sources,
                                 e.g. "script"
        @type  subtype:          usually C{None} or C{str}
        @param args:             mixed constructor/get_configuration_basis()
                                 arguments
        @type  args:             C{list}|C{tuple} of C{str}
        @param data:             configuration source data
                                 (all lines in [source] after the first one)
        @type  data:             usually C{None} or C{list} of C{str}

        @return:  unused args
        @rtype:   C{list}|C{tuple} of C{str}
        """
        return args
    # --- end of init_from_settings (...) ---

    @classmethod
    def new_from_def(cls, conf_source_env, name, source_def, **kwargs):
        """
        Creates a new configuration source with information
        from an already parsed and preprocessed source definition file.

        Source definition data can be created from ".ini"-like files with
        kernelconfig.sources.sourcedef.CuratedSourceDef.new_from_ini(),
        which is done in ../_sources.py (kernelconfig.sources._sources).

        The sourcedef-specific initialization of the config source
        is handled in init_from_def(), this class method creates
        a new object from conf_source_env and **kwargs
        and redirects the remaining args to the init_from_*() method.

        @param conf_source_env:  configuration source environment
        @type  conf_source_env:  L{ConfigurationSourcesEnv}
        @param name:             name of the configuration source
        @type  name:             C{str} or C{None}
        @param source_def:       config source definition data,
                                 a dict-like object
        @type  source_def:       L{CuratedSourceDef}
        @param kwargs:           additional subclass-specific keyword arguments
                                 passed to __init__()

        @return:  configuration source
        @rtype:   sub-of L{ConfigurationSourceBase}
        """
        obj = cls(
            name=name,
            conf_source_env=conf_source_env,
            **kwargs
        )
        obj.init_from_def(source_def)
        obj.check_source_valid()
        return obj
    # --- end of new_from_def (...) ---

    @abc.abstractmethod
    def init_from_def(self, source_def):
        """
        Initializes a newly created configuration source with information
        from an already parsed and preprocessed source definition file.

        Derived classes must implement this method.
        They may call super(), the implementation of the abstract base class
        creates the argument parser and attaches it to self.arg_parser.

        @param source_def:  config source definition data, a dict-like object
        @type  source_def:  L{CuratedSourceDef}

        @return:  None (implicit)
        """
        self.arg_parser = source_def.build_parser()
    # --- end of init_from_def (...) ---

    @abc.abstractmethod
    def check_source_valid(self):
        """
        This method is called after initializing the conf source with
        init_from_*(), and should raise a ConfigurationSourceInvalidError
        if the configuration is invalid or not sufficient.

        @raises ConfigurationSourceInvalidError:

        @return: None (implicit)
        """
        raise NotImplementedError()

    def format_help(self):
        """Formats the help message of this configuration source.

        This method relies on having an argument parser,
        if there is none (e.g. created from settings [source] and not from
        a source def), None will be returned.

        @return:  formatted help string or None
        @rtype:   C{str} or C{None}
        """
        if self.arg_parser is None:
            return None

        return self.arg_parser.format_help()

    def __init__(self, name, conf_source_env, **kwargs):
        super().__init__(name, **kwargs)
        self._str_formatter = None
        self.senv = conf_source_env
        self.auto_outconfig = None
        self.auto_tmpfiles = None
        self.auto_tmpdirs = None
        self.arg_parser = None

    @property
    def fmt_vars(self):
        """
        The 'static' string-format variables of this configuration source.
        """
        return self.get_str_formatter().fmt_vars

    # The thing with "getattr() || setattr(_, _, new())" methods is that
    # they are prone to errors when refactoring and not linter-friendly,
    # so we have 3 almost identical methods instead..
    # The alternative is to create the auto var mappings unconditionally,
    # which might actually happen for easier initialization of cur~sources.
    #

    def _get_init_auto_outconfig_vars(self):
        """
        @return:  auto outconfig vars
        @rtype:   L{ConfigurationSourceAutoTmpOutfileVarMapping}
        """
        auto_outconfig_vars = self.auto_outconfig
        if auto_outconfig_vars is None:
            auto_outconfig_vars = (
                _formatvar.ConfigurationSourceAutoTmpOutfileVarMapping()
            )
            self.auto_outconfig = auto_outconfig_vars
        # --
        return auto_outconfig_vars
    # --- end of _get_init_auto_outconfig_vars (...) ---

    def _get_init_auto_tmpfile_vars(self):
        """
        @return:  auto tmpfile vars
        @rtype:   L{ConfigurationSourceAutoTmpOutfileVarMapping}
        """
        auto_tmpfile_vars = self.auto_tmpfiles
        if auto_tmpfile_vars is None:
            auto_tmpfile_vars = (
                _formatvar.ConfigurationSourceAutoTmpOutfileVarMapping()
            )
            self.auto_tmpfiles = auto_tmpfile_vars
        # --
        return auto_tmpfile_vars
    # --- end of _get_init_auto_tmpfile_vars (...) ---

    def _get_init_auto_tmpdir_vars(self):
        """
        @return:  auto tmpdir vars
        @rtype:   L{ConfigurationSourceAutoTmpdirVarMapping}
        """
        auto_tmpdir_vars = self.auto_tmpdirs
        if auto_tmpdir_vars is None:
            auto_tmpdir_vars = (
                _formatvar.ConfigurationSourceAutoTmpdirVarMapping()
            )
            self.auto_tmpdirs = auto_tmpdir_vars
        # --
        return auto_tmpdir_vars
    # --- end of _get_init_auto_tmpdir_vars (...) ---

    def create_conf_basis_for_file(self, filepath):
        """
        Creates a "configuration basis" that consists of a single file.
        The file must exist and be a "normal" file
        (as determined with os.path.isfile()).

        @raises ConfigurationSourceNotFound:  if filepath missing or not a file

        @param filepath:
        @type  filepath:  C{str}

        @return:  configuration basis
        @rtype:   C{list} of C{str}
        """
        if os.path.isfile(filepath):
            return [filepath]
        else:
            raise exc.ConfigurationSourceNotFound(filepath)
    # ---

    def create_conf_basis_for_files(self, filepaths):
        """
        Creates a "configuration basis" that consists of several files
        that should be read in the given order (later on).

        @raises ConfigurationSourceNotFound:  if any file missing or not a file

        @param filepaths:
        @type  filepaths:  iterable of C{str} (e.g. list, genexpr)

        @return:  configuration basis
        @rtype:   C{list} of C{str}
        """
        retv = []
        miss = []
        for filepath in filepaths:
            if os.path.isfile(filepath):
                retv.append(filepath)
            else:
                miss.append(filepath)
        # --

        if miss:
            raise exc.ConfigurationSourceNotFound(miss)

        return retv
    # --- end of create_conf_basis_for_files (...) ---

    def get_new_str_formatter(self):
        """Returns a copy of the shared 'static' string formatter.

        This method can safely be used after binding the configuration
        source environment config (in __init__()).
        However, fmt vars added to the formatter
        are not preserved between calls.

        @return:  str formatter
        @rtype:   L{ConfigurationSourceStrFormatter}
        """
        return self.get_str_formatter().copy()
    # --- end of get_new_str_formatter (...) ---

    def get_str_formatter(self):
        """Returns the shared 'static' string formatter.

        This method can safely be used after binding the configuration
        source environment config (in __init__()).

        @return:  str formatter
        @rtype:   L{ConfigurationSourceStrFormatter}
        """
        str_formatter = self._str_formatter
        if str_formatter is None:
            str_formatter = _format.ConfigurationSourceStrFormatter(self.senv)
            self._str_formatter = str_formatter

        return str_formatter
    # --- end of get_str_formatter (...) ---

    @abc.abstractmethod
    def add_auto_var(self, varname, varkey):
        """
        Creates a "dynamic automatic format variable"
        if varname references such a var.

        Note that this method may get called multiple times for the same var.

        Derived classes must implement this method.
        Source types that do not support auto-vars should return "False",
        which is also available via super().add_auto_var(...).

        A few helper methods for common auto vars exist
        that can be used by derived classes if they support these vars:

          * add_auto_var_outconfig()   -- handle outconfig   vars
          * add_auto_var_tmpfile()     -- handle tmp-outfile vars
          * add_auto_var_tmpdir()      -- handle tmpdir      vars

          It is safe to call them in any order in an "elif" fashion:

          >>> if <custom auto var>:
          >>>     return True
          >>> elif add_auto_var_outconfig(...):
          >>>     return True
          >>> elif ...:
          >>>     ...
          >>> else:
          >>>     return False


        @param varname:  name of the format variable
                         (not case-converted and without dot suffix,
                         e.g. "outconfig" and not "outConfig.name")
        @type  varname:  C{str}
        @param varkey:   lowercase name of the format variable
        @type  varkey:   C{str}

        @return:  True if varname references a auto-var, else False
        @rtype:   C{bool}
        """
        return False
    # --- end of add_auto_var (...) ---

    def add_auto_var_outconfig(self, varname, varkey):
        """See add_auto_var()."""
        match = self.AUTO_OUTCONFIG_REGEXP.match(varkey)
        if match is None:
            return False

        auto_outconfig_vars = self._get_init_auto_outconfig_vars()
        auto_outconfig_vars.add(varkey, varname)
        return True
    # --- end of add_auto_var_outconfig (...) ---

    def add_auto_var_tmpfile(self, varname, varkey):
        """See add_auto_var()."""
        match = self.AUTO_TMPFILE_REGEXP.match(varkey)
        if match is None:
            return False

        auto_tmpfile_vars = self._get_init_auto_tmpfile_vars()
        auto_tmpfile_vars.add(varkey, varname)
        return True
    # --- end of add_auto_var_tmpfile (...) ---

    def add_auto_var_tmpdir(self, varname, varkey):
        """See add_auto_var()."""
        match = self.AUTO_TMPDIR_REGEXP.match(varkey)
        if match is None:
            return False

        auto_tmpdir_vars = self._get_init_auto_tmpdir_vars()

        if match.group("id"):
            # then create a new, unique tmpdir
            auto_tmpdir_vars.add(varkey, varname)
        else:
            # then use the shared tmpdir
            auto_tmpdir_vars.add(".", varname)

        return True
    # --- end of add_auto_var_tmpfile (...) ---

    def scan_auto_vars(
        self, format_str_list, str_formatter=None, drop_params=True
    ):
        """
        Scans a list of format strings for "dynamic auto variables", which
        are vars that need to be created during get_configuration_basis().
        Examples include "{T}" (create tmpdir, substitute {T} with its path),
        and "{outconfig}" (create outconfig obj, substitute with its path).

        Only unknown variables participate in auto-var scanning.
        That is, if the string formatter contains already a "T" fmtvar,
        "T" is not considered to be an auto-var.

        Additionally, this method returns whether any auto var has been
        detected and a set of unknown variables that were not auto vars.
        Consumers may use this e.g. for raising
        a ConfigurationSourceInvalidError at config source creation time.

        @param   format_str_list:  list of format strings to be scanned
        @type    format_str_list:  C{list} of C{str}  (or iterable)

        @keyword str_formatter:    in order to avoid unnecessary instantiation
                                   of a new str formatter, an existing one
                                   may be passed via this keyword.
                                   Otherwise, a new one is created.

        @type    str_formatter:    C{None} | L{ConfigurationSourceStrFormatter}

        @keyword drop_params:      whether to remove known argument parser
                                   parameters from the set of unknown vars
                                   Defaults to True.
        @type    drop_params:      C{bool}


        @return:  2-tuple (
                    any auto var detected,
                    set of unknown non-auto vars (may be empty)
                  )
        @rtype:   2-tuple (C{bool}, C{set} of C{str})
        """
        if str_formatter is None:
            str_formatter = self.get_str_formatter()

        missing = set()
        any_autovar = False
        for varname in (
            str_formatter.iter_unknown_var_names_v(format_str_list)
        ):
            if self.add_auto_var(varname, varname.lower()):
                any_autovar = True
            else:
                missing.add(varname)
        # --

        if missing:
            if drop_params and self.arg_parser is not None:
                for param_name in self.arg_parser.source_params:
                    missing.discard("param_{}".format(param_name))
        # --

        return (any_autovar, missing)
    # --- end of scan_auto_vars (...) ---

    def scan_auto_vars_must_exist(self, format_str_list, **kwargs):
        """This is a helper method that wraps scan_auto_vars().

        If any missing vars are reported,
        it raises an ConfigurationSourceInvalidError.

        The return value indicates whether any auto var has been detected.

        @return:  any auto var detected
        @rtype:   C{bool}
        """
        any_autovar, missing = self.scan_auto_vars(format_str_list, **kwargs)
        if missing:
            raise exc.ConfigurationSourceInvalidError(
                "unknown vars", sorted(missing)
            )
        return any_autovar
    # --- end of scan_auto_vars_must_exist (...) ---

# --- end of ConfigurationSourceBase ---


class PhasedConfigurationSourceBase(ConfigurationSourceBase):
    """
    Base class for more complex configuration source types.

    The creation of configuration bases is split into several phases,
    out of which some must be implemented by derived classes,
    while others are optional:

    * do_reset()                     -- optional, returns None,
                                        resets the conf source to clean state

    * do_parse_source_argv(argv)     -- mandatory, returns arg_config obj,
                                        creates an arg config object
                                        that is used by all other phases

    * do_init_auto_vars(arg_config)  -- optional, returns None,
                                        initializes the dynamic/automatic
                                        format vars
                                        Does not involve fs operations.

    * do_init_tmpdir(arg_config)     -- optional, returns None,
                                        initializes the temporary dir

    * do_init_env(arg_config)        -- optional, returns None,
                                        initializes arg_config.env_vars
                                        if necessary. no-op by default.

    * do_prepare(arg_config)         -- optional, returns None,
                                        prepare actions (e.g. file backup)

    * do_get_conf_basis(arg_config)  -- required, returns conf basis obj,
                                        the actual conf-getter

    * do_finalize(arg_config, conf_basis)
                                     -- optional, returns conf basis obj,
                                        cleanup and postprocessing
    """

    def do_reset(self):
        """Resets the configuration source to a clean state.

        @return:  None (implicit)
        """
        pass

    @abc.abstractmethod
    def do_parse_source_argv(self, argv):
        """Parses argv and creates an arg config object.

        Derives classes must implement this method.
        They may call super() to get the default implementation,
        which uses self.arg_parser to parse argv, and raises an error
        if argv is not empty, but no parser has been created.

        @raises ConfigurationSourceFeatureUsageError:  argv, but no parser
        @raises ConfigurationSourceError:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceExecError:
        @raises ConfigurationSourceNotFound:

        @param argv:  arguments
        @type  argv:  C{list} of C{str}

        @return:  arg config
        @rtype:   L{ConfigurationSourceArgConfig}
        """
        arg_config = _argconfig.ConfigurationSourceArgConfig()

        if self.arg_parser is not None:
            # allow None argv
            params, argv_rem = self.arg_parser.parse_args(argv or [])
            if params:
                arg_config.set_params(params)

            if argv_rem:
                arg_config.argv.extend(argv_rem)

        elif argv:
            raise exc.ConfigurationSourceFeatureUsageError(
                "this configuration source does not accept parameters"
            )
        # --

        return arg_config
    # --- end of do_parse_source_argv (...) ---

    def do_init_auto_vars(self, arg_config):
        """
        Creates the automatic temporary files/directories
        for the current get_configuration_basis() cycle
        and adds them to the given arg_config object,
        by registering them as outfiles/outconfig/outdirs
        and by adding them as format variables.

        After calling this method, arg_config knows about all auto files/dirs,
        but a temporary directory must be assigned to arg_config before
        dynamic str-formatting can be used (see do_init_tmpdir()).

        @param arg_config:  (will be modified)
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  None (implicit)
        """
        if self.auto_outconfig:
            arg_config.set_need_tmpdir()
            outfiles, fmt_vars = self.auto_outconfig.get_vars()
            arg_config.register_outfiles(outfiles, is_outconfig=True)
            arg_config.fmt_vars.update(fmt_vars)
        # --

        if self.auto_tmpfiles:
            arg_config.set_need_tmpdir()
            outfiles, fmt_vars = self.auto_tmpfiles.get_vars()
            arg_config.register_outfiles(outfiles, is_outconfig=False)
            arg_config.fmt_vars.update(fmt_vars)
        # --

        if self.auto_tmpdirs:
            arg_config.set_need_tmpdir()
            tmpdirs, fmt_vars = self.auto_tmpdirs.get_vars()
            arg_config.register_outdirs(tmpdirs)
            arg_config.fmt_vars.update(fmt_vars)
        # --

    # --- end of do_init_auto_vars (...) ---

    def do_init_tmpdir(self, arg_config):
        """
        Creates a temporary directory for arg_config if necessary
        and assigns it to arg_config, which triggers fs-initialization
        of all temporay files/dirs, including auto vars.

        @param arg_config:  (will be modified)
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  None (implicit)
        """
        if arg_config.check_need_tmpdir():
            arg_config.assign_tmpdir(
                self.senv.get_tmpdir().get_new_subdir()
            )
    # --- end of do_init_tmpdir (...) ---

    def do_init_env(self, arg_config):
        """
        Initializes the environment variables of arg_config (env_vars attr).

        They are only meaningful to configuration sources that involve running
        subprocesses, and therefore the base class implementation is a no-op.
        See CommandConfigurationSourceBase.do_init_env() for an example.

        @param arg_config:  (will be modified)
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  None (implicit)
        """
        pass
    # --- end of do_init_env (...) ---

    def _prepare_outfiles(self, filesv):
        for outfile in filesv:
            fs.prepare_output_file(outfile, move=True)
            # be extra sure that outfile does not exist anymore
            fs.rmfile(outfile)

    def do_prepare_outfiles(self, arg_config):
        """
        Backup-moves all output files and creates directories as needed.
        For temporary files, this is usually a no-op.

        After calling this method,
        no outfile exists and it is likely that they can be created
        (without having to call mkdir()).

        @param arg_config:
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  None (implicit)
        """
        self._prepare_outfiles(arg_config.iter_outfile_paths())

    def do_prepare(self, arg_config):
        """Pre-"get conf basis" actions.

        The default implementation backup-moves all output files,
        which is implemented in do_prepare_outfiles().
        For tmpdir outfiles, this may be a no-op.

        @raises ConfigurationSourceError:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceExecError:
        @raises ConfigurationSourceNotFound:

        @param arg_config:  arg config
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  None (implicit)
        """
        self.do_prepare_outfiles(arg_config)
    # --- end of do_prepare (...) ---

    @abc.abstractmethod
    def do_get_conf_basis(self, arg_config):
        """actual "get conf basis" actions.

        Derived classes must implement this method.

        @raises ConfigurationSourceError:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceExecError:
        @raises ConfigurationSourceNotFound:

        @param arg_config:  arg config
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  conf basis
        @rtype:   C{list} of C{str}
        """
        raise NotImplementedError()
    # ---

    def do_finalize(self, arg_config, conf_basis):
        """Post-"get conf basis" actions.

        @raises ConfigurationSourceError:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceExecError:
        @raises ConfigurationSourceNotFound: ?

        @param arg_config:  arg config
        @type  arg_config:  L{ConfigurationSourceArgConfig}
        @param conf_basis:  conf basis
        @type  conf_basis:  C{list} of C{str}

        @return:  conf basis
        @rtype:   C{list} of C{str}
        """
        return conf_basis

    def get_configuration_basis(self, argv):
        """Returns a configuration basis.

        @raises ConfigurationSourceError:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceExecError:
        @raises ConfigurationSourceNotFound:

        @param argv:  arguments
        @type  argv:  C{list} of C{str}

        @return:  conf basis
        @rtype:   C{list} of C{str}
        """
        self.do_reset()

        arg_config = self.do_parse_source_argv(argv)

        self.do_init_auto_vars(arg_config)
        self.do_init_tmpdir(arg_config)
        self.do_init_env(arg_config)

        self.do_prepare(arg_config)

        conf_basis = self.do_get_conf_basis(arg_config)

        return self.do_finalize(arg_config, conf_basis)
    # --- end of get_configuration_basis (...) ---

    def create_conf_basis_for_arg_config(self, arg_config):
        """
        Creates a "configuration basis" from arg_config's outconfig files.

        @raises NotImplementedError:  if arg_config does not provide
                                      a configuration basis

        @param arg_config:
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  configuration basis
        @rtype:   C{list} of C{str}
        """
        outconfig_v = list(arg_config.iter_outconfig_paths())
        if not outconfig_v:
            raise NotImplementedError("no outconfig")

        else:
            return self.create_conf_basis_for_files(outconfig_v)
    # ---

    def get_dynamic_str_formatter(self, arg_config):
        """
        Returns the 'dynamic' string formatter that is bound to
        an arg config object.

        @param arg_config:

        @return:  str formatter
        @rtype:   L{ConfigurationSourceStrFormatter}
        """
        str_formatter = self.get_new_str_formatter()
        self.init_dynamic_str_formatter(str_formatter, arg_config)
        return str_formatter
    # --- end of get_dynamic_str_formatter (...) ---

    def init_dynamic_str_formatter(self, str_formatter, arg_config):
        if arg_config.fmt_vars:
            str_formatter.fmt_vars.update(arg_config.fmt_vars)
    # --- end of init_dynamic_str_formatter (...) ---

# --- end of ConfigurationSourceBase ---


class CommandConfigurationSourceBase(PhasedConfigurationSourceBase):
    """
    A phased configuration source base class specialized
    for running a single command that creates the configuration basis.

    Derived classes must implement the following methods:

    * init_from_def()
    * init_from_settings()
    * check_source_valid()
    * do_parse_source_argv()  --  may return from super() here
    * create_cmdv()           --  create the command to be run

    In particular, do_get_conf_basis() and add_auto_var() are provided.
    do_get_conf_basis() is split into two subphases,
    command execution and config basis creation.

    (Phases may of course be overridden or extended where meaningful.)

    Additionally, this class offers helper methods for str-formatting commands.

    @ivar proc_timeout:  command timeout in seconds, or None for no timeout
                         Defaults to None,
                         the attr can be (re-)set after __init__().
    @type proc_timeout:  C{None} or C[int}|C{float}

    @ivar return_codes_success:  set of exit codes that indicate success
                                 Defaults to {os.EX_OK},
                                 the attr can be (re-)set after __init__().
    @type return_codes_success:  C{set} of C{int}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proc_timeout = None
        self.return_codes_success = {os.EX_OK, }

    def add_auto_var(self, varname, varkey):
        """
        command-running configuration sources support the full range
        of automatic variables - outconfig, tmpfile, tmpdir.

        @return:  "varname references an auto var?"
        @rtype:   C{bool}
        """
        if self.add_auto_var_outconfig(varname, varkey):
            return True

        elif self.add_auto_var_tmpfile(varname, varkey):
            return True

        elif self.add_auto_var_tmpdir(varname, varkey):
            return True

        else:
            return False
    # --- end of add_auto_var (...) ---

    def format_cmdv(self, arg_config, cmdv, *, str_formatter=None):
        """Formats a command using the dynamic string formatter.

        @param   arg_config
        @type    arg_config:       L{ConfigurationSourceArgConfig}
        @param   cmdv:             command to be formatted
        @type    cmdv:             C{list} of C{str}

        @keyword str_formatter:    in order to avoid unnecessary instantiation
                                   of a new str formatter, an existing one
                                   may be passed via this keyword.
                                   Otherwise, a new one is created.

        @type    str_formatter:    C{None} | L{ConfigurationSourceStrFormatter}

        @return:  formatted command
        @rtype:   C{list} of C{str}
        """
        if str_formatter is None:
            str_formatter = self.get_dynamic_str_formatter(arg_config)
        return str_formatter.format_list(cmdv)
    # --- end of format_cmdv (...) ---

    @abc.abstractmethod
    def create_cmdv(self, arg_config):
        """
        Creates the command that will be run to get the configuration basis.

        Derived classes must implement this method.
        The returned should be a string or a list of strings (or tuple),
        in either case it should already be formatted.
        str-lists can be formatted with format_cmdv().

        @param arg_config:
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  command
        @rtype:   C{list} of C{str}, or C{str}
        """
        raise NotImplementedError()

    def create_subproc(self, arg_config):
        """
        Creates the subprocess that produces the configuration basis.

        Derived classes may override this, but implementing the create_cmdv()
        method should be sufficient in most cases.

        @param arg_config:
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  subprocess (not started yet)
        @rtype:   L{subproc.SubProc}
        """
        return subproc.SubProc(
            self.create_cmdv(arg_config),
            logger=self.logger,
            tmpdir=arg_config.tmpdir_path,
            extra_env=arg_config.env_vars
        )

    def do_init_env(self, arg_config):
        """
        Initializes the environment variables of arg_config as follows:

        * adds all source env related environment variables
          (e.g. SRCTREE, ARCH, KV)

        * T: if a temporary dir has been requested for arg_config (likely),
          sets T to its path. Otherwise, unsets T.

        @param arg_config:  (will be modified)
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  None (implicit)
        """
        arg_config.env_vars.update(self.senv.get_env_vars())
        if arg_config.has_tmpdir():
            arg_config.env_vars["T"] = arg_config.tmpdir_path
        else:
            arg_config.env_vars["T"] = None  # deletes "T"
    # ---

    def create_conf_basis(self, arg_config, proc):
        """
        This method creates the configuration basis,
        it is called after running the subprocess
        (if it completed successfully).

        Derived classes may override this method,
        the default implementation redirects to
        create_conf_basis_for_arg_config().

        @param arg_config:
        @type  arg_config:  L{ConfigurationSourceArgConfig}
        @param proc:        subprocess  (completed successfully)
        @type  proc:        L{subproc.SubProc}

        @return:  configuration basis
        @rtype:   C{list} of C{str}
        """
        return self.create_conf_basis_for_arg_config(arg_config)

    def do_get_conf_basis(self, arg_config):
        """
        Gets the "configuration basis".

        Runs a subprocess created with create_subproc() (--> create_cmdv()),
        and calls create_conf_basis() to create the conf basis.

        Subprocess errors raise an exception.
        @raises ConfigurationSourceExecError:  subprocess error (or timeout)

        @param arg_config:
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  configuration basis
        @rtype:   C{list} of C{str}
        """
        with self.create_subproc(arg_config) as proc:
            try:
                retcode = proc.join(
                    timeout=self.proc_timeout,
                    return_success=False
                )
            except subprocess.TimeoutExpired:
                raise exc.ConfigurationSourceExecError(
                    "timeout", proc.cmdv
                ) from None
            # --

            if retcode in self.return_codes_success:
                pass
            # elif retcode in self.return_codes_retry: ...
            else:
                raise exc.ConfigurationSourceExecError("exit code", proc.cmdv)

            conf_basis = self.create_conf_basis(arg_config, proc)
        # -- end with

        return conf_basis
    # --- end of do_get_conf_basis (...) ---

# --- end of CommandConfigurationSourceBase ---
