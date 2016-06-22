#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This script imports kernelconfig's lang parser
# and instructs it to build the parsetab.py file.
#
# Usage: create-parsetab <build lib> <parser module name>
#
# Note: <parser module name> must exist in <build lib>
#
import importlib
import os
import sys

if __name__ == "__main__":
    def main():
        if (
            len(sys.argv) != 3
            or not os.path.isdir(sys.argv[1])
        ):
            sys.stderr.write("Bad usage!\n")
            sys.exit(1)
        # --

        # add <build lib> to sys.path, giving it the highest priority
        sys.path[:0] = [sys.argv[1]]

        # import <parser module name>
        parser_mod = importlib.import_module(sys.argv[2])

        # build the parser
        parser_mod.build_parser()
    # --- end of __main__ (...) ---

    main()
# -- end if __main__
