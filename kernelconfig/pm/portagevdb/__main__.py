# This file is part of kernelconfig.
# -*- coding: utf-8 -*-
#
# Usage: python -m kernelconfig.pm.portagevdb [...]
#

from . import base
from . import overlay


def main():
    import logging
    import argparse
    import os.path
    import sys

    def setup_logging():
        console_log_fmt = "%(levelname)-8s [%(name)s] %(message)s"
        log_level = logging.DEBUG

        logger = logging.getLogger()

        streamhandler = logging.StreamHandler(sys.stderr)
        streamhandler.setLevel(log_level)

        streamhandler.setFormatter(logging.Formatter(fmt=console_log_fmt))

        logger.addHandler(streamhandler)
        logger.setLevel(log_level)
    # ---

    def get_arg_parser():
        prog = os.path.basename(sys.argv[0])
        if prog == "__main__.py":
            prog = "{} -m kernelconfig.pm.portagevdb".format(
                os.path.basename(sys.executable)
            )

        arg_parser = argparse.ArgumentParser(prog=prog)

        arg_parser.set_defaults(command=None)
        sub_parsers = arg_parser.add_subparsers(dest="command")

        config_check_arg_parser = sub_parsers.add_parser(
            "print-config-check",
            help=(
                'print the build-time value of CONFIG_CHECK'
                ' for packages inheriting linux-info.eclass'
            )
        )

        config_check_arg_parser.add_argument(
            "-a", "--all", dest="print_config_check_show_all",
            default=False, action="store_true",
            help="include packages with empty CONFIG_CHECK in output"
        )

        mkoverlays_arg_parser = sub_parsers.add_parser("mkoverlays")
        mkoverlays_arg_parser.add_argument(
            "overlays_rootdir",
            help="root directory of the to-be-created overlays"
        )

        return arg_parser
    # ---

    arg_parser = get_arg_parser()
    arg_config = arg_parser.parse_args()

    setup_logging()
    port_iface = base.PortageInterface()

    if not arg_config.command or arg_config.command == "print-config-check":
        # empty CONFIG_CHECK does *not* imply that
        # CONFIG_CHECK was empty at build time:
        #
        # * "local CONFIG_CHECK" in pkg_pretend()/pkg_setup()
        # * CONFIG_CHECK conditionally set,
        #   but no conditions were met
        #
        # Also, querying CONFIG_CHECK together with INHERITED takes *more* time
        # than querying CONFIG_CHECK afterwards for those packages that inherit
        # linux-info
        # (but that depends on how many of the installed pkgs use linux-info)
        #
        for cpv, config_check in port_iface.zipmap_get_var(
            port_iface.find_all_cpv_inheriting_linux_info(), "CONFIG_CHECK"
        ):
            if config_check or arg_config.print_config_check_show_all:
                cfg_opts = sorted(
                    port_iface.parse_config_check(config_check)
                )
                print(cpv, "::", cfg_opts)
        # --

    elif arg_config.command == "mkoverlays":
        ov_root = overlay.TemporaryOverlayUnion(arg_config.overlays_rootdir)

        for cpv in port_iface.find_all_cpv_inheriting_linux_info():
            pkg_info = port_iface.get_package_info(cpv)
            ov_root.add_package(pkg_info)
        # --

        ov_root.fs_init()
        ov_root.populate()
    else:
        raise NotImplementedError(arg_config.command)
# --- end of main (...) ---

if __name__ == "__main__":
    main()
