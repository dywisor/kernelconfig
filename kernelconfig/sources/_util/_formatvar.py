# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections.abc

from . import _outfile
from ...util.misc import get_revlist_map


__all__ = [
    "ConfigurationSourceAutoTmpOutfileVarMapping",
    "ConfigurationSourceAutoTmpdirVarMapping",
]


class _ConfigurationSourceAutoVarMapping(collections.abc.Sized):

    def __init__(self):
        super().__init__()
        self.data = {}
        self.alias_map = {}

    def __bool__(self):
        return bool(self.alias_map)

    def __len__(self):
        return len(self.alias_map)

    @abc.abstractmethod
    def create_new_auto_var(self, key):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_vars(self):
        raise NotImplementedError()

    def add(self, key, alias_key):
        if key not in self.data:
            self.data[key] = self.create_new_auto_var(key)

        self.add_alias(key, alias_key)
    # ---

    def add_alias(self, key, alias_key):
        if alias_key in self.alias_map:
            if self.alias_map[alias_key] != key:
                raise KeyError(alias_key)
        else:
            self.alias_map[alias_key] = key
    # ---

    def __repr__(self):
        return "{cls.__name__}({data!r})".format(
            cls=self.__class__, data=self.data
        )

# --- end of _ConfigurationSourceAutoVarMapping ---


class ConfigurationSourceAutoTmpOutfileVarMapping(
    _ConfigurationSourceAutoVarMapping
):

    def create_new_auto_var(self, key):
        return _outfile.TmpOutfile(key)

    def get_vars(self):
        revmap = get_revlist_map(self.alias_map)
        outfiles = []
        outvars = {}

        for key, outfile_orig in self.data.items():
            outfile_copy = outfile_orig.copy()
            outfiles.append(outfile_copy)
            for fmt_var_name in revmap[key]:
                outvars[fmt_var_name] = outfile_copy
        # --

        return (outfiles, outvars)
    # ---

# --- end of ConfigurationSourceAutoTmpOutfileVarMapping ---


class ConfigurationSourceAutoTmpdirVarMapping(
    ConfigurationSourceAutoTmpOutfileVarMapping
):

    def create_new_auto_var(self, key):
        return _outfile.TmpOutdir(key)

# --- end of ConfigurationSourceAutoTmpdirVarMapping ---
