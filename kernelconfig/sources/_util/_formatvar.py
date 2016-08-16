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
    """
    A collection of automatic variables, used for dynamic str-formatting.
    While it is a mapping-like data structure,
    it does not provide the usual dict-access methods like __getitem__().

    Instead, entries must be created with add() or add_alias(),
    and the complete format var mapping can be created with get_vars().

    @ivar data:       mapping from outfile identifier to outfile object
    @type data:       C{dict} :: hashable => sub-of L{AbstractOutfile}
    @ivar alias_map:  mapping from outfile name to outfile identifier
    @type alias_map:  C{dict} :: C{str} => hashable
    """

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
        """Creates a new automatic variable.

        Derived classes must implement this method.

        @param key:  auto var identifier
        @type  key:  hashable

        @return:  auto var
        @rtype:   subclass of L{AbstractOutfile}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_vars(self):
        """
        Creates a format varname => outfile mapping for all outfiles,
        including aliases and returns them as 2-tuple
        (deduplicated list of outfiles, format var X outfile mapping).
        The returned outfiles are copies and can be modified freely.

        Not injective: due to aliases, multiple format variable names may
                       reference the same outfile object,
                       so, generally, len(fmt_vars) >= len(outfiles).
                       For that reason, a duplicate-free list of outfile
                       objects is also returned.

        Derived classes must implement this method.

        @return:  2-tuple (
                     list of new, unique outfile objects,
                     format varname => outfile object mapping
                  )
        @rtype:   2-tuple (
                     C{list} of sub-of L{AbstractOutfile},
                     C{dict} :: C{str} => L{AbstractOutfile}
                  )
        """
        raise NotImplementedError()

    def add(self, key, alias_key):
        """
        Adds an auto var to the mapping, creates it if necessary.

        @raises KeyError:  duplicate alias entry that does not reference
                           the same auto var

        @param key:        the auto var's identifier
        @type  key:        hashable
        @param alias_key:  name of the auto var
        @type  alias_key:  C{str}
        """
        if key not in self.data:
            self.data[key] = self.create_new_auto_var(key)

        # the get_vars() implementation looks up names in self.alias_map only,
        # so an alias entry needs to be created even if key == alias_key
        self.add_alias(key, alias_key)
    # ---

    def add_alias(self, key, alias_key):
        """
        Adds an alias entry to the mapping,
        does not check whether the referenced entry does actually exist.

        @raises KeyError:  duplicate alias entry that does not reference
                           the same auto var

        @param key:        the auto var's identifier
        @type  key:        hashable
        @param alias_key:  name of the auto var
        @type  alias_key:  C{str}

        @return:  None (implicit)
        """
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
