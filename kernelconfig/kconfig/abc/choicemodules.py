# kernelconfig -- abstract description of Kconfig-related classes
# -*- coding: utf-8 -*-

import abc
import collections.abc
import itertools

from ...abc import informed
from ...util import misc


__all__ = [
    "AbstractChoiceModule",
    "AbstractChoiceModules",
]


class AbstractChoiceModule(informed.AbstractInformed):
    """
    A 'choice module' provides config option suggestions.
    """

    __slots__ = []

    @abc.abstractmethod
    def get_suggestions(self, **kwargs):
        """
        Requests config option suggestions from this choice module.
        This can be thought of as the "main" routine of a choice module.

        This method must be implemented by derived classes.
        Whether it accepts arguments or not depends on the implementation.
        As a general rule, the method should work without any args passed,
        so all arguments should be keywords.

        The result is a 2-tuple (errors, config suggestions).
        The type of "errors" is undefined, except that it should evaluate
        to True if there are errors, and to False if there are none.
        "config suggestions" is a dict that maps config option names to
        the requested value, which can be True (builtin or module),
        False (disable), a tristate value, an integer or a str.
        It can also be None in case of errors.

        Note: except for "builtin-or-module" (True), it is not possible to
              suggest variant config option values such as {tristate n, m}

        @param kwargs:  undefined

        @return:  2-tuple (errors, config suggestions dict)
        @rtype:   2-tuple (
                     undefined,
                     C{None} or C{dict} :: C{str} => True|False|None|C{str}
                  )
        """
        raise NotImplementedError()

# --- end of AbstractChoiceModule ---


class AbstractChoiceModules(
    informed.AbstractInformed, collections.abc.Mapping
):
    """
    A mapping that contains all available 'choice modules',
    which are instantiated on demand.

    @ivar _modules_loaded:
    @type _modules_loaded:  C{dict} :: C{str} => sub-of L{AbstractChoiceModule}

    @ivar _modules_avail:   4-tuple (cls, None|constructor, args, kwargs)
    @type _modules_avail:
    """

    __slots__ = ["_modules_loaded", "_modules_avail"]

    UNREGISTER_AVAIL_MODULES_AFTER_LOADING = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._modules_loaded = {}
        self._modules_avail = {}

    def normalize_module_name(self, name):
        return name.lower()
    # ---

    @abc.abstractmethod
    def create_dynamic_module(
        self, module_name, module_constructor, module_args, module_kwargs
    ):
        raise KeyError(module_name)

    def _create_module(self, module_name):
        mod_constructor_entry = self._modules_avail[module_name]
        (mcls, mnew, margs, mkwargs) = mod_constructor_entry

        if mnew is None:
            mnew = self.create_informed

        if margs is None:
            margs = ()

        if mkwargs is None:
            mkwargs = {}

        if mcls is True:
            # redundant copy if margs/mkwargs was None
            return self.create_dynamic_module(
                module_name, mnew, list(margs), mkwargs.copy()
            )
        else:
            return mnew(mcls, *margs, **mkwargs)
    # --- end of _create_module (...) ---

    def _init_module(self, module_name):
        module_obj = self._create_module(module_name)
        self._modules_loaded[module_name] = module_obj

        if self.UNREGISTER_AVAIL_MODULES_AFTER_LOADING:
            del self._modules_avail[module_name]

        return module_obj
    # --- end of _init_module (...) ---

    def check_module_loaded(self, module_name):
        return self.normalize_module_name(module_name) in self._modules_loaded

    def list_modules_loaded(self):
        return sorted(self._modules_loaded)

    def _get_module(self, module_name):
        try:
            return self._modules_loaded[module_name]
        except KeyError:
            pass

        return self._init_module(module_name)
    # ---

    def get_module(self, module_name):
        return self._get_module(self.normalize_module_name(module_name))

    __getitem__ = get_module

    def __contains__(self, name):
        module_name = self.normalize_module_name(name)
        return (
            module_name in self._modules_loaded
            or module_name in self._modules_avail
        )

    def __iter__(self):
        return misc.iter_dedup(
            itertools.chain(
                self._modules_loaded,
                self._modules_avail
            )
        )

    def __len__(self):
        return len(set(self._modules_avail) | set(self._modules_loaded))

    def __bool__(self):
        return True

    def _register_module_v(
        self, module_name, module_cls,
        module_constructor, module_args, module_kwargs
    ):
        if (
            module_name in self._modules_loaded
            or module_name in self._modules_avail
        ):
            raise KeyError("cannot re-add module", module_name)
        # --

        if module_cls is None:
            raise ValueError("module cls must not be None")

        elif module_cls is True:
            # dynamic constructor
            pass

        elif (
            module_constructor is None
            and not issubclass(module_cls, AbstractChoiceModule)
        ):
            raise ValueError(
                "module cls does not inherit from AbstractChoiceModule",
                module_cls
            )
        # --

        self._modules_avail[module_name] = (
            module_cls, module_constructor, module_args, module_kwargs
        )
    # ---

    def register_module(
        self, module_name, module_cls,
        module_constructor=None, module_args=None, module_kwargs=None
    ):
        return self._register_module_v(
            self.normalize_module_name(module_name),
            module_cls, module_constructor, module_args, module_kwargs
        )
    # ---

# --- end of AbstractChoiceModules ---
