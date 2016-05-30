# kernelconfig -- abstract description of a Kconfig symbol
# -*- coding: utf-8 -*-

import abc
import collections.abc

__all__ = ["AbstractKconfigSymbol"]


class AbstractKconfigSymbol(collections.abc.Hashable):
    """
    A(n abstract) kconfig option,

    which has a name
    @ivar name: name of the config option
    @type name: str

    a specific type,
    which is determined by its class and may also be retrieved as str via
    @cvar type_name: short word describing the type. no spaces allowed
    @type type_name: C{str}

    optionally dependencies on other symbols,
    @cvar dir_dep:  the symbol's dependencies ("depends on"). May be None.
    @type dir_dep:  C{None} or undef

    and optionally reverse dependencies
    @cvar rev_dep:  the symbol's reverse dependencies ("selected by").
                    May be None.
    @type rev_dep:  C{None} or undef

    Additionally, a class-wide variables exists for str-formatting the
    option in case of "is not set" values:
    @cvar VALUE_NOT_SET_FMT_STR: used for formatting "not set" values
    @type VALUE_NOT_SET_FMT_STR: C{str}
    """

    __slots__ = ["__weakref__", "name", "dir_dep", "rev_dep"]

    VALUE_NOT_SET_FMT_STR = "# {name} is not set"

    @abc.abstractproperty
    def type_name(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    @abc.abstractclassmethod
    def normalize_and_validate(self, value):
        """Converts the given value to its normalized form.

        @raises ValueError: if value cannot be normalized (is not valid)

        @param value: value to be normalized and validated
        @type  value: should match the symbol's value type

        @return: normalized value
        """
        raise NotImplementedError()

    def format_value_is_not_set(self):
        return self.VALUE_NOT_SET_FMT_STR.format(name=self.name)
    # --- format_value_is_not_set (...) ---

    @abc.abstractmethod
    def format_value(self, value):
        """Creates a formatted string representing this kconfig symbol
        alongside with the specified value.

        @param value: symbol value (must be normalized/validated)
        @type value: depends on symbol type

        @return: C{str}
        """
        raise NotImplementedError()
    # ---

    def __init__(self, name, dir_dep=None, rev_dep=None):
        super().__init__()
        self.name = name
        self.dir_dep = dir_dep
        self.rev_dep = rev_dep

    def __hash__(self):
        return hash((self.__class__, self.name))

    def __repr__(self):
        return "{c.__qualname__}<{s.name!s}>".format(c=self.__class__, s=self)

# --- end of AbstractKconfigSymbol ---
