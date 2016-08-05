# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...kernel.hwdetection import detector

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

    def __init__(self, *, modules_dir=True, **kwargs):
        self._config = {
            "modules_dir": modules_dir
        }
        super().__init__(**kwargs)

# ---
