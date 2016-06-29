# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _base
from ..abc import exc

__all__ = ["ScriptConfigurationSource"]


class ScriptConfigurationSource(_base.CommandConfigurationSourceBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interpreter = None
        self.script_file = None

    def set_interpreter(self, interpreter, argv=None):
        if not interpreter:
            raise exc.ConfigurationSourceInvalidError("empty interpreter name")

        self.interpreter = [interpreter]
        if argv:
            self.interpreter.extend(argv)

    def init_from_settings(self, subtype, args, data):
        if not data:
            raise exc.ConfigurationSourceInvalidError("empty data")
        # --

        if subtype:
            self.set_interpreter(subtype)
        else:
            # FIXME: get interpreter from args
            raise exc.ConfigurationSourceInvalidError("empty subtype")
        # --

        with self.senv.get_tmpdir().open_new_file(text=True) as tmpfile:
            tmpfile.fh.write("\n".join(data))
            tmpfile.fh.write("\n")
            self.script_file = tmpfile.path

        return args
    # --- end of init_from_settings (...) ---

    def create_cmdv(self, arg_config):
        if not self.interpreter:
            raise exc.ConfigurationSourceInvalidError("no interpreter")

        if not self.script_file:
            raise exc.ConfigurationSourceInvalidError("no script file")

        cmdv = []
        cmdv.extend(self.interpreter)
        cmdv.append(self.script_file)

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
