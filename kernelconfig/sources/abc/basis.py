# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc


__all__ = [
    "AbstractConfigurationBasis",
    "AbstractFileBackedConfigurationBasis"
]


class AbstractConfigurationBasis(object, metaclass=abc.ABCMeta):
    """
    This class represents a single "configuration basis",
    which is an input config that exists as file or in memory.
    """
    __slots__ = []

    @abc.abstractmethod
    def read_config(self):
        """
        Generator that yields (name, value) tuples representing the
        configuration served by this basis.

        May also return a anything iterable, e.g. a list.

        Derived classes must implement this method.

        @return:  (iterable of) 2-tuples (option name, option value)
        @rtype:   (iterable of) 2-tuples (C{str}, C{str})
        """
        raise NotImplementedError()
    # --- end of read_config (...) ---

# --- end of AbstractConfigurationBasis ---


class AbstractFileBackedConfigurationBasis(AbstractConfigurationBasis):
    """
    This class represents a single "configuration basis",
    which is, essentially, just a path to the input .config file.
    """
    __slots__ = []

    @abc.abstractmethod
    def get_filepath(self):
        """
        Returns the path to the input .config file
        served by this configuration basis.

        Derived classes must implement this method.

        @return:  path to input .config file
        @rtype:   C{str}
        """
        raise NotImplementedError()
    # --- end of get_filepath (...) ---

    def read_config(self):
        raise NotImplementedError(
            "TODO: file backed conf bases should get read_config() from abc"
        )

# --- end of AbstractFileBackedConfigurationBasis ---
