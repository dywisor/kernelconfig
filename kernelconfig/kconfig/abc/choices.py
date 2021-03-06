# kernelconfig -- abstract description of Kconfig-related classes
# -*- coding: utf-8 -*-

import abc
import functools

from ...abc import loggable

__all__ = [
    "AbstractConfigChoices",
    "AbstractConfigDecision",
    "AbstractRestrictionSetConfigDecision",
    "AbstractValueConfigDecision",
]


def _decision_method(unbound_method):
    """Turns a f(self, decision_key, ...)
    into a f'(self, decision_obj, ...) method.

    The decision object is retrieved via
    self.get_or_create_decision(decision_key).
    If it is None, then the wrapper returns False ("operation failed"),
    otherwise it hands the decision object (and remaining args/kwargs)
    over to the original method.

    @param unbound_method:  an unbound method whose signature must conform
                            with f(self, key[, ...])
    @type  unbound_method:  method :: (C{type}, C{str}|_[, ...])

    @return: new unbound method
    @rtype: method :: (C{type}, L{AbstractConfigDecision}, ...)
    """
    def wrapper(self, config_option, *args, **kwargs):
        decision = self.get_or_create_decision(config_option)
        if decision is None:
            return False
        else:
            return unbound_method(self, decision, *args, **kwargs)
    # --- end of wrapper (...) ---

    return functools.update_wrapper(wrapper, unbound_method)
# --- end of _decision_method (...) ---


class AbstractConfigChoices(loggable.AbstractLoggable):
    """
    This abstract class describes the operations
    that can be used for modifying configurations.

    The operations return a C{bool} value indicating success or failure,
    do not raise Exceptions under normal circumstances
    (and value errors are considered normal, for instance),
    and take care of logging.

    Most of the actual work is offloaded to symbol-specific decision objects.
    """

    @abc.abstractmethod
    def commit(self):
        """Resolves decisions and transfers them to the config dict.

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_or_create_decision(self, config_option):
        """
        Returns a decision container for the given config option.
        Creates a new one if necessary,
        returns None if the option doesn't exist.

        @raises TypeError: only if the option exists,
                           but has no decision container class associated

        @param config_option:  option name
                               (more generally, config option identifier)
        @type  config_option:  usually C{str}

        @return:  decision object or C{None}
        @rtype:   subclass of L{AbstractConfigDecision} or C{None}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def discard(self, config_option, source=None):
        """Forgets any previous decision that has been made
        for the given config option.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: True if option existed, else False
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @_decision_method
    def option_disable(self, config_option, source=None):
        """Disables a config option.

        This operation may result in failure due to missing config options,
        and previous decisions.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        return config_option.disable(source=source)

    @_decision_method
    def option_module(self, config_option, source=None):
        """Enables a config option as module.

        This operation may result in failure due to missing config options,
        unsupported values, and previous decisions.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        return config_option.module(source=source)

    @_decision_method
    def option_builtin(self, config_option, source=None):
        """Enables a config option as builtin, if applicable,
        and otherwise sets the config option to an appropriate value
        representing an "enabled" state.

        This operation may result in failure due to missing config options,
        unsupported values, and previous decisions.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        return config_option.builtin(source=source)

    @_decision_method
    def option_builtin_or_module(self, config_option, source=None):
        """Enables a config option as builtin and/or module,
        depending on whatever value is supported and previous decisions.

        This operation may result in failure due to missing config options,
        unsupported values, and previous decisions.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        return config_option.builtin_or_module(source=source)

    @_decision_method
    def option_set_to(self, config_option, value, source=None):
        """Sets a config option to a specific value.

        This operation may result in failure due to missing config options,
        unsupported value, and previous decisions.

        A value of True gets interpreted as option_builtin_or_module(),
        False as option_disable(), and None is forbidden, because it is used
        for internal purposes.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @param   value:          option value
        @type    value:          undef, possibly C{str}, C{bool} or C{int}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        if value is True:
            return config_option.builtin_or_module(source=source)
        elif value is False:
            return config_option.disable(source=source)
        elif value is None:
            return self._log_forbidden_value(value, source=source)
        else:
            return config_option.set_to(value, source=source)

    def __setitem__(self, key, value):
        """Convenience wrapper that calls option_set_to(key, value)."""
        return self.option_set_to(key, value)

    def set_options_from_map(
        self, config_options, source=None, *,
        ignore_missing=False, allow_empty=True, filter_func=None
    ):
        """Sets several config options to their (individual) values.

        This helper method acts like a "mass-option_set_to()" and adds
        a few convenience features such as filtering out unknown options.

        The "config options" parameter should be a dict where the keys are
        config option names, and values are config option values.
        It can also be a sequence of 2-tuples, similar to dict.update().

        Any false value, e.g. None, is also accepted,
        and makes this method immediately return "success" or "failure",
        depending on the "allow_empty" keyword parameter.

        @param   config_options:   either a dict of config option name X value,
                                   or an iterable of 2-tuples(option, value).

                                   See option_set_to() for a description
                                   of possible config option names and values.
        @type    config_options:   dict :: C{str} => undef
                                   or iterable of 2-tuple (C{str}, undef)
                                   or anything false

        @keyword source:           additional information about the decision's
                                   origin. Defaults to None.
        @type    source:           undef or C{None}

        @keyword ignore_missing:   whether to ignore nonexistent config options
                                   Normally, this an error, but if the config
                                   options come from an unreliable source,
                                   this keyword may be set to True to discard
                                   unknown options.
                                   Defaults to False.
        @type    ignore_missing:   C{bool}

        @keyword allow_empty:      whether an empty (or otherwise false)
                                   config_options parameter should be
                                   interpreted as success or failure.
                                   Defaults to True, which allows empty input.

                                   The meaning of "empty" here is
                                   "no config option has been set".
                                   An input config options sequence
                                   that has been completely filtered out
                                   due to unknown options is considered
                                   as "equally" empty as an empty dict.
        @type    allow_empty:      usually C{bool}

        @keyword filter_func:      either None,
                                   which disables name/value-based filtering,
                                   True which filters out false values,
                                   or a function that receives a config option
                                   name as first and its value as second
                                   argument and returns True if the option
                                   should be set and false otherwise.
        @type    filter_func:      C{None} | C{bool} | callable :: n,v -> bool

        @return: success (True/False)
        @rtype:  C{bool}
        """
        if not config_options:
            return allow_empty
        elif hasattr(config_options, "keys"):
            options_iter = ((k, config_options[k]) for k in config_options)
        else:
            options_iter = config_options

        if ignore_missing:
            # check has_option() before calling option_set_to(),
            # there's no way to know why option_set_to() failed

            def verbosely_check_option_exists(
                item, *, has_option=self.has_option
            ):
                # item: 2-tuple (name, value)
                if has_option(item[0]):
                    return True
                else:
                    self.logger.warning("Unknown config option: %s", item[0])
                    return False
            # ---

            options_iter = filter(verbosely_check_option_exists, options_iter)
        # --

        if not filter_func:
            def check_option_value_allowed(option, value):
                return True
        elif filter_func is True:
            def check_option_value_allowed(option, value):
                if not value:
                    # COULDFIX: empty str -- is a false value
                    return False
                else:
                    return True
        else:
            check_option_value_allowed = filter_func
        # --

        option_set_to = self.option_set_to
        have_set_any_config_option = False
        for config_option, value in options_iter:
            if not check_option_value_allowed(config_option, value):
                self.logger.debug(
                    "Ignoring %r decision for config option %s (filtered out)",
                    value, config_option
                )

            elif option_set_to(config_option, value, source=source):
                have_set_any_config_option = True

            else:
                return False
        # --

        return True if have_set_any_config_option else allow_empty
    # --- end of set_options_from_map (...) ---

    def set_options_from_suggestions(self, config_suggestions, **kwargs):
        """
        Accepts a config suggestions result object
        as returned by AbstractChoiceModule.get_suggestions()
        and sets config options accordingly if no errors occurred.
        Otherwise, returns False.

        See set_options_from_map() for accepted keyword arguments.

        @param config_suggestions:  config suggestions,
                                    a 2-tuple (errors, config options map)
        @type  config_suggestions:  2-tuple (undef, dict)

        @param kwargs:              see set_options_from_map()

        @return: success (True/False)
        @rtype:  C{bool}
        """
        errors, config_options = config_suggestions
        if errors:
            # assume already logged
            return False
        else:
            return self.set_options_from_map(config_options, **kwargs)
    # --- end of set_options_from_suggestions (...) ---

    @_decision_method
    def option_append(self, config_option, value, source=None):
        """Appends a value to the existing value of a config option.
        Identical to option_set_to() if no value exists so far.

        The concrete meaning of "append" is left open here.
        For string-type options, this method could append a word to the end
        of the existing string value, possibly separated by whitespace.

        This operation may result in failure due to missing config options,
        unsupported value, and previous decisions.

        A value of None is forbidden as it is used for internal purposes.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @param   value:          option value
        @type    value:          undef, possibly C{str} or C{int}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        if value is None:
            return self._log_forbidden_value(value, source=source)
        else:
            return config_option.append(value, source=source)

    @_decision_method
    def option_add(self, config_option, value, source=None):
        """Adds a value to the existing value of a config option.
        Identical to option_set_to() if no value exists so far.

        The meaning of "add" is left open here.
        For string-type options,
        this method could insert a word into the list of existing words.
        For int-type options, this method could simply do addition.

        This operation may result in failure due to missing config options,
        unsupported value, and previous decisions.

        A value of None is forbidden as it is used for internal purposes.

        @param   config_option:  option name
        @type    config_option:  usually C{str}
        @param   value:          option value
        @type    value:          undef, possibly C{str} or C{int}
        @keyword source:         additional information about the decision's
                                 origin. Defaults to None.
        @type    source:         undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        return config_option.add(value, source=source)

    @abc.abstractmethod
    def has_option(self, config_option):
        """Checks whether a config option with the given name exists.

        @param   config option:  option name
        @type    config_option:  usually C{str}

        @return:  True if the option exists, False otherwise
        @rtype:   C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def find_option(self, approx_config_option):
        """Checks whether a config option with the given name exists.
        If not, tries to find options whose names are close to the requested
        name.

        The result is a list of candidates,
        with one item if an exact match has been found,
        a variable number of name candidates ordered by 'distance'
        if close matches have been found, and an empty list of not.

        Derived classes that do not implement approximate matching should
        check whether the requested option exists and return a one item list
        in that case, and an empty list otherwise.
        This implementation is also available via super().find_solution(...).

        @param   approx_config option:  approximate option name
        @type    approx_config_option:  usually C{str}

        @return:  list of candidates, with zero or more items
        @rtype:   C{list} of C{str}
        """
        if self.has_option(approx_config_option):
            return [approx_config_option]
        else:
            return []
    # --- end of find_option (...) ---

    def _log_forbidden_value(self, value, source=None):
        self.logger.error("%r value is forbidden", value)
        return False
    # --- end of _log_forbidden_value (...) ---

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type is None:
            self.commit()

# --- end of AbstractConfigChoices (...) ---


class AbstractConfigDecision(loggable.AbstractLoggable):
    """
    A config decision keeps track of user-requested values
    for a single kconfig symbol.

    @ivar symbol:   symbol controlled by this decision
    @type symbol:   subclass of L{AbstractKconfigSymbol}
    @ivar default:  default value, e.g. from defconfig, may be None if unknown
    @type default:  L{TristateKconfigSymbolValue} | C{str} | C{int} | C{None}
    """
    __slots__ = ["symbol", "default"]

    @abc.abstractmethod
    def get_decisions(self):
        """Returns an ordered list of decision variants made for the symbol.

        Returns None if no decision has been made,
        and empty list there are no variants,
        a list with one element if there's only one variant,
        and a list with multiple elements if there are > 2 variants,
        with the most preferred variant at the end of the list,
        so that it can be retrieved with <list>.pop().

        @return: new list or C{None}
        @rtype:  C{list} or C{None}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def disable(self, source=None):
        """Make a request to the disable the option.

        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def module(self, source=None):
        """Make a request to the enable the option as module.

        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def builtin(self, source=None):
        """Make a request to the enable the option as builtin.

        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def builtin_or_module(self, source=None):
        """Make a request to the enable the option as builtin or module.

        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def set_to(self, value, source=None):
        """Make a request to assign the given value to the option.

        Note: value is never a C{bool} (True/False)

        @param   value:   value
        @type    value:   C{str} | C{int} | L{TristateKconfigSymbolValue} | _
        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def append(self, value, source=None):
        """Make a request to append the given value to the existing value.
        Identical to set_to() if no value exists so far.

        @param   value:   value
        @type    value:   C{str} | C{int} | L{TristateKconfigSymbolValue} | _
        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def add(self, value, source=None):
        """Make a request to add the given value to the existing value.
        Identical to set_to() if no value exists so far.

        @param   value:   value
        @type    value:   C{str} | C{int} | L{TristateKconfigSymbolValue} | _
        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return: success (True/False)
        @rtype:  C{bool}
        """
        raise NotImplementedError()

    def operation_not_supported(self, op_name, source=None):
        """A helper method that derived classes may call
        if they do not support a specific operation.

        It logs the incident and returns False ("operation failed").

        @param op_name:   name of the operation, e.g. "module"
        @type  op_name:   C{str}
        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}
        """
        self.logger.error(
            "%s-type option does not support %s()",
            self.symbol.type_name, op_name
        )
        return False
    # --- end of operation_not_supported (...) ---

    def set_logger(self, **kwargs):
        if not kwargs.get("logger_name"):
            # also override logger_name=None
            kwargs["logger_name"] = self.symbol.name

        return super().set_logger(**kwargs)
    # --- end of set_logger (...) ---

    def __init__(self, kconfig_symbol, default, **kwargs):
        self.symbol = kconfig_symbol  # needs to be set before super()
        self.default = default
        super().__init__(**kwargs)
    # --- end of __init__ (...) ---

    def typecheck_value(self, value):
        """Checks and converts a value.

        By default, calls the symbol's normalize_and_validate() method.
        Derived classes may override this method
        to allow for a wider range of input.

        @raises ValueError: bad value

        @param value:  input value
        @type  value:  undef

        @return: modified value
        @rtype:  undef
        """
        return self.symbol.normalize_and_validate(value)
    # --- end of typecheck_value (...) ---

    def typecheck_values(self, values):
        """
        Checks an iterable of values the using typecheck_value() method.

        Catches ValueErrors.

        Returns a 2-tuple (good values, bad values).

        @param values:
        @type  values:  iterable

        @return: 2-tuple (normalized, invalid)
        @rtype:  2-tuple (C{list}, C{list})
        """
        _typecheck_value = self.typecheck_value

        normvals = []
        badvals = []

        for val in values:
            try:
                normval = _typecheck_value(val)
            except ValueError:
                badvals.append(val)
            else:
                normvals.append(normval)
        # ---

        return (normvals, badvals)
    # --- end of typecheck_symbol_values (...) ---

# --- end of AbstractConfigDecision ---


class AbstractRestrictionSetConfigDecision(AbstractConfigDecision):
    """A config decision that stores value variants in an initially
    unrestricted set that can be further restricted by making decisions.

    @cvar VALUE_SET_TYPE:  set type for storing acceptable values
    @type VALUE_SET_TYPE:  set-like C{type}

    @ivar:  either C{None} (no restrictions) or a set of acceptable values
    @type:  C{None} or C{set}
    """
    __slots__ = ["values"]

    VALUE_SET_TYPE = set

    @classmethod
    def get_decision_str_of(cls, values):
        """Formats a sequence of values.

        @param values:
        @type  values:  iterable

        @return:  value list string
        @rtype:   C{str}
        """
        return ", ".join(sorted(map(str, values)))
    # --- end of get_decision_str_of (...) ---

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = None  # unrestricted, initially
    # --- end of __init__ (...) ---

    def update_restrictions(self, values, source=None):
        """
        Imposes further restrictions to the set of acceptable values.

        This operation may result in failure due to
        values that are unsuitable for the symbol's type,
        and values that are not a restriction of previous restrictions.
        That is, the new values should form a subset of existing restrictions
        (which does not have to be a proper subset).

        @param   values:  an iterable containing proper values
        @type    values:  iterable

        @keyword source:  additional information about the decision's origin.
                          Defaults to None.
        @type    source:  undef or C{None}

        @return:  success (True/False)
        @rtype    C{bool}
        """
        # the values per se are "valid",
        # but they are not necessarily suitable for the symbol, so check that.
        normvals, badvals = self.typecheck_values(values)

        if badvals:
            self.logger.error(
                "Invalid value(s): %s", self.get_decision_str_of(badvals)
            )
            return False
        # --

        prev_decision = self.values
        decision = self.VALUE_SET_TYPE(normvals)

        if prev_decision is None:
            # no previous decision, first restriction
            self.logger.debug(
                "Setting decision to %r (overrides default value %s)",
                self.get_decision_str_of(decision),
                ("<unset>" if self.default is None else self.default)
            )
            self.values = decision
            return True
        # --

        # a previous decision exists;
        #  in that case, decision must be equiv. or a further restriction

        decision_symdiff = decision ^ prev_decision

        if not decision_symdiff:
            self.logger.debug(
                "Keeping previous decision %r",
                self.get_decision_str_of(decision)
            )
            # self.values = prev_decision
            return True

        elif decision_symdiff & decision:
            # decision is not a restriction of prev_decision
            #   x | x in decision and x not in prev_decision
            self.logger.warning(
                'Decision %r conflicts with previous decision %r',
                self.get_decision_str_of(decision),
                self.get_decision_str_of(prev_decision)
            )
            return False

        else:
            # decision is a further restriction of the previous decision
            #  (decision_symdiff & prev_decision) == decision_symdiff
            self.logger.debug(
                "Updating decision to %r (removed %r)",
                self.get_decision_str_of(decision),
                self.get_decision_str_of(decision_symdiff)
            )
            self.values = decision
            return True
        # -- end if
    # --- end of update_restrictions (...) ---

    def set_to(self, value, source=None):
        return self.update_restrictions([value], source=source)

    def append(self, value, source=None):
        # contradicts restrictive behavior
        return self.operation_not_supported("append", source=source)

    def add(self, value, source=None):
        # contradicts restrictive behavior
        return self.operation_not_supported("add", source=source)

# --- end of AbstractRestrictionSetConfigDecision ---


class AbstractValueConfigDecision(AbstractConfigDecision):
    __slots__ = ["value"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = None
    # --- end of __init__ (...) ---

    def get_decisions(self):
        return None if self.value is None else [self.value]

    def set_to(self, value, source=None):
        try:
            normval = self.typecheck_value(value)
        except ValueError:
            self.logger.error("Invalid value: %r", value)
            return False

        if self.value is None:
            return self.do_set_value(normval, source=source)

        elif self.value == normval:
            self.logger.debug("Keeping decision %r", normval)
            return True

        else:
            self.logger.error(
                "Cannot override earlier decision %r with %r",
                self.value, normval
            )
            return False
    # --- end of set_to (...) ---

    def do_set_value(self, value, source=None):
        self.logger.debug(
            "Setting decision to %r (overrides '%s')",
            value,
            (
                self.value if self.value is not None
                else ("<unset>" if self.default is None else self.default)
            )
        )
        self.value = value
        return True
    # --- end of do_set_value (...) ---

# --- end of AbstractValueConfigDecision ---
