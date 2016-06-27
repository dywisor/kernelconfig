# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os

from ..abc import source as _source_abc
from ..abc import exc

from ...util import subproc
from ...util import fs


__all__ = ["MakeConfigurationSource"]


class MakeConfigurationSource(_source_abc.AbstractConfigurationSource):

    def get_configuration_basis(self, csenv, subtype, args):
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

        cmdv = ["make", "-C", csenv.source_info.get_filepath()]
        cmdv.extend((
            "{}={}".format(k, v)
            for k, v in csenv.source_info.iter_make_vars()
        ))

        argv = []
        if subtype is not None:
            argv.append(subtype)

        argv.extend(args)
        if not argv:
            argv.append("defconfig")
        # --

        # TODO:
        # if source_info.supports_out_of_tree_build():
        #    make O=csenv.get_tmpdir().get_new_subdir()
        #

        cfg_file = csenv.source_info.get_filepath(".config")

        fs.prepare_output_file(cfg_file, move=True)
        # be *extra* sure that cfg_file does not exist
        try:
            os.unlink(cfg_file)
        except OSError:
            if os.path.lexists(cfg_file):
                raise

        with subproc.SubProc(cmdv + argv, logger=self.logger) as proc:
            if not proc.join():
                raise exc.ConfigurationSourceError("make-config failed")
        # --

        if not os.path.isfile(cfg_file):
            raise exc.ConfigurationSourceError(
                "make command did not create .config file"
            )

        return cfg_file
    # ---
# --- end of MakeConfigurationSource ---
