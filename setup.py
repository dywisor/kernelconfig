#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path
import distutils.core
import distutils.command.build
import distutils.command.build_py

class ProjectSetup(object):
    PRJ_NAME = "kernelconfig"
    PYM_NAME = PRJ_NAME

    @classmethod
    def pym_name(cls, sub_mod):
        return ".".join((cls.PYM_NAME, sub_mod)) if sub_mod else cls.PYM_NAME

    @classmethod
    def pym_names(cls, *sub_mods):
        return [cls.pym_name(sub_mod) for sub_mod in sub_mods]

    @classmethod
    def setup(cls):
        kernelconfig_lkconfig_pyext = distutils.core.Extension(
            cls.pym_name("kconfig.lkconfig"),
            sources = (
                [
                    "src/lkconfig.c",
                    "src/lkc/zconf.tab.c",
                ]
            ),
            extra_compile_args = ["-Wall"]
        )

        distutils.core.setup(
            name        = cls.PRJ_NAME,
            version     = "0.1",
            license     = "GPLv2",
            ext_modules = [kernelconfig_lkconfig_pyext],
            packages    = cls.pym_names(
                None,
                "abc",
                "installinfo",
                "kernel",
                "kconfig",
                "kconfig.abc",
                "kconfig.config",
                "lang",
                "scripts",
                "util"
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
        install_info_dir = os.path.join(
            self.build_lib, ProjectSetup.PYM_NAME, "installinfo"
        )
        install_info_file = os.path.join(install_info_dir, "_info.py")

        self.mkpath(install_info_dir)
        self.copy_file(self.get_install_info_infile(), install_info_file)
        self.byte_compile([install_info_file])

    def run(self):
        self.build_generated_files()
        super().run()
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
