# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections.abc
import os.path


from . import parser

__all__ = [
    "ConfigOptionConditionContext",
    "IncludeFileConditionContext"
]


class BaseConditionContext(collections.abc.Mapping):

    @abc.abstractproperty
    def COND_OPS(cls):
        """
        A list of conditional operations that are supported by this context
        (as condop opcodes).
        """
        return []

    @abc.abstractmethod
    def get_context_desc(self):
        raise NotImplementedError()

    def __init__(self):
        super().__init__()
        self._evaluators = {
            op: getattr(self, "eval_" + op.name) for op in self.COND_OPS
        }
        self.reset()

    def reset(self):
        pass

    @abc.abstractmethod
    def bind(self, *args, **kwargs):
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.reset()

    def __contains__(self, op):
        return op in self._evaluators

    def __getitem__(self, op):
        return self._evaluators[op]

    def __iter__(self):
        return iter(self._evaluators)

    def __len__(self):
        return len(self._evaluators)

    def __call__(self, cond_type, cond_func, cond_args):
        return self._evaluators[cond_type](cond_func, cond_args)

    def eval_condop_hwmatch(self, cond_func, args):
        return True

# --- end of BaseConditionContext ---


class ConfigOptionConditionContext(BaseConditionContext):

    COND_OPS = [
        parser.KernelConfigOp.condop_exists,
        # parser.KernelConfigOp.condop_hwmatch,
    ]

    def get_context_desc(self):
        return "config option"

    def __init__(self, config_choices, **kwargs):
        super().__init__(**kwargs)
        self.config_choices = config_choices

    def reset(self):
        self.config_option = None

    def bind(self, config_option):
        self.config_option = config_option
        return self

    def eval_condop_exists(self, cond_func, arg):
        if arg is None:
            config_option = self.config_option
            return (
                True, bool(self.config_choices.find_option(config_option))
            )

        else:
            return (
                False, self.config_choices.has_option(arg)
            )
    # ---

# --- end of ConfigOptionConditionContext ---


class IncludeFileConditionContext(BaseConditionContext):

    COND_OPS = [
        parser.KernelConfigOp.condop_exists,
        # # parser.KernelConfigOp.condop_hwmatch,
    ]

    def get_context_desc(self):
        return "include-file"

    def reset(self):
        self.include_file = None

    def bind(self, include_file):
        self.include_file = include_file
        return self

    def eval_condop_exists(self, cond_func, arg):
        if arg is None:
            include_file = self.include_file
            dynamic = True
        else:
            include_file = arg
            dynamic = False

        return (
            dynamic,
            (include_file and os.path.exists(include_file))
        )
    # ---

# --- end of IncludeFileConditionContext ---


# class HardwareDetectionConditionContext(BaseConditionContext):
#
#     COND_OPS = []
#
#     def get_context_desc(self):
#         return "hardware-detection"
#
#     def bind(self):
#         return self
#
# # --- end of HardwareDetectionConditionContext ---
