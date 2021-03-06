# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import lookup

__all__ = []

if __name__ == "__main__":
    # $ python -m kernelconfig.kernel.hwdetection.modalias <modalias> ...
    #
    # or
    #
    # $ find /sys -name modalias | \
    #       xargs python -m kernelconfig.kernel.hwdetection.modalias -F
    #
    def main():
        import os
        import argparse

        def get_arg_parser():
            arg_parser = argparse.ArgumentParser()

            arg_parser.add_argument(
                "-M", "--modules-dir",
                default="/lib/modules/{!s}".format(os.uname().release)
            )

            arg_parser.add_argument(
                "-F", "--files", default=False, action="store_true"
            )

            arg_parser.add_argument(
                "-a", "--all", dest="show_all",
                default=False, action="store_true"
            )

            arg_parser.add_argument("modaliases", nargs="*")
            return arg_parser
        # ---

        arg_parser = get_arg_parser()
        arg_config = arg_parser.parse_args()

        mod_lookup = lookup.ModaliasLookup(arg_config.modules_dir)

        do_lookup = (
            mod_lookup.lookup_from_file if arg_config.files
            else mod_lookup.lookup
        )

        for arg in arg_config.modaliases:
            modules = do_lookup(arg)
            if modules or arg_config.show_all:
                print("{!s}: {!r}".format(arg, sorted(modules)))
    # ---

    try:
        main()
    except BrokenPipeError:
        pass
# -- end if __main__
