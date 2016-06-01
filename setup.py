#!/usr/bin/env python
# -*- coding: utf-8 -*-

import distutils.core


kernelconfig_lkconfig_pyext = distutils.core.Extension(
    "kernelconfig.kconfig.lkconfig",
    sources = (
        [
            "src/lkconfig.c",
            "src/lkc/zconf.tab.c",
        ]
    ),
    extra_compile_args = ["-Wall"]
)


distutils.core.setup(
    name        = "kernelconfig",
    version     = "0.1",
    license     = "GPLv2",
    ext_modules = [kernelconfig_lkconfig_pyext],
    packages    = [
        "kernelconfig",
        "kernelconfig.abc",
        "kernelconfig.kernel",
        "kernelconfig.kconfig",
        "kernelconfig.kconfig.abc",
        "kernelconfig.kconfig.config",
        "kernelconfig.util",
    ]
)
