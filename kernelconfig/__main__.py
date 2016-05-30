#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import logging

import kernelconfig.kernel.info
import kernelconfig.kconfig.symbolgen
import kernelconfig.kconfig.config


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
    arg_parser.add_argument("-A", "--arch", default="x86_64")
    arg_parser.add_argument("-a", "--srcarch", default="x86")
    arg_parser.add_argument("-k", "--kernelversion", default="4.6.0")

    arg_parser.add_argument("-C", "--config", default=None)

    arg_config = arg_parser.parse_args()

    kinfo = kernelconfig.kernel.info.KernelInfo(
        srctree=arg_config.kernel_src,
        arch=arg_config.arch,
        srcarch=arg_config.srcarch,
        kernelversion=arg_config.kernelversion
    )

    kconfig_syms = (
        kernelconfig.kconfig.symbolgen.
        KconfigSymbolGenerator(kinfo).get_symbols()
    )

    cfg = kernelconfig.kconfig.config.KernelConfig(kconfig_syms)
    cfg.read_config_file(
        arg_config.config or os.path.join(kinfo.srctree, ".config")
    )
    cfg.write_config_file(
        sys.stdout
    )