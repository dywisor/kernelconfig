# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections.abc

from ...abc import loggable


__all__ = [
    "AbstractConfigurationSource",
]


class AbstractConfigurationSource(
    loggable.AbstractLoggable, collections.abc.Hashable
):
    """
    A configuration source provides one or more configuration basis objects.

    Usually, they are created dynamically,
    e.g. by downloading files or running commands.

    A configuration source is identified by its name,
    @ivar name:  name of the configuration source
    @type name:  C{str}
    """

    __slots__ = ["name"]

    def __init__(self, name, **kwargs):
        super().__init__(**kwargs)
        self.name = name
    # --- end of __init__ (...) ---

    def __hash__(self):
        return hash(self.name)
    # --- end of __hash__ (...) ---

    @abc.abstractmethod
    def get_configuration_basis(self, *args, **kwargs):
        """
        Returns a configuration basis for the requested input parameters.

        @param args:     unspecified for now
        @param kwargs:   unspecified for now


        @return:  configuration basis object
        @rtype:   subclass of L{AbstractConfigurationBasis}
        """
        raise NotImplementedError()
    # --- end of get_configuration_basis (...) ---

# --- end of AbstractConfigurationSource ---
