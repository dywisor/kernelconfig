# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os.path

from ....abc import loggable
from ....util import fs


__all__ = ["NullModulesDir", "StaticModulesDir"]


class AbstractModulesDir(loggable.AbstractLoggable, fs.AbstractFsView):
    __slots__ = []

    # files that get opened when running kmod.Kmod().lookup(),
    # gathered from strace output:
    KMOD_ESSENTIAL_FILES = frozenset({
        "modules.softdep",
        "modules.dep.bin",
        "modules.alias.bin",
        "modules.symbols.bin",
        "modules.builtin.bin"
    })

    def is_available(self):
        mod_dir = self.get_path()
        return all((
            os.path.isfile(os.path.join(mod_dir, candidate))
            for candidate in self.KMOD_ESSENTIAL_FILES
        ))
    # --- end of is_available (...) ---

    @abc.abstractmethod
    def is_ready(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def create(self):
        raise NotImplementedError()

    def prepare(self):
        if not self.is_ready():
            self.create()
        return self.is_available()
    # --- end of prepare (...) ---

# --- end of AbstractModulesDir ---


class NullModulesDir(AbstractModulesDir):
    __slots__ = []

    def get_path(self):
        raise TypeError()

    def is_available(self):
        return False

    def is_ready(self):
        return True

    def create(self):
        pass

# --- end of NullModulesDir ---


class StaticModulesDir(AbstractModulesDir):
    __slots__ = ["path"]

    def __init__(self, path, **kwargs):
        super().__init__(**kwargs)
        self.path = path

    def get_path(self):
        return self.path

    def is_ready(self):
        return os.path.isdir(self.get_path())

    def create(self):
        pass

# --- end of StaticModulesDir ---
