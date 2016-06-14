#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import logging

import kernelconfig.kernel.info
import kernelconfig.kconfig.symbolgen
import kernelconfig.kconfig.config.data
import kernelconfig.kconfig.config.choices
import kernelconfig.lang.interpreter


def setup_console_logging(logger, outstream=None, log_level=logging.DEBUG):
    streamhandler = logging.StreamHandler(
        sys.stdout if outstream is None else outstream
    )
    streamhandler.setLevel(log_level)

    streamhandler.setFormatter(
        logging.Formatter(fmt="%(levelname)-8s [%(name)s] %(message)s")
    )

    logger.addHandler(streamhandler)
    logger.setLevel(log_level)
# ---


if __name__ == "__main__":
    import argparse
    import os.path

    setup_console_logging(logging.getLogger())

    arg_parser = argparse.ArgumentParser("preliminary main script")
    # currently,
    #  all of srctree, arch, srcarch and kernelversion need to be specified
    arg_parser.add_argument("-S", "--kernel-src", default="/usr/src/linux")
    arg_parser.add_argument("-A", "--arch", default=None)
    arg_parser.add_argument("-C", "--config", default=None)

    arg_config = arg_parser.parse_args()

    kinfo = kernelconfig.kernel.info.KernelInfo(
        srctree=arg_config.kernel_src,
        arch=arg_config.arch
    )
    kinfo.prepare()

    kconfig_syms = (
        kernelconfig.kconfig.symbolgen.
        KconfigSymbolGenerator(kinfo).get_symbols()
    )

    cfg = kernelconfig.kconfig.config.data.KernelConfig(kconfig_syms)
    cfg.read_config_file(
        arg_config.config or os.path.join(kinfo.srctree, ".config")
    )

    cc = kernelconfig.kconfig.config.choices.ConfigChoices(cfg)

    cl = cc.create_loggable(
        kernelconfig.lang.interpreter.KernelConfigLangInterpreter,
        kinfo,
        cc
    )
    cl.process_str("ym CONFIG_E1000E")

    cc.option_module("CONFIG_E1000E")
    cc.option_builtin_or_module("DVB_DDBRIDGE")
    cc.option_append("CONFIG_CMDLINE", "panic=10")

    cc.commit()

    cfg.write_config_file(kinfo.get_filepath("outconfig"))
