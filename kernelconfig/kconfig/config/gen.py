# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from ...abc import loggable
from ...lang import interpreter
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

    def __init__(self, source_info, **kwargs):
        super().__init__(**kwargs)

        self.source_info = source_info
        self.source_info.set_logger(parent_logger=self.logger)

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
            self.source_info, self.get_config_choices()
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

# --- end of ConfigGenerator ---