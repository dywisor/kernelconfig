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

    @ivar auto_outfiles:   mapping of "outfile" auto format vars,
                           initially None, see add_auto_var_tmpfile()
    @type auto_outfiles:   C{None} or C{dict} :: C{str} => L{TmpOutfile}

    @ivar auto_tmpdirs:    mapping of "tmpdir" auto format vars,
                           initially None, see add_auto_var_tmpdir()
    @type auto_tmpdirs:    C{None} or C{dict} :: C{str} => undef
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
        pass
    # --- end of init_from_settings (...) ---

    @classmethod
    def new_from_def(cls, conf_source_env, name, source_def, **kwargs):
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
        return self.get_str_formatter().fmt_vars

    # The thing with "getattr() || setattr(_, _, new())" methods is that
    # they are prone to errors when refactoring and not linter-friendly,
    # so we have 3 almost identical methods instead..
    # The alternative is to create the auto var mappings unconditionally,
    # which might actually happen for easier initialization of cur~sources.
    #

    def _get_init_auto_outconfig_vars(self):
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
        auto_tmpfile_vars = self.auto_outfiles
        if auto_tmpfile_vars is None:
            auto_tmpfile_vars = (
                _formatvar.ConfigurationSourceAutoTmpOutfileVarMapping()
            )
            self.auto_tmpfiles = auto_tmpfile_vars
        # --
        return auto_tmpfile_vars
    # --- end of _get_init_auto_tmpfile_vars (...) ---

    def _get_init_auto_tmpdir_vars(self):
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
        # FIXME: temporary helper method
        #         replace w/ plain str ret or ConfigurationBasis obj
        if os.path.isfile(filepath):
            return [filepath]
        else:
            raise exc.ConfigurationSourceNotFound(filepath)
    # ---

    def create_conf_basis_for_files(self, filepaths):
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
        match = self.AUTO_OUTCONFIG_REGEXP.match(varkey)
        if match is None:
            return False

        auto_outconfig_vars = self._get_init_auto_outconfig_vars()
        auto_outconfig_vars.add(varkey, varname)
        return True
    # --- end of add_auto_var_outconfig (...) ---

    def add_auto_var_tmpfile(self, varname, varkey):
        match = self.AUTO_TMPFILE_REGEXP.match(varkey)
        if match is None:
            return False

        auto_tmpfile_vars = self._get_init_auto_tmpfile_vars()
        auto_tmpfile_vars.add(varkey, varname)
        return True
    # --- end of add_auto_var_tmpfile (...) ---

    def add_auto_var_tmpdir(self, varname, varkey):
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
        if arg_config.check_need_tmpdir():
            arg_config.assign_tmpdir(
                self.senv.get_tmpdir().get_new_subdir()
            )
    # --- end of do_init_tmpdir (...) ---

    def do_init_env(self, arg_config):
        pass
    # --- end of do_init_env (...) ---

    def _prepare_outfiles(self, filesv):
        for outfile in filesv:
            fs.prepare_output_file(outfile, move=True)
            # be extra sure that outfile does not exist anymore
            fs.rmfile(outfile)

    def do_prepare_outfiles(self, arg_config):
        self._prepare_outfiles(arg_config.iter_outfile_paths())

    def do_prepare(self, arg_config):
        """Pre-"get conf basis" actions.

        The default implementation backup-moves all output files.
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
        @type  conf_basis:

        @return:  conf basis
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
        @rtype:
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proc_timeout = None
        self.return_codes_success = {os.EX_OK, }

    def add_auto_var(self, varname, varkey):
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
        if str_formatter is None:
            str_formatter = self.get_dynamic_str_formatter(arg_config)
        return str_formatter.format_list(cmdv)
    # --- end of format_cmdv (...) ---

    @abc.abstractmethod
    def create_cmdv(self, arg_config):
        raise NotImplementedError()

    def do_init_env(self, arg_config):
        arg_config.env_vars.update(self.senv.get_env_vars())
        if arg_config.has_tmpdir():
            arg_config.env_vars["T"] = arg_config.tmpdir_path
        else:
            arg_config.env_vars["T"] = None  # deletes "T"
    # ---

    def create_subproc(self, arg_config):
        return subproc.SubProc(
            self.create_cmdv(arg_config),
            logger=self.logger,
            tmpdir=arg_config.tmpdir_path,
            extra_env=arg_config.env_vars
        )

    def create_conf_basis(self, arg_config, proc):
        return self.create_conf_basis_for_arg_config(arg_config)

    def do_get_conf_basis(self, arg_config):
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
