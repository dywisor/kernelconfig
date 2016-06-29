# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _base
from ..abc import exc

__all__ = ["CommandConfigurationSource"]


class CommandConfigurationSource(_base.CommandConfigurationSourceBase):

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
    # --- end of init_from_settings (...) ---

    def create_cmdv(self, arg_config):
        if not self.cmdv:
            raise exc.ConfigurationSourceInvalidError("empty command")

        cmdv = []
        cmdv.extend(self.cmdv)

        if arg_config.argv:
            cmdv.extend(arg_config.argv)

        return cmdv
    # --- end of create_cmdv (...) ---

    def do_parse_source_argv(self, argv):
        arg_config = _base.ConfigurationSourceArgConfig()
        if argv:
            arg_config.argv.extend(argv)

        arg_config.add_tmp_outfile("config")
        return arg_config