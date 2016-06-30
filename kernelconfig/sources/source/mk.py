# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _base
from ..abc import exc


__all__ = ["MakeConfigurationSource"]


class MakeConfigurationSource(_base.CommandConfigurationSourceBase):
    """
    Configuration source that creates a .config file with "make <target>".
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_argv = []
        self.make_target = None

    def init_from_settings(self, subtype, args, data):
        if data:
            raise exc.ConfigurationSourceInvalidError("non-empty data")
        # --

        # FIXME: for defconfig,
        #        this needs some investigation and minor changes
        #
        #        In kernelconfig, the meaning of "arch" is ambiguous:
        #        (a) the kernel arch, which is a 'simplification'
        #            of the target arch (e.g. "arm")
        #
        #        (b) the target arch (e.g. "armv5te")
        #
        #        If an arch has more than one defconfig,
        #        it would good to choose the best-fitting one!
        #

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
            self.make_target = subtype
            args_rem = args
        else:
            raise NotImplementedError("more advanced make target")
            args_rem = None
        # --

        return args_rem
    # --- end of __init__ (...) ---

    def add_auto_var(self, varname, varkey):
        # does not support auto vars
        return False

    def do_init_env(self, arg_config):
        # does not make use of the default env vars
        return False

    def do_parse_source_argv(self, argv):
        arg_config = _base.ConfigurationSourceArgConfig()
        arg_config.argv.extend(argv)

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

        # make -C <srctree>
        cmdv = ["make", "-C", self.senv.source_info.get_filepath()]
        #  + base argv
        cmdv.extend(self.base_argv)

        #  + make target
        cmdv.append(self.make_target)

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
