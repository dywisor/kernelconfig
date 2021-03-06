#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import distutils.core
import distutils.command.build
import distutils.command.build_py


class ProjectSetup(object):
    PRJ_NAME = "kernelconfig"
    PYM_NAME = PRJ_NAME
    PRJ_VER  = "1.0_alpha1"

    @classmethod
    def pym_name(cls, sub_mod):
        return ".".join((cls.PYM_NAME, sub_mod)) if sub_mod else cls.PYM_NAME

    @classmethod
    def pym_names(cls, *sub_mods):
        return [cls.pym_name(sub_mod) for sub_mod in sub_mods]

    @classmethod
    def get_ext_modules(cls):
        lkconfig_src = "src"

        # get_lkconfig_src(name):  lkconfig_src "/" name
        get_lkconfig_src = lambda n, *, s=lkconfig_src: os.path.join(s, n)

        lkc_src_from_env = os.getenv("LKCONFIG_LKC")
        if lkc_src_from_env:
            lkc_src = os.path.realpath(lkc_src_from_env)
        else:
            lkc_src = get_lkconfig_src("lkc")

        # get_lkc_src(name):  lkc_src "/" name
        get_lkc_src = lambda n, *, s=lkc_src: os.path.join(s, n)

        if os.path.isabs(lkc_src):  # equiv if lkc_src_from_env
            _get_lkc_src_include = get_lkc_src
        else:
            _get_lkc_src_include = lambda n, *, b=lkconfig_src: \
                os.path.relpath(get_lkc_src(n), b)
        # --

        # get_lkc_src_include(name):  "\"" lkc_src "/" name "\""
        get_lkc_src_include = lambda n: "\"%s\"" % _get_lkc_src_include(n)

        kernelconfig_lkconfig_pyext = distutils.core.Extension(
            cls.pym_name("kconfig.lkconfig"),
            sources = (
                [
                    get_lkconfig_src("lkconfig.c"),
                    get_lkc_src("zconf.tab.c"),
                ]
            ),
            extra_compile_args = ["-Wall"],
            define_macros = [
                ("LKCONFIG_LKC", get_lkc_src_include("lkc.h"))
            ]
        )

        return [kernelconfig_lkconfig_pyext]
    # ---

    @classmethod
    def setup(cls):
        scripts_dir = os.path.join("files", "scripts")

        distutils.core.setup(
            name        = cls.PRJ_NAME,
            version     = cls.PRJ_VER,
            license     = "GPLv2",
            ext_modules = cls.get_ext_modules(),
            scripts     = [os.path.join(scripts_dir, "kernelconfig")],
            packages    = cls.pym_names(
                None,
                "abc",
                "_base",
                "installinfo",
                "kernel",
                "kernel.hwdetection",
                "kernel.hwdetection.modalias",
                "kernel.hwdetection.modalias.abc",
                "kernel.hwdetection.modalias.cachedir",
                "kernel.hwdetection.modulesmap",
                "kernel.hwdetection.modulesmap.mkscanner",
                "kconfig",
                "kconfig.abc",
                "kconfig.config",
                "pm",
                "pm.portagevdb",
                "scripts",
                "sources",
                "sources.abc",
                "sources._util",
                "sources.source",
                "util"
            ),
            py_modules = cls.pym_names(
                "lang.lexer",
                "lang.parser",
                "lang.interpreter",
                "lang.cond"
            ),
            cmdclass={
                "build": genfiles_build,
                "build_py": genfiles_build_py
            }
        )
# ---

class genfiles_build_py(distutils.command.build_py.build_py):

    user_options = (
        distutils.command.build_py.build_py.user_options
        + [
            ("standalone", None, "build for standalone mode")
        ]
    )

    boolean_options = (
        distutils.command.build_py.build_py.boolean_options
        + ["standalone"]
    )

    def write_py_file_header(self, fh):
        fh.write(
            '# This file is part of kernelconfig.\n'
            '# -*- coding: utf-8 -*-\n'
        )
    # ---

    def initialize_options(self):
        self.standalone = None
        super().initialize_options()

    def finalize_options(self):
        self.set_undefined_options("build", ("standalone", "standalone"))
        super().finalize_options()

    def get_install_info_infile(self):
        if self.standalone:
            return os.path.join("files", "installinfo", "standalone.py")
        else:
            return os.path.join("build", "installinfo.py")

    def build_generated_files(self):
        def build_installinfo():
            nonlocal gen_files
            install_info_dir = os.path.join(
                self.build_lib, ProjectSetup.PYM_NAME, "installinfo"
            )
            install_info_file = os.path.join(install_info_dir, "_info.py")

            self.mkpath(install_info_dir)
            self.copy_file(self.get_install_info_infile(), install_info_file)
            gen_files.append(install_info_file)
        # ---

        def build_version():
            nonlocal gen_files

            def write_version(outfile):
                with open(outfile, "wt") as fh:
                    self.write_py_file_header(fh)
                    fh.write(
                        '\nversion = \"{ver!s}\"\n'.format(
                            ver=ProjectSetup.PRJ_VER
                        )
                    )
            # ---

            # mkdir not necessary
            version_info_file = os.path.join(
                self.build_lib, ProjectSetup.PYM_NAME, "_version.py"
            )
            self.execute(
                write_version,
                [version_info_file],
                msg="creating _version.py"
            )
            gen_files.append(version_info_file)
        # ---

        gen_files = []
        build_installinfo()
        build_version()
        self.byte_compile(gen_files)

    def build_parsetab(self):
        # COULDFIX: it would be possible to create parsetab.py
        #           without running a second Python interpreter process,
        #           but the relative imports make it quite tricky
        #
        #           (-- importlib.machinery.SourceLoader)
        #
        mkparsetab_script = os.path.join(
            os.path.dirname(sys.argv[0]),
            "build-scripts",
            "create-parsetab.py"
        )

        parsetab_dir = os.path.join(
            self.build_lib, ProjectSetup.PYM_NAME, "lang"
        )
        parsetab_file = os.path.join(parsetab_dir, "parsetab.py")

        if self.force or not os.access(parsetab_file, os.F_OK):
            self.execute(
                subprocess.check_call,
                [
                    [
                        sys.executable,
                        mkparsetab_script,
                        self.build_lib,
                        ProjectSetup.pym_name("lang.parser")
                    ]
                ],
                msg="creating parsetab"
            )
        # --
        self.byte_compile([parsetab_file])

    def run(self):
        self.build_generated_files()
        super().run()
        self.build_parsetab()
# ---


class genfiles_build(distutils.command.build.build):

    user_options = (
        distutils.command.build.build.user_options
        + [
            ("standalone", None, "build for standalone mode")
        ]
    )

    boolean_options = (
        distutils.command.build.build.boolean_options
        + ["standalone"]
    )

    def initialize_options(self):
        self.standalone = None
        super().initialize_options()
# ---


ProjectSetup.setup()
