#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
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
# ---


def run_setup_py(prjroot, setup_file, build_dir, build_pym_dir, force=False):
    cmdv = [
        sys.executable, setup_file, "-q", "build",
        "-b", build_dir, "--build-lib", build_pym_dir,
        "--standalone"
    ]
    if force:
        cmdv.append("--force")

    subprocess.check_call(cmdv, cwd=prjroot)
# ---


def setup_lkconfig_lkc_env_var(arg_config, *, varname="LKCONFIG_LKC"):
    if hasattr(arg_config, "lkc_src"):
        os.environ[varname] = arg_config.lkc_src

    elif varname in os.environ:
        pass

# %%%autoset LKC_SRC from srctree
#    elif getattr(arg_config, "srctree", None):
#        lkc_src = os.path.join(arg_config.srctree, "scripts", "kconfig")
#        if os.path.isdir(lkc_src):
#            os.environ[varname] = lkc_src
# ---


def main():
    def arg_is_dir(arg):
        if arg:
            fspath = os.path.realpath(arg)
            if os.path.isdir(fspath):
                return fspath
        # --
        raise argparse.ArgumentTypeError()
    # ---

    with_default = lambda h, d=None: (
        "%s\n (default: %s)" % (h, ("%(default)s" if d is None else d))
    )

    prjname = "kernelconfig"

    check_pydeps()
    # Note: "all unknown args passed to main" is not strictly correct,
    #       the argparse consumes all options that are a substring
    #       of any known arg.
    #       So, anything starting with "--w" will be parsed and
    #       might produce a usage error.
    #
    #       In Python >= 3.5, it is possible to disable this behavior.
    #
    #       FIXME: investigate whether there's sth. equivalent for 3.4
    #
    arg_parser_kwargs = {}
    if sys.hexversion >= 0x3050000:
        arg_parser_kwargs["allow_abbrev"] = False

    arg_parser = argparse.ArgumentParser(
        description=(
            'kernelconfig standalone wrapper\n'
            '\n'
            'Runs \'setup.py build\' and then the main script.\n'
            'All unknown arguments are passed to the main script.\n'
            '\n'
            'Example usage: %(prog)s -k /usr/src/linux\n'
        ),
        add_help=False,
        formatter_class=argparse.RawTextHelpFormatter,
        **arg_parser_kwargs
    )

    arg_parser.add_argument(
        "--wrapper-help", action="help",
        help="show this help message and exit"
    )
    arg_parser.add_argument(
        "--wrapper-prjroot", dest="prjroot", default=None,
        help=with_default(
            "path to the project's root directory",
            "dir containing this script"
        )
    )
    arg_parser.add_argument(
        "--wrapper-build-base", dest="build_base", default=None,
        help=with_default(
            "build files root directory",
            "$PY_BUILDDIR or <PRJROOT>/build"
        )
    )
    arg_parser.add_argument(
        "--wrapper-lkc",  dest="lkc_src",
        default=argparse.SUPPRESS,
        type=lambda w: (arg_is_dir(w) if w else ""),
        help=with_default(
            "lkc source directory",
            "$LKCONFIG_LKC or <PRJROOT>/src/lkc"
        )
    )
# %%%autoset LKC_SRC from srctree
#    arg_parser.add_argument(
#        "-k", "--kernel", dest="srctree",
#        default=argparse.SUPPRESS, type=arg_is_dir,
#        help=(
#            'path to the unpacked kernel sources directory,\n'
#            'used for getting LKC_SRC automatically,\n'
#            'will be forwarded to the main script'
#        )
#    )

    arg_parser.add_argument(
        "--wrapper-rebuild", dest="rebuild",
        default=False, action="store_true",
        help=with_default(
            "force rebuilding of all Python modules", "disabled"
        )
    )

    # add "..." to the end of the usage string,
    # indicating how to specify args for the real main script
    arg_parser.usage = "%s ...\n\n" % arg_parser.format_usage().rstrip()

    arg_config, main_argv = arg_parser.parse_known_args()
# %%%autoset LKC_SRC from srctree
#    if hasattr(arg_config, "srctree"):
#        # push back deduplicated --kernel, -k
#        main_argv.extend(["-k", arg_config.srctree])


    prjroot = arg_config.prjroot
    if not prjroot:
        # get the project root directory
        script_file = os.path.realpath(sys.argv[0])
        if not script_file:
            sys.exit(1)

        prjroot = os.path.dirname(script_file)
    # --

    get_prjfile = lambda *a: os.path.join(prjroot, *a)

    # identify the root directory / check for representative dirs/files
    if not os.path.isdir(get_prjfile(prjname)):
        sys.exit(9)

    setup_file = get_prjfile("setup.py")
    if not os.path.isfile(setup_file):
        sys.exit(9)

    py_build_root = arg_config.build_base
    if not py_build_root:
        # get build directory
        py_build_root = (
            os.environ.get("PY_BUILDDIR") or get_prjfile("build")
        )
    # --

    py_build_dir = os.path.join(
        py_build_root,
        "{}-standalone".format(prjname),
        "{v.major}.{v.minor}.{v.micro}".format(v=sys.version_info)
    )
    py_build_pym = os.path.join(py_build_dir, "pym")

    setup_lkconfig_lkc_env_var(arg_config)

    run_setup_py(
        prjroot, setup_file,
        py_build_dir, py_build_pym, force=arg_config.rebuild
    )

    # add py_build_pym to sys.path, with higher priority than $PWD
    #  (which is important if $PWD is prjroot,
    #  because the Python/C-based modules are not in $PWD/kernelconfig)
    sys.path[:0] = [py_build_pym]

    # make the prjroot available via os.environ,
    #  important for relpath file lookups
    os.environ["KERNELCONFIG_PRJROOT"] = prjroot

    # run the real main script
    import kernelconfig.scripts.main
    kernelconfig.scripts.main.KernelConfigMainScript.run_main(argv=main_argv)
# --- end of main (...) ---

if __name__ == "__main__":
    main()
