# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _sourcebase
from ..abc import exc

__all__ = ["ScriptConfigurationSource"]


class ScriptConfigurationSource(_sourcebase.CommandConfigurationSourceBase):
    """
    @type interpreter:  C{None} or C{list} of C{str}
    @type script_file:  C{None} or C{str}
    @type script_data:  C{None} or C{list} of C{str}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interpreter = None
        self.script_file = None
        self.script_data = None

    def set_interpreter(self, interpreter, argv=None):
        if not interpreter:
            raise exc.ConfigurationSourceInvalidError("empty interpreter name")

        self.interpreter = [interpreter]
        if argv:
            self.interpreter.extend(argv)

    def write_script_file(self, formatted_data):
        script_filepath = None
        with self.senv.get_tmpdir().open_new_file(text=True) as tmpfile:
            tmpfile.fh.write("\n".join(formatted_data))
            tmpfile.fh.write("\n")
            script_filepath = tmpfile.path
        return script_filepath
    # --- end of write_script_file (...) ---

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

        str_formatter = self.get_str_formatter()

        if self.scan_auto_vars_must_exist(data, str_formatter=str_formatter):
            self.script_data = data

        else:
            self.script_file = self.write_script_file(
                str_formatter.format_list(data)
            )
        # --

        return args
    # --- end of init_from_settings (...) ---

    def create_cmdv(self, arg_config):
        if not self.interpreter:
            raise exc.ConfigurationSourceInvalidError("no interpreter")

        if not arg_config.script_file:
            raise exc.ConfigurationSourceInvalidError("no script file")

        cmdv = []
        cmdv.extend(self.interpreter)
        cmdv.append(arg_config.script_file)

        if arg_config.argv:
            cmdv.extend(arg_config.argv)

        return cmdv
    # --- end of create_cmdv (...) ---

    def do_parse_source_argv(self, argv):
        arg_config = _sourcebase.ConfigurationSourceArgConfig()
        if argv:
            arg_config.argv.extend(argv)

        if not self.auto_outconfig:
            # FIXME: remove/replace,
            #        there is also the possibility to read from piped stdout
            arg_config.add_tmp_outfile("config")
        # --

        # set script file,
        #  it is None if it has to be created in the prepare phase
        arg_config.script_file = self.script_file  # new attr

        return arg_config
    # --- end of do_parse_source_argv (...) ---

    def do_prepare(self, arg_config):
        if arg_config.script_file is None:
            # then it needs to be created from self.script_data now
            if not self.script_data:
                raise exc.ConfigurationSourceInvalidError("no script data")

            str_formatter = self.get_dynamic_str_formatter(arg_config)
            arg_config.script_file = self.write_script_file(
                str_formatter.format_list(self.script_data)
            )
    # --- end of do_prepare (...) ---

# --- end of ScriptConfigurationSource ---
