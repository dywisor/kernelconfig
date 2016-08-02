# This file is part of kernelconfig.
# -*- coding: utf-8 -*-
#
# Usage: python -m kernelconfig.pm.portagevdb [...]
#

from . import base


def main():
    import argparse
    import os.path
    import sys

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

        return arg_parser
    # ---

    arg_parser = get_arg_parser()
    arg_config = arg_parser.parse_args()

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
    else:
        raise NotImplementedError(arg_config.command)
# --- end of main (...) ---

if __name__ == "__main__":
    main()
