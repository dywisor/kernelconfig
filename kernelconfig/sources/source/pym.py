# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import importlib
import importlib.machinery
import string
import sys

from ...abc import loggable
# from ...util import fs

from ..abc import exc
from .._util import _pymenv

from . import _sourcebase


__all__ = ["PymConfigurationSource"]


class PymConfigurationSource(_sourcebase.PhasedConfigurationSourceBase):
    """
    This configuration source loads a python module
    and calls its run() function with an "environment" object as first arg.

    Also, if the module has a reset() function,
    it is called after (re)loading the module.

    This class is meant for complex source types
    that benefit from interfacing with kernelconfig.

    It can only be created from source definition files.

    A minimal (but useless) module would be:

       # module for <name> configuration source
       # -*- coding: utf-8 -*-

       def reset():
           pass

       def run(env):
           env.add_config_file(env.download_file("http://the/config/file"))

    See _pymenv (kernelconfig.sources._util._pymenv) for details about 'env'.
    """

    @property
    def pym_file(self):
        return self.pym.filepath

    @property
    def pym_name(self):
        return self.pym.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pym = None
        self.sourcedef_config = None

    def check_source_valid(self):
        if self.pym is None:
            raise exc.ConfigurationSourceInvalidError(
                "python module has not been set up"
            )

        pym_file = self.pym.filepath
        if not pym_file:
            raise exc.ConfigurationSourceInvalidError(
                "python module file path is not set"
            )

        elif not os.path.isfile(pym_file):
            raise exc.ConfigurationSourceInvalidError(
                "python module file does not exist: {}".format(pym_file)
            )

        elif not os.access(pym_file, os.R_OK):
            raise exc.ConfigurationSourceInvalidError(
                "python module file is not readable: {}".format(pym_file)
            )

        pym_name = self.pym.name
        if not pym_name:
            raise exc.ConfigurationSourceInvalidError("pym_name is not set")

        if self.sourcedef_config is None:
            raise exc.ConfigurationSourceInvalidError(
                "sourcedef_config is not set"
            )
    # --- end of check_source_valid (...) ---

    def add_auto_var(self, varname, varkey):
        return False
    # --- end of add_auto_var (...) ---

    def init_from_settings(self, subtype, args, data):
        raise exc.ConfigurationSourceInvalidError(
            "cannot be created from settings"
        )
    # --- end of init_from_settings (...) ---

    def init_from_def(self, source_data):
        super().init_from_def(source_data)

        pym_file = (
            source_data.get("path") or source_data.default_script_file
        )
        if pym_file:
            self.pym = self.create_loggable(
                PymConfigurationSourceModule,
                name=PymConfigurationSourceModule.sanitize_name(
                    "curated_source_pym_{}".format(self.name)
                ),
                filepath=pym_file,
                logger_name="pym"
            )

        self.sourcedef_config = source_data.get("config") or {}
    # --- end of init_from_def (...) ---

    def do_parse_source_argv(self, argv):
        arg_config = super().do_parse_source_argv(argv)

        arg_config.pym = None  # new attr
        return arg_config
    # --- end of do_parse_source_argv (...) ---

    def do_load_pym(self, arg_config):
        # catch ImportError?
        arg_config.pym = self.pym.load()
        arg_config.pym.call_optional("reset")
    # --- end of do_load_pym (...) ---

    def do_prepare(self, arg_config):
        super().do_prepare(arg_config)
        self.do_load_pym(arg_config)
    # --- end of do_prepare (...) ---

    def do_get_conf_basis(self, arg_config):
        # arg_config.pym should spawn the run_env,
        #  so that versioning is actually possibly
        run_env = self.create_loggable(
            _pymenv.PymConfigurationSourceRunEnv,
            name=self.name,
            conf_source_env=self.senv,
            config=self.sourcedef_config,
            arg_config=arg_config,
            logger_name="pymrun"
        )

        # not really necessary, but enforce cwd=tmpdir for the module
        old_working_dir = os.getcwd()
        try:
            os.chdir(run_env.get_tmpdir_path())
            ret = arg_config.pym.call("run", env=run_env)

        finally:
            os.chdir(old_working_dir)

        if not ret and ret is not None:
            raise exc.ConfigurationSourceExecError()

        return self.create_conf_basis_for_arg_config(arg_config)
    # --- end of do_get_conf_basis (...) ---

# --- end of PymConfigurationSource ---


class PymConfigurationSourceModule(loggable.AbstractLoggable):

    PYM_NAME_CHARS = string.ascii_letters + string.digits + "_"

    @classmethod
    def load_module_from_file(cls, name, filepath, *, write_bytecode=False):
        # TODO in Python >= 3.5, use importlib.util:
        # >>> spec   = importlib.util.spec_from_file_location(name, filepath)
        # >>> module = importlib.util.module_from_spec(spec)
        # >>> spec.loader.exec_module(module) ?
        #  see http://bugs.python.org/issue21436#msg255901

        bak_dont_write_bytecode = sys.dont_write_bytecode
        try:
            if write_bytecode is not None:
                sys.dont_write_bytecode = not bool(write_bytecode)

            pym_loader = importlib.machinery.SourceFileLoader(name, filepath)
            return pym_loader.load_module(name)

        finally:
            sys.dont_write_bytecode = bak_dont_write_bytecode
    # --- end of load_module_from_file (...) ---

    @classmethod
    def sanitize_name(cls, name):
        pym_name_chars = cls.PYM_NAME_CHARS
        return "".join((c for c in name if c in pym_name_chars))

    def __init__(self, name, filepath, **kwargs):
        super().__init__()
        self.name = name
        self.filepath = filepath
        self._pym = None
    # --- end of __init__ (...) ---

    def _load(self):
        if self._pym is None:
            self.logger.debug(
                "Loading python module %s (from %r)", self.name, self.filepath
            )

            self._pym = self.load_module_from_file(self.name, self.filepath)
            self.logger.debug("Python module %s has been loaded", self.name)

        else:
            self.logger.debug(
                "Python module %s has already been loaded", self.name
            )
    # --- end of _load (...) ---

    def load(self):
        self._load()
        return self
    # --- end of load (...) ---

    def call_optional(self, name, *args, **kwargs):
        try:
            func = getattr(self._pym, name)
        except AttributeError:
            if self._pym is None:
                self.warning("module has not been loaded")
            self.logger.debug("has no %s() function", name)
            return None

        if not hasattr(func, "__call__"):
            self.logger.debug("%s is not a function", name)
            return None
        # --

        return func(*args, **kwargs)
    # --- end of call_optional (...) ---

    def call(self, name, *args, **kwargs):
        try:
            func = getattr(self._pym, name)
        except AttributeError:
            if self._pym is None:
                raise exc.ConfigurationSourceExecError(
                    "module has not been loaded"
                ) from None
            else:
                raise exc.ConfigurationSourceExecError(
                    "module has no {}() function".format(name)
                )
        # --

        if not hasattr(func, "__call__"):
            raise exc.ConfigurationSourceExecError(
                "{} is not a function".format(name)
            )

        return func(*args, **kwargs)
    # --- end of call (...) ---

    # __call__ = call

# --- end of PymConfigurationSourceModule ---
