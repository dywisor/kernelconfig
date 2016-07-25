# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...abc import loggable
from ...lang import interpreter

from ...kernel.hwdetection import detector

from .. import symbolgen

from . import data
from . import choices


__all__ = ["ConfigGenerator"]


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


class ConfigGenerator(loggable.AbstractLoggable):

    def __init__(self, install_info, source_info, modules_dir=True, **kwargs):
        super().__init__(**kwargs)

        self.install_info = install_info

        self.source_info = source_info
        self.source_info.set_logger(parent_logger=self.logger)

        # hwdetector lazy-inits itself
        self._hwdetector = self.create_loggable(
            detector.HWDetect, self.source_info, modules_dir=modules_dir
        )

        self._kconfig_symbols = None
        self._config = None
        self._config_choices = None
        self._config_choices_interpreter = None
    # --- end of __init__ (...) ---

    def _create_kconfig_symbols(self):
        self.source_info.prepare()
        symgen = self.create_loggable(
            symbolgen.KconfigSymbolGenerator, self.source_info
        )
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

    def commit(self):
        if self._config_choices is None:
            return True

        elif self._config_choices.commit():
            self._config_choices = None
            return True

        else:
            return False
    # --- end of commit (...) ---

# --- end of ConfigGenerator ---
