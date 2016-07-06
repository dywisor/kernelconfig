# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import stat

from . import _sourcebase
from ..abc import exc

__all__ = ["ScriptConfigurationSource"]


class ScriptConfigurationSource(_sourcebase.CommandConfigurationSourceBase):
    """
    @type base_cmdv:    C{None} or C{list} of C{str}
    @type script_file:  C{None} or C{str}
    @type script_data:  C{None} or C{list} of C{str}
    """

    SCRIPT_FILE_FMT_VARNAME = "script_file"

    @property
    def SCRIPT_FILE_FMT_VAR_TEMPLATE(self):
        return "{" + self.SCRIPT_FILE_FMT_VARNAME + "}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interpreter = None
        self.base_cmdv = None
        self.script_file = None
        self.script_data = None

    def check_source_valid(self):
        if self.script_file is None:
            if self.script_data is None:
                raise exc.ConfigurationSourceInvalidError(
                    "script file is not set, and data neither"
                )

            # {script_file} in script_data needs to be checked in init_()

        elif not os.path.isfile(self.script_file):
            raise exc.ConfigurationSourceInvalidError(
                "script file {!r} does not exist or is not a file".format(
                    self.script_file
                )
            )

        elif not os.access(
            self.script_file,
            os.R_OK | (0 if self.interpreter else os.X_OK)
        ):
            raise exc.ConfigurationSourceInvalidError(
                "script file {!r} is not readable/executable".format(
                    self.script_file
                )
            )
        # --

        if not self.base_cmdv:
            raise exc.ConfigurationSourceInvalidError("no command")
    # --- end of check_source_valid (...) ---

    def write_script_file(self, formatted_data):
        script_filepath = None
        with self.senv.get_tmpdir().open_new_file(text=True) as tmpfile:
            tmpfile.fh.write("\n".join(formatted_data))
            tmpfile.fh.write("\n")
            script_filepath = tmpfile.path
        return script_filepath
    # --- end of write_script_file (...) ---

    def init_base_cmdv_scan_auto_vars(self, base_cmdv, str_formatter=None):
        if str_formatter is not None:
            assert self.SCRIPT_FILE_FMT_VARNAME not in str_formatter.fmt_vars

        has_auto_vars, missing = self.scan_auto_vars(
            base_cmdv, str_formatter=str_formatter
        )

        try:
            missing.remove(self.SCRIPT_FILE_FMT_VARNAME)
        except KeyError:
            # FIXME: handle this gracefully
            raise exc.ConfigurationSourceInvalidError(
                "script command line does not include the script"
            )
        # --

        if missing:
            raise exc.ConfigurationSourceInvalidError(
                "unknown vars", sorted(missing)
            )
        # --

        self.base_cmdv = base_cmdv
    # --- end of init_base_cmdv_scan_auto_vars (...) ---

    def init_from_settings(self, subtype, args, data):
        super().init_from_settings(subtype, args, data)

        script_file_fmt_varname = self.SCRIPT_FILE_FMT_VARNAME
        script_file_fmt_var_template = self.SCRIPT_FILE_FMT_VAR_TEMPLATE

        if not data:
            raise exc.ConfigurationSourceInvalidError("empty data")
        # --

        base_cmdv = None
        if subtype == "sh":
            self.interpreter = True
            base_cmdv = [subtype, script_file_fmt_var_template]
        else:
            # FIXME: get interpreter from args
            raise exc.ConfigurationSourceInvalidError("empty/unknown subtype")
        # --

        if args:
            base_cmdv.extend(args)

        str_formatter = self.get_str_formatter()
        # generally, self.fmt_vars should be used for modifying fmt vars,
        # but in this case, it is important that the formatter does not
        # have this var:
        assert self.SCRIPT_FILE_FMT_VARNAME not in str_formatter.fmt_vars

        has_auto_vars, missing = self.scan_auto_vars(
            data, str_formatter=str_formatter
        )

        if script_file_fmt_varname in missing:
            raise exc.ConfigurationSourceInvalidError(
                "script references itself via {} format var".format(
                    script_file_fmt_varname
                )
            )
        elif missing:
            raise exc.ConfigurationSourceInvalidError(
                "unknown vars", sorted(missing)
            )
        # --

        if has_auto_vars:
            self.script_file = None
            self.script_data = data
        else:
            self.script_file = self.write_script_file(
                str_formatter.format_list(data)
            )
            # self.script_data = None  # already set
        # --

        self.init_base_cmdv_scan_auto_vars(
            base_cmdv, str_formatter=str_formatter
        )

        return []
    # --- end of init_from_settings (...) ---

    def init_from_def(self, source_def):
        super().init_from_def(source_def)

        if "path" in source_def:
            self.script_file = source_def["path"]

        source_def_cmdv = source_def.get("command")  # ref-copy!
        if source_def_cmdv:
            # this is not really required since no other object uses the
            # source_def, but stay safe and copy source_def_cmdv
            base_cmdv = list(source_def_cmdv)

        else:
            # use the calling convention of the original project
            base_cmdv = [
                "{script_file}",      # 0: the script file to be executed
                "{outconfig}",        # 1: the output config file
                "{param_arch}",       # 2: target arch
                "{kmaj}.{kpatch}"     # 3: kernel version $KMAJ.$KPATCH
            ]

            # all parameters (except for target arch, see above)
            base_cmdv.extend((
                "{{param_{!s}}}".format(param)
                for param in sorted(self.arg_parser.source_params)
                if param != "arch"
            ))
        # --

        self.init_base_cmdv_scan_auto_vars(base_cmdv)
    # --- end of init_from_def (...) ---

    def create_cmdv(self, arg_config):
        if not arg_config.script_file:
            raise exc.ConfigurationSourceInvalidError("no script file")

        cmdv = []
        cmdv.extend(self.base_cmdv)

        if arg_config.argv:
            cmdv.extend(arg_config.argv)

        return self.format_cmdv(arg_config, cmdv)
    # --- end of create_cmdv (...) ---

    def do_parse_source_argv(self, argv):
        arg_config = super().do_parse_source_argv(argv)

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
                # this should have been catched by check_source_valid() already
                raise exc.ConfigurationSourceInvalidError("no script data")

            str_formatter = self.get_dynamic_str_formatter(arg_config)
            arg_config.script_file = self.write_script_file(
                str_formatter.format_list(self.script_data)
            )

            if not self.interpreter:
                # make it executable
                os.chmod(arg_config.script_file, stat.S_IRWXU)
            # --
        # --

        # script_file format var can only be set after assigning script_file
        arg_config.fmt_vars[self.SCRIPT_FILE_FMT_VARNAME] = (
            arg_config.script_file
        )
    # --- end of do_prepare (...) ---

# --- end of ScriptConfigurationSource ---
