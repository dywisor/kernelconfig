# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...kernel.hwdetection import detector
from ...pm.portagevdb import integrator
from ...util import tmpdir as _tmpdir

from ..abc import choicemodules as _choicemodules_abc


__all__ = ["KernelConfigChoiceModules"]


class _ConfigChoiceModules(_choicemodules_abc.AbstractChoiceModules):
    __slots__ = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_default_modules()

    def register_default_modules(self):
        for name in dir(self):
            if name.startswith("create_dynamic_module_"):
                module_name = name[22:]  # len(^)
                # constructor is bound at __init__ time,
                # rebinding the method after register_default_modules()
                # will have no effect.
                # OTOH, this is consistent with "for _ in dir(self)",
                # which operates on what is currently bound.
                #
                constructor = getattr(self, name)
                self.register_module(
                    module_name, True, constructor, None, None
                )
    # ---

    def create_dynamic_module(
        self, module_name, module_constructor, module_args, module_kwargs
    ):
        self.logger.debug(
            "Initializing dynamic config choices module: %s", module_name
        )
        return module_constructor(*module_args, **module_kwargs)
    # --- end of create_dynamic_module (...) ---

# ---


class KernelConfigChoiceModules(_ConfigChoiceModules):

    def __init__(
        self, *, modules_dir=True, tmpdir=None, parent_tmpdir=None, **kwargs
    ):
        self._config = {
            "modules_dir": modules_dir
        }

        if tmpdir is None and parent_tmpdir is None:
            self._tmpdir = None
        else:
            self._tmpdir = _tmpdir.get_tmpdir_or_view(tmpdir, parent_tmpdir)

        super().__init__(**kwargs)

    def get_tmpdir(self):
        tmpdir = self._tmpdir
        if tmpdir is None:
            tmpdir = _tmpdir.Tmpdir()
            self._tmpdir = tmpdir
        return tmpdir

    def create_dynamic_module_hwdetector(self):
        # NOTE: changes to _config will not affect already loaded modules
        return self.create_informed(
            detector.HWDetect, modules_dir=self._config["modules_dir"]
        )

    def create_dynamic_module_pm(self):
        return self.create_informed(
            integrator.PMIntegration, parent_tmpdir=self.get_tmpdir()
        )

# ---
