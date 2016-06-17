#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys


def check_pydeps():
    try:
        import toposort
    except ImportError:
        sys.stderr.write("'toposort' module is missing.")

    try:
        import ply.lex
    except ImportError:
        sys.stderr.write("'PLY' module is missing.")


def run_setup_py(setup_file, build_dir, build_pym_dir):
    subprocess.check_call(
        [
            sys.executable, setup_file, "-q", "build",
            "-b", build_dir, "--build-lib", build_pym_dir
        ]
    )


def main():
    prjname = "kernelconfig"

    check_pydeps()

    # get the project root directory
    script_file = os.path.realpath(sys.argv[0])
    if not script_file:
        sys.exit(1)

    prjroot = os.path.dirname(script_file)
    get_prjfile = lambda *a: os.path.join(prjroot, *a)

    # identify the root directory / check for representative dirs/files
    if not os.path.isdir(get_prjfile(prjname)):
        sys.exit(9)

    setup_file = get_prjfile("setup.py")
    if not os.path.isfile(setup_file):
        sys.exit(9)

    # get build directory
    py_build_root = (
        os.environ.get("PY_BUILDDIR") or get_prjfile("build")
    )

    py_build_dir = os.path.join(
        py_build_root,
        "{}-standalone".format(prjname),
        "{v.major}.{v.minor}.{v.micro}".format(v=sys.version_info)
    )
    py_build_pym = os.path.join(py_build_dir, "pym")

    run_setup_py(setup_file, py_build_dir, py_build_pym)

    # add py_build_pym to sys.path, with higher priority than $PWD
    #  (which is important if $PWD is prjroot,
    #  because the Python/C-based mdoules are not in $PWD/kernelconfig)
    sys.path[:0] = [py_build_pym]

    # run the real main script
    import kernelconfig.scripts.main
    kernelconfig.scripts.main.KernelConfigMainScript.run_main()
# --- end of main (...) ---

if __name__ == "__main__":
    main()
