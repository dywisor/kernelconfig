# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc

from ....abc import loggable
from ....util import fileio
from ....util import misc


__all__ = ["AbstractModaliasLookup"]


class AbstractModaliasLookup(loggable.AbstractLoggable):
    """
    This base class describes the methods available
    for looking up kernel module alias identifiers.
    """
    __slots__ = []

    @abc.abstractproperty
    def AVAILABLE(cls):
        """
        This class-wide variable should indicate whether
        the lookup implementation provided by the class is available,
        which may depend on external python modules.

        Derived classes must set this attribute.

        @return:  whether the modalias lookup implementation is available
        @rtype:   C{bool}
        """
        return False
    # --- end of class property AVAILABLE (...) ---

    @abc.abstractmethod
    def iter_lookup_v(self, modaliases):
        """Generator that looks up a sequence of module aliases
        and yields module names.

        Derived classes must implement this method.

        Deduplication of the resulting module names is handled by lookup_v().

        @param modaliases:  iterable containing module alias identifiers
        @type  modaliases:  iterable of C{str}

        @return:  kernel module name(s), possibly empty/None
        @rtype:   C{str} or C{None}
        """
        raise NotImplementedError()
    # --- end of iter_lookup_v (...) ---

    def lookup_v(self, modaliases, **kwargs):
        """Looks up a sequence of module aliases
        and returns a deduplicated list of module names.

        @param modaliases:  iterable containing module alias identifiers
        @type  modaliases:  iterable of C{str}

        @return:  deduplicated list of "non-empty" kernel module names
        @rtype:   C{list} of C{str}
        """
        return list(
            misc.iter_dedup(
                filter(
                    None,
                    self.iter_lookup_v(modaliases, **kwargs)
                )
            )
        )
    # --- end of lookup_v (...) ---

    def lookup(self, *modaliases, **kwargs):
        """varargs variant of lookup_v()."""
        return self.lookup_v(modaliases, **kwargs)
    # --- end of lookup (...) ---

    def __getitem__(self, key):
        """by-key access to module alias lookup,
        obj[module_alias] -> [module names]

        @return:  deduplicated list of kernel module names
        @rtype:   C{list} of C{str}
        """
        return self.lookup_v([key])
    # --- end of __getitem__ (...) ---

    def lookup_from_file(self, modalias_file):
        """
        Reads a modalias file and returns a list of corresponding
        kernel module names.

        File format: one module alias identifier per line

        @param modalias_file:  path to modalias file or file object
        @type  modalias_file:  C{str} (or fileobj)

        @return:  deduplicated list of kernel module names
        @rtype:   C{list} of C{str}
        """
        modaliases = [
            l.strip() for k, l in fileio.read_text_file_lines(modalias_file)
        ]

        return self.lookup_v(modaliases)
    # --- end of lookup_from_file (...) ---

# --- end of AbstractModaliasLookup ---


class UnavailableModaliasLookup(AbstractModaliasLookup):
    """
    This class is a complete modalias lookup implementation
    that is not able to perform the lookup.

    Modules that provide a lookup class depending on external modules
    can use this class for the "implementation unavailable" case:

    >>> try import ext_module, set HAVE_EXT accordingly
    >>>
    >>> if HAVE_EXT:
    >>>     class MyLookup(AbstractModaliasLookup):
    >>>         AVAILABLE = True
    >>>         ...
    >>> else:
    >>>      MyLookup = UnavailableModaliasLookup
    >>>

    To avoid confusion, classes that are possibly aliased
    to UnavailableModaliasLookup should not be subclassed.
    Also, isinstance(_, MyLookup) checks are not meaningful.

    @cvar AVAILABLE:  this class is never "available"
    @type AVAILABLE:  C{bool}
    """

    AVAILABLE = False

    def iter_lookup_v(self, modaliases):
        self.logger.warning("modalias lookup is not available")
        yield None

    def __init__(self, *args, **kwargs):
        super().__init__(
            logger=kwargs.get("logger"),
            logger_name=kwargs.get("logger_name"),
            parent_logger=kwargs.get("parent_logger")
        )
        # ignored args, kwargs

# --- end of UnavailableModaliasLookup ---
