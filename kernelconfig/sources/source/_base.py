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

from . import _argconfig
from ._argconfig import ConfigurationSourceArgConfig   # remove, unexport
from . import _format
from . import _formatvar


__all__ = [
    "ConfigurationSourceArgConfig",
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
        return (obj, args_rem)
    # --- end of new_from_settings (...) ---

    @abc.abstractmethod
    def init_from_settings(self, subtype, args, data):
        raise NotImplementedError()
    # --- end of init_from_settings (...) ---

    def __init__(self, name, conf_source_env, **kwargs):
        super().__init__(name, **kwargs)
        self.senv = conf_source_env
        self.auto_outconfig = None
        self.auto_tmpfiles = None
        self.auto_tmpdirs = None

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
            return filepath
        else:
            raise exc.ConfigurationSourceNotFound(filepath)
    # ---

    def get_str_formatter(self):
        """Returns the 'static' string formatter.

        This method can safely be used after binding the configuration
        source environment config (in __init__()).
        However, fmt vars added to the formatter
        are not preserved between calls.

        @return:  str formatter
        @rtype:   L{ConfigurationSourceStrFormatter}
        """
        return _format.ConfigurationSourceStrFormatter(self.senv)

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
        auto_tmpdir_vars.add(varkey, varname)

        return True
    # --- end of add_auto_var_tmpfile (...) ---

    def scan_auto_vars(self, format_str_list, str_formatter=None):
        """
        Scans a list of format strings for "dynamic auto variables", which
        are vars that need to be created during get_configuration_basis().
        Examples include "{T}" (create tmpdir, substitute {T} with its path),
        and "{outconfig}" (create outconfig obj, substitute with its path).

        Only unknown variables participate in auto-var scanning.
        That is, if the string formatter contains already a "T" fmtvar,
        "T" is not considered to be an auto-var.

        Additionally, this method returns whether any auto var has been
        detected and a list of unknown variables that were not auto vars.
        Consumers may use this e.g. for raising
        a ConfigurationSourceInvalidError at config source creation time.

        @param   format_str_list:  list of format strings to be scanned
        @type    format_str_list:  C{list} of C{str}  (or iterable)

        @keyword str_formatter:    in order to avoid unnecessary instantiation
                                   of a new str formatter, an existing one
                                   may be passed via this keyword.
                                   Otherwise, a new one is created.

        @type    str_formatter:    C{None} | L{ConfigurationSourceStrFormatter}

        @return:  2-tuple (
                    any auto var detected,
                    list of unknown non-auto vars (may be empty)
                  )
        @rtype:   2-tuple (C{bool}, C{list} of C{str})
        """
        if str_formatter is None:
            str_formatter = self.get_str_formatter()

        missing = []
        any_autovar = False
        for varname in (
            str_formatter.iter_unknown_var_names_v(format_str_list)
        ):
            if self.add_auto_var(varname, varname.lower()):
                any_autovar = True
            else:
                missing.append(varname)
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
                "unkown vars", sorted(missing)
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

    * do_init_tmpdir(arg_config)     -- initializes the temporary dir

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
        return _argconfig.ConfigurationSourceArgConfig()

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
            raise NotImplementedError("auto tmpdirs")
        # --

    # --- end of do_init_auto_vars (...) ---

    def do_init_tmpdir(self, arg_config):
        if arg_config.check_need_tmpdir():
            arg_config.assign_tmpdir(
                self.senv.get_tmpdir().get_new_subdir_path()
            )
    # --- end of do_init_tmpdir (...) ---

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

        self.do_prepare(arg_config)

        conf_basis = self.do_get_conf_basis(arg_config)

        return self.do_finalize(arg_config, conf_basis)
    # --- end of get_configuration_basis (...) ---

    def create_conf_basis_for_arg_config(self, arg_config):
        outconfig_v = list(arg_config.iter_outconfig_paths())
        if not outconfig_v:
            raise NotImplementedError("no outconfig")

        elif len(outconfig_v) == 1:
            return self.create_conf_basis_for_file(outconfig_v[0])

        else:
            raise NotImplementedError("many outconfigs")
    # ---

    def get_dynamic_str_formatter(self, arg_config):
        """
        Returns the 'dynamic' string formatter that is bound to
        an arg config object.

        @param arg_config:

        @return:  str formatter
        @rtype:   L{ConfigurationSourceStrFormatter}
        """
        str_formatter = self.get_str_formatter()
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

    def create_subproc(self, arg_config):
        return subproc.SubProc(
            self.create_cmdv(arg_config),
            logger=self.logger, tmpdir=arg_config.tmpdir
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
