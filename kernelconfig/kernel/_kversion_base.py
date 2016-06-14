# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc


__all__ = ["KernelVersionBaseObject"]


class KernelVersionBaseObject(object, metaclass=abc.ABCMeta):
    """Base class for kernel version objects."""
    __slots__ = []

    @abc.abstractclassmethod
    def new_from_str(cls, seq, *args, **kwargs):
        """Parses a str and creates a (new) version object.

        @param seq:  input str
        @type  seq:  C{str}

        @return:  version object
        @rtype:   subclass of L{KernelVersionBaseObject}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def gen_str(self):
        """Generator that yields str parts that can be concatened for
        creating a str representation of this version object.

        May also return a iterable or an iterator.

        @return:  str parts
        @rtype:   C{str}
        """
        raise NotImplementedError()

    def __str__(self):
        return "".join(self.gen_str())

    def __repr__(self):
        try:
            version_str = str(self)
        except:
            version_str = "???"
        # --
        return "{c.__qualname__}({!r})".format(version_str, c=self.__class__)
    # --- end of __repr__ (...) ---

    @abc.abstractmethod
    def get_sort_key(self):
        """Returns a 'key' suitable for sorting objects of the same type.

        @return: unspecified, possibly a C{tuple}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _cmp_iter(self, other):
        """Generator or iterator that yields
        3-tuples (none_is_lt_than_not_none, value from self, value from other)

        none_is_lt_than_not_none will be queried if either of the values
        is None, but not both.
        It indicates whether "None < x" is True or False.
        It may also be None, in which case the _cmp_lt_gt_le_ge() and
        __eq__() methods of the not-None object will be called.
        Note that its inverse is interpreted as "x > None" (and not ">=").

        @param other:
        @type  other:  same as or subclass of self.__class__

        @return:  3-tuple
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _cmp_none(self):
        """Returns the int result of comparing this object to None.
        It should be -1 for "less than", 0 for "equal to",
        and 1 for "greater than", or NotImplemented.

        @raises TypeError:

        @return:  -1 if less than, 0 if equal to and 1 if greater than C{None}
        @rtype:   C{int} or C{NotImplemented}
        """
        raise NotImplementedError()

    # def __cmp__(self, other)  -- Python 2
    def _cmp_lt_gt_le_ge(self, other):
        """Compares this object to another object (possibly None)
        and returns the result as int.

        @raises TypeError:

        @param other:  object or C{None}

        @return:  -1 if less than, 0 if equal to and 1 if greater than other
        @rtype:   C{int} or C{NotImplemented}
        """
        if other is None:
            return self._cmp_none()

        elif not isinstance(other, self.__class__):
            return NotImplemented

        else:
            for none_is_lt_other, my_val, other_val in self._cmp_iter(other):
                if my_val is None:
                    if other_val is None:
                        # eq
                        pass

                    elif none_is_lt_other is None:
                        cmp_ret = other_val._cmp_lt_gt_le_ge(my_val)
                        if cmp_ret is NotImplemented:
                            return cmp_ret
                        elif cmp_ret != 0:
                            return -cmp_ret

                    else:
                        # None < other_val?
                        return -1 if none_is_lt_other else 1

                elif other_val is None:
                    # and my_val is not None
                    # then "my_val < None"? (cannot be eq)
                    if none_is_lt_other is None:
                        cmp_ret = my_val._cmp_lt_gt_le_ge(other_val)
                        if cmp_ret is NotImplemented:  # redundant
                            return cmp_ret
                        elif cmp_ret != 0:
                            return cmp_ret

                    else:
                        return 1 if none_is_lt_other else -1

                elif my_val < other_val:
                    return -1

                elif my_val > other_val:
                    return 1
            # --

            return 0
    # --- end of _cmp_lt_gt_le_ge (...) ---

    def __eq__(self, other):
        if other is None:
            cmp_ret = self._cmp_none()
            return cmp_ret if cmp_ret is NotImplemented else (cmp_ret == 0)

        elif not isinstance(other, self.__class__):
            return NotImplemented

        else:
            for none_is_lt_other, my_val, other_val in self._cmp_iter(other):
                if none_is_lt_other is None:
                    if my_val is None:
                        if other_val is not None:
                            # other_val eq None?
                            cmp_ret = other_val.__eq__(my_val)
                            if cmp_ret is not True:
                                return cmp_ret

                        # else None eq None

                    elif other_val is None:
                        # my_val eq None?
                        cmp_ret = my_val.__eq__(other_val)
                        if cmp_ret is not True:
                            return cmp_ret

                    elif my_val != other_val:
                        # ne
                        return False

                    # else eq

                elif my_val != other_val:
                    return False
            # -- end for

            return True
    # --- end of __eq__ (...) ---

    def __ne__(self, other):
        is_eq = self.__eq__(other)
        return is_eq if is_eq is NotImplemented else (not is_eq)
    # --- end of __ne__ (...) ---

    def __lt__(self, other):
        cmp_ret = self._cmp_lt_gt_le_ge(other)
        return cmp_ret if (cmp_ret is NotImplemented) else (cmp_ret < 0)

    def __le__(self, other):
        cmp_ret = self._cmp_lt_gt_le_ge(other)
        return cmp_ret if (cmp_ret is NotImplemented) else (cmp_ret <= 0)

    def __gt__(self, other):
        cmp_ret = self._cmp_lt_gt_le_ge(other)
        return cmp_ret if (cmp_ret is NotImplemented) else (cmp_ret > 0)

    def __ge__(self, other):
        cmp_ret = self._cmp_lt_gt_le_ge(other)
        return cmp_ret if (cmp_ret is NotImplemented) else (cmp_ret >= 0)

# --- end of KernelVersionBaseObject
