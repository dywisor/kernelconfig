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
    @ivar type_name: short word describing the type. no spaces allowed
    @type type_name: C{str}

    optionally dependencies on other symbols,
    @ivar dir_dep:  the symbol's dependencies ("depends on"). May be None.
    @type dir_dep:  C{None} or undef

    and optionally visibility dependencies on other symbols
    @ivar vis_dep:  the symbol's visiblity dependencies
                     (visibilty of the symbol's prompts, OR-merged)
    @type vis_dep:  C{None} or undef


    Additionally, a class-wide variables exists for str-formatting the
    option in case of "is not set" values:
    @cvar VALUE_NOT_SET_FMT_STR: used for formatting "not set" values
    @type VALUE_NOT_SET_FMT_STR: C{str}
    """

    __slots__ = ["__weakref__", "name", "dir_dep", "vis_dep"]

    VALUE_NOT_SET_FMT_STR = "# {name} is not set"

    @abc.abstractproperty
    def type_name(cls):  # pylint: disable=E0213
        raise NotImplementedError()

    @abc.abstractclassmethod
    def normalize_and_validate(self, value, lenient=False):
        """Converts the given value to its normalized form.

        @raises ValueError: if value cannot be normalized (is not valid)

        @param value:      value to be normalized and validated
        @type  value:      should match the symbol's value type

        @keyword lenient:  whether normalizing should be a more tolerant
                           Defaults to False
        @type    lenient:  C{bool}

        @return: normalized value
        """
        raise NotImplementedError()

    @classmethod
    def normalize_and_validate_set(cls, value_set):
        """Converts a sequence of values to their normalized form.

        @param value_set:  iterable containing hashable values
        @type  value_set:  C{set}

        @return:  2-tuple (bad values, normalized values)
        @rtype:   2-tuple (C{list}, C{set})
        """
        badvals = []
        normval_set = set()
        for value in value_set:
            try:
                normval = cls.normalize_and_validate(value)
            except ValueError:
                badvals.append(value)
            else:
                normval_set.add(normval)
        # --

        return (badvals, normval_set)
    # ---

    @abc.abstractmethod
    def evaluate_dir_dep(self, symbol_value_map):
        """
        Given a symbol => value map,
        calculates the tristate value of the dir_dep expression of this symbol.

        If the symbol has no dir_deps, returns tristate "y".
        Reinterprets the expression value based on the symbol type.

        @param symbol_value_map:  (incomplete) symbol to value mapping
        @type  symbol_value_map:  C{dict} :: L{AbstractKconfigSymbol} => _

        @return: tristate value
        @rtype:  L{TristateKconfigSymbolValue}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def evaluate_vis_dep(self, symbol_value_map):
        """
        Given a symbol => value map, calculates
        the tristate values of the vis_dep expressions of this symbol,
        and returns the highest value (y > m > n).

        If the symbol has no vis_dep, returns tristate "y".
        Reinterprets expression values based on the symbol type.

        @param symbol_value_map:  (incomplete) symbol to value mapping
        @type  symbol_value_map:  C{dict} :: L{AbstractKconfigSymbol} => _

        @return: tristate value
        @rtype:  L{TristateKconfigSymbolValue}
        """
        raise NotImplementedError()

    def evaluate_dep(self, symbol_value_map):
        """Given a symbol => value map,
        calculates the tristate value of this symbol's dependencies
        (both dir_dep and vis_dep).

        If the symbol has no dependencies, returns tristate "y".

        @param symbol_value_map:  (incomplete) symbol to value mapping
        @type  symbol_value_map:  C{dict} :: L{AbstractKconfigSymbol} => _

        @return: tristate value
        @rtype:  L{TristateKconfigSymbolValue}
        """
        # lazy-eval min(dep(), vis())
        dep_eval = self.evaluate_dir_dep(symbol_value_map)
        if not dep_eval:
            return dep_eval
        else:
            return min((dep_eval, self.evaluate_vis_dep(symbol_value_map)))
    # --- end of evaluate_dep (...) ---

    def format_value_is_not_set(self, name_convert=None):
        return self.VALUE_NOT_SET_FMT_STR.format(
            name=(
                self.name if name_convert is None
                else name_convert(self.name)
            )
        )
    # --- format_value_is_not_set (...) ---

    @abc.abstractmethod
    def format_value(self, value, name_convert=None):
        """Creates a formatted string representing this kconfig symbol
        alongside with the specified value.

        @param value:         symbol value (must be normalized/validated)
        @type value:          depends on symbol type
        @param name_convert:  None or function that converts the symbol name
        @type  name_convert:  C{None} | lambda str: str

        @return: C{str}
        """
        raise NotImplementedError()
    # ---

    def __init__(self, name, dir_dep=None, vis_dep=None):
        super().__init__()
        self.name = name
        self.dir_dep = dir_dep
        self.vis_dep = vis_dep

    def __hash__(self):
        return hash((self.__class__, self.name))

    @abc.abstractclassmethod
    def get_lkconfig_value_repr(self, value):
        """Converts the input value to a value suitable for interfacing
        with lkconfig/oldconfig.

        For tristate and boolean symbols, the result must be an int,
        where 0, 1, 2 correspond to n, m, y, respectively.

        For string, int and hex symbols, the result must be either int 0,
        or a string.
        In case of hex symbols, the string should include the leading "0x".

        @param value:  symbol value (must be normalized/validated)
        @type  value:  depends on symbol type

        @return: lkconfig value representation
        @rtype:  C{int} or C{str}
        """
        raise NotImplementedError()

    def __repr__(self):
        return "{c.__qualname__}<{s.name!s}>".format(c=self.__class__, s=self)

# --- end of AbstractKconfigSymbol ---
