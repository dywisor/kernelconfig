# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _sourcebase
from ..abc import exc
from .._util import _argconfig

__all__ = ["CommandConfigurationSource"]


class CommandConfigurationSource(_sourcebase.CommandConfigurationSourceBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmdv = None

    def init_from_settings(self, subtype, args, data):
        if data:
            raise exc.ConfigurationSourceInvalidError("non-empty data")
        # --

        if subtype:
            raise exc.ConfigurationSourceInvalidError("non-empty subtype")
        # --

        if not args:
            raise exc.ConfigurationSourceInvalidError("empty command")
        # --

        self.cmdv = list(args)
        self.scan_auto_vars_must_exist(self.cmdv)
    # --- end of init_from_settings (...) ---

    def create_cmdv(self, arg_config):
        if not self.cmdv:
            raise exc.ConfigurationSourceInvalidError("empty command")

        cmdv = []
        cmdv.extend(self.cmdv)

        if arg_config.argv:
            cmdv.extend(arg_config.argv)

        return self.format_cmdv(arg_config, cmdv)
    # --- end of create_cmdv (...) ---

    def do_parse_source_argv(self, argv):
        arg_config = _argconfig.ConfigurationSourceArgConfig()
        if argv:
            arg_config.argv.extend(argv)

        return arg_config
    # --- end of do_parse_source_argv (...) ---

# --- end of CommandConfigurationSource ---
