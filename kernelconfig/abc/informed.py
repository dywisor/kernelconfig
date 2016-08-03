# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import loggable

__all__ = ["AbstractSourceInformed", "AbstractInformed"]


class AbstractSourceInformed(loggable.AbstractLoggable):
    __slots__ = ["source_info"]

    def __init__(self, *, source_info, **kwargs):
        super().__init__(**kwargs)
        self.source_info = source_info

    def create_source_informed(self, constructor, *args, **kwargs):
        kwargs.setdefault("source_info", self.source_info)
        return self.create_loggable(constructor, *args, **kwargs)
    # --- end of create_source_informed (...) ---

# --- end of AbstractSourceInformed ---


# AbstractInstallInformed


class AbstractInformed(AbstractSourceInformed):
    __slots__ = ["install_info"]

    def __init__(self, *, install_info, source_info, **kwargs):
        super().__init__(source_info=source_info, **kwargs)
        self.install_info = install_info

    def create_informed(self, constructor, *args, **kwargs):
        kwargs.setdefault("source_info", self.source_info)
        kwargs.setdefault("install_info", self.install_info)
        return self.create_loggable(constructor, *args, **kwargs)
    # --- end of create_informed (...) ---

# --- end of AbstractInformed ---
