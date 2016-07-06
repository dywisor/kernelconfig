# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _sourcebase
from ..abc import exc

__all__ = ["CommandConfigurationSource"]


class CommandConfigurationSource(_sourcebase.CommandConfigurationSourceBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cmdv = None

    def check_source_valid(self):
        if not self.cmdv:
            raise exc.ConfigurationSourceInvalidError("empty command")

    def _set_cmdv(self, cmdv):
        self.cmdv = list(cmdv)
        self.scan_auto_vars_must_exist(cmdv)
    # --- end of _set_cmdv (...) ---

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

        self._set_cmdv(args)
        return []
    # --- end of init_from_settings (...) ---

    def init_from_def(self, source_def):
        super().init_from_def(source_def)

        cmdv = source_def.get("command")
        if cmdv:
            self._set_cmdv(cmdv)
    # --- end of init_from_def (...) ---

    def create_cmdv(self, arg_config):
        cmdv = []
        cmdv.extend(self.cmdv)

        if arg_config.argv:
            cmdv.extend(arg_config.argv)

        return self.format_cmdv(arg_config, cmdv)
    # --- end of create_cmdv (...) ---

    def do_parse_source_argv(self, argv):
        return super().do_parse_source_argv(argv)
    # --- end of do_parse_source_argv (...) ---

# --- end of CommandConfigurationSource ---
