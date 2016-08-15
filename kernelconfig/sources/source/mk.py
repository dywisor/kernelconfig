# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _sourcebase
from ..abc import exc


__all__ = ["MakeConfigurationSource"]


class MakeConfigurationSource(_sourcebase.CommandConfigurationSourceBase):
    """
    Configuration source that creates a .config file with "make <target>".
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_argv = None
        self.make_target = None

    def check_source_valid(self):
        if not self.make_target:
            raise exc.ConfigurationSourceInvalidError("no make target")
    # --- end of check_source_valid (...) ---

    def _set_base_argv(self, base_argv):
        self.base_argv = list(base_argv) if base_argv else []
        self.scan_auto_vars_must_exist(self.base_argv)
    # ---

    def _set_make_target(self, subtype, name):
        make_target = None

        if subtype == "defconfig":
            # FIXME: for defconfig,
            #        this needs some investigation and minor changes
            #
            #        If an arch has more than one defconfig,
            #        it would good to choose the best-fitting one!
            #
            if not name:
                make_target = subtype

            else:
                raise NotImplementedError("defconfig with variant name")

        elif subtype:
            raise exc.ConfigurationSourceInvalidError(
                "unknown make subtype {!r}".format(subtype)
            )

        elif name:
            make_target = name

        # else keep make_target==None

        self.make_target = make_target
        if make_target:
            self.scan_auto_vars_must_exist([make_target])
    # --- end of _set_make_target (...) ---

    def init_from_settings(self, subtype, args, data):
        if data:
            raise exc.ConfigurationSourceInvalidError("non-empty data")
        # --

        # FIXME:
        # if subtype == defconfig or not subtype:
        #    get defconfig name from source info
        #     args may contain further specifications of the defconfig
        #     or a target name
        #
        #  else
        #     error
        #  end if

        if subtype:
            self._set_make_target(subtype, None)
            args_rem = args
        else:
            raise NotImplementedError("more advanced make target")
            args_rem = None
        # --

        self._set_base_argv(args_rem)
        return []
    # --- end of init_from_settings (...) ---

    def init_from_def(self, source_def):
        super().init_from_def(source_def)

        source_type = source_def.get_source_type()

        self._set_make_target(
            source_type.source_subtype, source_def.get("target")
        )
        self._set_base_argv(source_def.get("command"))
    # --- end of init_from_def (...) ---

    def add_auto_var(self, varname, varkey):
        # does not support auto vars
        return False

    def do_init_env(self, arg_config):
        # does not make use of the default env vars
        return False

    def do_parse_source_argv(self, argv):
        # pylint: disable=E1101
        arg_config = super().do_parse_source_argv(argv)

        arg_config.out_of_tree = (  # new attr
            self.senv.source_info.check_supports_out_of_tree_build()
        )

        if arg_config.out_of_tree:
            arg_config.add_tmp_outfile(".config")
        else:
            arg_config.add_outfile(
                self.senv.source_info.get_filepath(".config")
            )

        return arg_config
    # ---

    def create_cmdv(self, arg_config):
        def gen_make_var_args(mvar_items):
            for vname, val in mvar_items:
                yield "{!s}={!s}".format(vname, val)
        # ---

        def add_make_vars(mvar_items):
            nonlocal cmdv
            cmdv.extend(gen_make_var_args(mvar_items))
        # --

        str_formatter = self.get_dynamic_str_formatter(arg_config)

        # make -C <srctree>
        cmdv = ["make", "-C", self.senv.source_info.get_filepath()]
        #  + base argv
        if self.base_argv:
            cmdv.extend(str_formatter.format_list(self.base_argv))

        #  + make target
        cmdv.append(str_formatter.format(self.make_target))

        #  + ARCH=...,
        add_make_vars(self.senv.source_info.iter_make_vars())

        if arg_config.out_of_tree:
            #  + O= ...
            add_make_vars(
                self.senv.source_info.iter_out_of_tree_build_make_vars(
                    arg_config.tmpdir_path
                )
            )
        # --

        #  + arg_config.argv (if non-empty)
        if arg_config.argv:
            cmdv.extend(arg_config.argv)

        return cmdv
    # ---
# --- end of MakeConfigurationSource ---
