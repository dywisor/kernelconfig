# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os
import subprocess

from ..abc import source as _source_abc
from ..abc import exc

from ...util import subproc
from ...util import fs


__all__ = [
    "ConfigurationSourceArgConfig",
    "ConfigurationSourceBase",
    "PhasedConfigurationSourceBase",
    "CommandConfigurationSourceBase",
]


class ConfigurationSourceArgConfig(object):
    """
    Data object that is passed around during the various phases
    of PhasedConfigurationSourceBase.

    Consumers may add new attributes freely.

    @ivar argv:
    @type argv:      undef
    @ivar outfiles:
    @type outfiles:  C{None} or list-like
    @ivar tmpdir:
    @type tmpdir:    C{None} or C{bool} or C{str}
    """

    # no __slots__ here! -- "consumers may add new attrs freely"

    def __init__(self):
        super().__init__()
        self.argv = []
        self.outfiles = None
        self.tmpdir = None

    def iter_outfiles(self):
        if not self.outfiles:
            return
        for outfile in self.outfiles:
            yield outfile
    # --

# --- end of ConfigurationSourceArgConfig ---


class ConfigurationSourceBase(_source_abc.AbstractConfigurationSource):
    """
    @ivar senv:  shared configuration source environment
    @type senv:  L{ConfigurationSourcesEnv}
    """

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

    def create_conf_basis_for_file(self, filepath):
        # FIXME: temporary helper method
        #         replace w/ plain str ret or ConfigurationBasis obj
        if os.path.isfile(filepath):
            return filepath
        else:
            raise exc.ConfigurationSourceNotFound(filepath)
    # ---

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
        return ConfigurationSourceArgConfig()

    def do_prepare_tmpdir(self, arg_config):
        if arg_config.tmpdir is True:
            arg_config.tmpdir = self.senv.get_tmpdir().get_new_subdir()

    def _prepare_outfiles(self, filesv):
        for outfile in filesv:
            fs.prepare_output_file(outfile, move=True)
            # be extra sure that outfile does not exist anymore
            fs.rmfile(outfile)

    def do_prepare_outfiles(self, arg_config):
        self._prepare_outfiles(arg_config.iter_outfiles())

    def do_prepare(self, arg_config):
        """Pre-"get conf basis" actions.

        The default implementation creates the tmpdir if necessary,
        and backup-moves all output files.
        For tmpdir outfiles, this may be a no-op.

        @raises ConfigurationSourceError:
        @raises ConfigurationSourceInvalidError:
        @raises ConfigurationSourceExecError:
        @raises ConfigurationSourceNotFound:

        @param arg_config:  arg config
        @type  arg_config:  L{ConfigurationSourceArgConfig}

        @return:  None (implicit)
        """
        self.do_prepare_tmpdir(arg_config)
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
        return arg_config.outfile

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

        self.do_prepare(arg_config)

        conf_basis = self.do_get_conf_basis(arg_config)

        return self.do_finalize(arg_config, conf_basis)
    # --- end of get_configuration_basis (...) ---

# --- end of ConfigurationSourceBase ---


class CommandConfigurationSourceBase(PhasedConfigurationSourceBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proc_timeout = None
        self.return_codes_success = {os.EX_OK, }

    @abc.abstractmethod
    def create_cmdv(self, arg_config):
        raise NotImplementedError()

    def create_subproc(self, arg_config):
        return subproc.SubProc(
            self.create_cmdv(arg_config),
            logger=self.logger, tmpdir=arg_config.tmpdir
        )

    @abc.abstractmethod
    def create_conf_basis(self, arg_config, proc):
        raise NotImplementedError()

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
