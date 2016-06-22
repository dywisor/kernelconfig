# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import functools


__all__ = ["ObjectCache"]


class ObjectCache(object):
    """Object cache that tries to avoid object creation by using
    functools.lru_cache for memorizing recent objects.
    """

    def _create_object(self, constructor, args):
        """Creates a new object, constructor(*args)."""
        return constructor(*args)

    def _get_object(self, constructor, args):
        """Returns a shared object, creates a new one if necessary.

        This method gets rebound in __init__().
        """
        return self._create_object(constructor, args)

    def info(self):
        """Returns information about the object cache.

        This method gets rebound in __init__().
        """
        return self.get.cache_info()

    def __init__(self, maxsize=32, typed=True):
        """
        @keyword maxsize:  max number of objects to keep in the cache
                           Defaults to 32.
        @type    maxsize:  C{int} or C{None}

        @keyword typed:
        @type    typed:    C{bool}
        """
        super().__init__()
        cache = functools.lru_cache(maxsize=maxsize, typed=typed)
        self._get_object = cache(self._create_object)
        self.info = self._get_object.cache_info

    def get(self, constructor, *args):
        """Returns a shared object, creates a new one if necessary."""
        return self._get_object(constructor, args)

    def wraps(self, constructor):
        """Wraps a constructor.

        The returned function is a new constructor that uses the object cache.

        Note: do not cache-wrap an already cache-wrapped constructor
        """
        def wrapper(*args):
            return self._get_object(constructor, args)

        return functools.update_wrapper(wrapper, constructor)
    # --- end of wraps (...) ---

# --- end of ObjectCache ---
