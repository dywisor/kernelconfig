# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc

from ...abc import informed
from ...lang import interpreter

from ...kernel.hwdetection import detector

from .. import symbolgen

from . import data
from . import choices


__all__ = ["KernelConfigGenerator"]


def _lazy_constructor(attr_name, attr_constructor_name=None):
    if attr_constructor_name is None:
        attr_constructor_name = "_create_" + attr_name.lstrip("_")

    def wrapper(self):
        attr = getattr(self, attr_name)
        if attr is None:
            attr = getattr(self, attr_constructor_name)()
            setattr(self, attr_name, attr)
        return attr
    # ---

    return wrapper
# ---


class AbstractConfigGenerator(informed.AbstractInformed):

    @abc.abstractmethod
    def get_kconfig_symbols(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_config(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_config_choices(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_config_choices_interpreter(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def commit(self):
        raise NotImplementedError()

# --- end of AbstractConfigGenerator ---


class _ConfigGenerator(AbstractConfigGenerator):

    def __init__(self, install_info, source_info, **kwargs):
        # super().__init__() is kw-only
        super().__init__(
            install_info=install_info, source_info=source_info, **kwargs
        )

        # take over ownership of source_info
        self.source_info.set_logger(parent_logger=self.logger)

        self._kconfig_symbols = None
        self._config = None
        self._config_choices = None
        self._config_choices_interpreter = None
    # --- end of __init__ (...) ---

    def _create_kconfig_symbols(self):
        self.source_info.prepare()
        symgen = self.create_source_informed(symbolgen.KconfigSymbolGenerator)
        return symgen.get_symbols()

    def _create_config(self):
        return self.create_loggable(
            data.KernelConfig, self.get_kconfig_symbols()
        )

    def _create_config_choices(self):
        return self.create_loggable(
            choices.ConfigChoices, self.get_config()
        )

    def _create_config_choices_interpreter(self):
        return self.create_loggable(
            interpreter.KernelConfigLangInterpreter,
            self.install_info,
            self.source_info,
            self.get_config_choices(),
            self.get_hwdetector()
        )

    get_kconfig_symbols = _lazy_constructor("_kconfig_symbols")
    get_config = _lazy_constructor("_config")
    get_config_choices = _lazy_constructor("_config_choices")
    get_config_choices_interpreter = \
        _lazy_constructor("_config_choices_interpreter")

    def commit(self):
        if self._config_choices is None:
            return True

        elif self._config_choices.commit():
            self._config_choices = None
            return True

        else:
            return False
    # --- end of commit (...) ---

# --- end of _ConfigGenerator ---


class KernelConfigGenerator(_ConfigGenerator):

    def __init__(self, install_info, source_info, modules_dir=True, **kwargs):
        super().__init__(
            install_info=install_info, source_info=source_info, **kwargs
        )

        # hwdetector lazy-inits itself
        self._hwdetector = self.create_informed(
            detector.HWDetect, modules_dir=modules_dir
        )
    # --- end of __init__ (...) ---

    def get_modules_map(self):
        # FIXME: remove
        return self._hwdetector.get_modules_map()
    # --- end of get_modules_map (...) ---

    def get_modalias_map(self):
        # FIXME: remove
        return self._hwdetector.get_modalias_map()
    # --- end of get_modalias_map (...) ---

    def get_hwdetector(self):
        return self._hwdetector
    # --- end of get_hwdetector (...) ---

# --- end of KernelConfigGenerator ---
