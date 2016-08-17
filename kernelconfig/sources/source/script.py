# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import stat

from . import _sourcebase
from ..abc import exc

__all__ = ["ScriptConfigurationSource"]


class ScriptConfigurationSource(_sourcebase.CommandConfigurationSourceBase):
    """
    This configuration source runs a script that creates the config basis.

    Depending on the init_from_() type,
    the script may be a file and or data (text lines).

    When initialized from the settings file, the script must exist as "data",
    and the text lines are embedded into the [source] section,
    beginning at the second non-empty, non-comment line.
    The text lines are subject to string formatting and a temporary script
    file is generated during init_from_settings() if it does not contain
    "automatic format variables". In that case, individual tmpfiles
    are generated during each get_configuration_basis() cycle.

    When initialized as "curated source" (from source def and/or script),
    the script must be an existing file.

    @cvar SCRIPT_FILE_FMT_VARNAME:       name of the format variable that
                                         references the script file
                                         Used in the base command (base_cmdv)
                                         to reference the not-yet-existing
                                         script file.
    @type SCRIPT_FILE_FMT_VARNAME:       C{str}

    @cvar SCRIPT_FILE_FMT_VAR_TEMPLATE:  script file format variable
                                         including braces ("{...}")
                                         (readonly property)
    @type SCRIPT_FILE_FMT_VAR_TEMPLATE:  C{str}

    @cvar DEFAULT_SCRIPT_CALLING_CONVENTION:  default argument list
                                              passed to curated sources
                                              (unless defined otherwise)
                                              May contain format variables.
                                              Used in init_from_def() only.
    @type DEFAULT_SCRIPT_CALLING_CONVENTION:  C{tuple} of C{str}


    @ivar base_cmdv:        the base command for running the script (file).
                            If an interpreter is to be used,
                            it should be included in the base command.

                            subject to string formatting,
                            the complete command is base_cmdv
                            + args passed to get_configuration_basis()
    @type base_cmdv:        C{None} or C{list} of C{str}

    @ivar has_interpreter:  whether the script's base command includes
                            an interpreter (e.g. "sh") or not.
                            This has an effect on whether the script file
                            must be executable or not.
    @type has_interpreter:  C{None} or C{bool}

    @ivar script_file:      path to the script file if known, None otherwise

                            Should only be set if the script file exists.
                            If script_file is None, script_data must be set.

                            When deciding whether to use the script file
                            or generate a new one from script_data, the
                            existing file takes precedence over script_data.
    @type script_file:      C{None} or C{str}

    @ivar script_data:      either None or the script in form of text lines
    @type script_data:      C{None} or C{list} of C{str}
    """

    # the script calling convention of the original project
    DEFAULT_SCRIPT_CALLING_CONVENTION = (
        "{outconfig}",        # 1: the output config file
        "{param_arch}",       # 2: target arch
        "{kmaj}.{kpatch}"     # 3: kernel version $KMAJ.$KPATCH
    )

    SCRIPT_FILE_FMT_VARNAME = "script_file"

    @property
    def SCRIPT_FILE_FMT_VAR_TEMPLATE(self):
        return "{" + self.SCRIPT_FILE_FMT_VARNAME + "!s}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_interpreter = None
        self.base_cmdv = None
        self.script_file = None
        self.script_data = None

    def check_source_valid(self):
        # script_file not set => script_data must be set
        if self.script_file is None:
            if self.script_data is None:
                raise exc.ConfigurationSourceInvalidError(
                    "script file is not set, and data neither"
                )

            # {script_file} in script_data needs to be checked in init_()

        # if script_file is set, it must exist
        elif not os.path.isfile(self.script_file):
            raise exc.ConfigurationSourceInvalidError(
                "script file {!r} does not exist or is not a file".format(
                    self.script_file
                )
            )

        # and be readable,
        # and also executable unless base_cmdv includes the interpreter
        elif not os.access(
            self.script_file,
            os.R_OK | (0 if self.has_interpreter else os.X_OK)
        ):
            raise exc.ConfigurationSourceInvalidError(
                "script file {!r} is not readable/executable".format(
                    self.script_file
                )
            )
        # --

        # the base command must not be empty
        if not self.base_cmdv:
            raise exc.ConfigurationSourceInvalidError("no command")
    # --- end of check_source_valid (...) ---

    def write_script_file(self, formatted_data):
        """
        Generates a temporary script file from formatted_data
        and returns its filesystem path.

        @param formatted_data:  formatted text lines
        @type  formatted_data:  C{list} of C{str}

        @return:  path to the temporary script file
        @rtype:   C{str}
        """
        script_filepath = None
        with self.senv.get_tmpdir().open_new_file(text=True) as tmpfile:
            tmpfile.fh.write("\n".join(formatted_data))
            tmpfile.fh.write("\n")
            script_filepath = tmpfile.path
        return script_filepath
    # --- end of write_script_file (...) ---

    def init_base_cmdv_scan_auto_vars(self, base_cmdv, str_formatter=None):
        """
        Scans the given base command for unknown (automatic) format variables,
        checks whether it includes the script file, and sets self.base_cmdv.

        @raises ConfigurationSourceInvalidError:

        @param   base_cmdv:
        @keyword str_formatter:  None or a str formatter, defaults to None

        @return:  None (implicit)
        """
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

    def get_subtype_base_cmdv(self, subtype):
        """
        Initializes a new base command from the given source "subtype".

        The returned command includes the script file referenced by its
        format variable name, and possibly a script interpreter (+ args).
        It can be modified freely (.append(), .extend()).

        @param subtype:  configuration source subtype, e.g. "sh"
        @type  subtype:  C{None} or C{str}

        @return:  2-tuple (has interpreter, new base command)
        @rtype:   2-tuple (C{bool}, C{list} of C{str})
        """
        if not subtype:
            return (False, [self.SCRIPT_FILE_FMT_VAR_TEMPLATE])

        elif subtype in {"sh", }:
            return (True, [subtype, self.SCRIPT_FILE_FMT_VAR_TEMPLATE])

        else:
            raise exc.ConfigurationSourceInvalidError(
                "unknown subtype {!r}".format(subtype)
            )
    # --- end of get_subtype_base_cmdv (...) ---

    def init_from_settings(self, subtype, args, data):
        """
        Condition:  data && (subtype || args),
                    data must be non-empty,
                    at least one of subtype or args must be non-empty

        @raises ConfigurationSourceInvalidError:

        @param subtype:  the configuration source's subtype,
                         denotes the interpreter to be used
                         If empty or None, args[0] will be used as interpreter.
        @type  subtype:  C{None} or C{list} of C{str}

        @param args:     additional args that will be appended to the
                         base command (args[0] may be special, see subtype)
        @type  args:     C{None} or C{list} of C{str}

        @param data:     the script's data (text lines)
        @type  data:     C{list} of C{str}

        @return:  None - all args are appended to the base command
        """
        super().init_from_settings(subtype, args, data)

        script_file_fmt_varname = self.SCRIPT_FILE_FMT_VARNAME

        if not data:
            raise exc.ConfigurationSourceInvalidError("empty data")
        # --

        if not subtype:
            if args:
                subtype = args[0]
                args = args[1:]

            if not subtype:
                raise exc.ConfigurationSourceInvalidError("empty subtype")
        # --

        has_ipret, base_cmdv = self.get_subtype_base_cmdv(subtype)
        self.has_interpreter = has_ipret

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

        return None  # no args remainder
    # --- end of init_from_settings (...) ---

    def init_from_def(self, source_def):
        super().init_from_def(source_def)

        source_type = source_def.get_source_type()

        if "path" in source_def:
            self.script_file = source_def["path"]

        source_def_cmdv = source_def.get("command")  # ref-copy!
        if source_def_cmdv:
            # a command has been specified, ignore subtype

            # this is not really required since no other object uses the
            # source_def, but stay safe and copy source_def_cmdv
            base_cmdv = list(source_def_cmdv)

        else:
            has_ipret, base_cmdv = self.get_subtype_base_cmdv(
                source_type.source_subtype
            )
            self.has_interpreter = has_ipret
            base_cmdv.extend(self.DEFAULT_SCRIPT_CALLING_CONVENTION)

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

            if not self.has_interpreter:
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
