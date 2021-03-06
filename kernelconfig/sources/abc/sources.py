# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections.abc
import sys

from ...abc import loggable
from . import exc


__all__ = ["AbstractConfigurationSources"]


class AbstractConfigurationSources(
    loggable.AbstractLoggable, collections.abc.Mapping
):
    """
    A collection of 'dynamic' sources providing configuration basis objects.

    Usually, only a subset of all sources is required at runtime,
    and this class takes care of lazy-loading the sources,
    derived classes must be implement the actual creation
    (but not the lazy-load logic).

    @ivar _sources:  a mapping of already loaded configuration sources
    @type _sources:  dict :: C{str} => sub-of L{AbstractConfigurationSource}
    """

    __slots__ = ["_sources"]

    @abc.abstractmethod
    def create_source_by_name(self, source_name):
        """
        This method creates a new configuration source object.

        Derived classes must implement this method.
        Its sole input is the requested source name,
        everything else is up to the actual implementation.

        It should raise appropriate exceptions on errors, namely
        ConfigurationSourceNotFound if the requested source does not exist,
        or a [subclass of] ConfigurationSourceError on construction errors.

        It may also return None if the requested source does not exist.

        It must not register the created configuration source with
        the sources mapping of this object.


        @param source_name:  name of the requested configuration source
        @type  source_name:  C{str}

        @return:  configuration source object or None
        @rtype:   subclass of L{AbstractConfigurationSource} or C{None}
        """
        raise NotImplementedError()
    # --- end of create_source_by_name (...) ---

    def load_available_sources(self):
        """
        Tries to construct and add all available configuration sources.

        THe names of sources that have been loaded are returned as a list,
        while sources that could not be constructed are returned as
        a name => exc_info dict.

        Whether this method replaces existing configuration sources
        with new objects is up to the actual implementation.

        @return:  2-tuple (
                     list of loaded sources' names,
                     dict of failed sources' names
                  )
        @return:  2-tuple (
                     C{list} of C{str},
                     C{dict} :: C{str} => None | exc_info 3-tuple
                  )
        """
        sources_loaded = []
        sources_failed = {}

        for source_name, source_info in self.iter_available_sources_info():
            #  source_info discarded
            source, source_exc_info = self.load_source(source_name)

            if source_exc_info is not None:
                assert source_name not in sources_failed
                sources_failed[source_name] = source_exc_info

            elif source is None:
                # false positive
                pass

            else:
                sources_loaded.append(source.name)
        # --

        return (sources_loaded, sources_failed)
    # --- end of load_available_sources (...) ---

    @abc.abstractmethod
    def iter_available_sources_info(self):
        """
        Generator that yields information about sources
        that could be constructed with create_source_by_name().

        Note that there is no guarantee that the sources
        can actually be constructed.

        Derived classes must implement this method.
        It should not create ConfigurationSource objects
        (that is a task for create_source_by_name()),
        but instead provide basic information about available sources
        such as name and origin (e.g. definition file path).

        Source names must be unique.

        @return:  2-tuples (source name, source info)
        @rtype:   2-tuples (C{str}, C{object})
        """
        raise NotImplementedError()
    # --- end of iter_available_sources (...) ---

    def get_available_sources_info(self):
        """Returns a dict with information about available sources."""
        return dict(self.iter_available_sources_info())
    # --- end of get_available_sources_info (...) ---

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sources = {}
    # --- end of __init__ (...) ---

    def __len__(self):
        """
        Returns the number of loaded configuration sources.

        There is a loose relation between this number
        and the number of available config sources.
        Usually, |loaded| <= |avail|.
        But as register_source() can be used to add 'unavailable' sources
        (sources which can not be created by get_source()),
        the number of loaded configuration sources is <= |avail| + |unavail|.

        IOW, this value is not meaningful for determining the total number of
        sources, unless all available sources have been loaded and
        no 'unavailable' have been registered.

        @return: number of loaded configuration sources
        @rtype:  C{int}
        """
        return len(self._sources)

    def __iter__(self):
        """Iter over the configuration sources' names."""
        return iter(self._sources)

    def __getitem__(self, key):
        """Get a configuration source by name, creating it if necessary.

        @param key:  configuration source name
        @type  key:  C{str}

        @return:  configuration source object
        @rtype:   subclass of L{AbstractConfigurationSource}
        """
        return self.get_source(key)

    def iter_sources(self):
        """Sorted iteration over the configuration source objects."""
        sources = self._sources
        return (sources[k] for k in sorted(sources))

    def get_sources(self):
        """Returns a sorted list of all loaded configuration sources.

        @return:  sorted list of loaded configuration sources
        @rtype:   C{list} of sub-of L{AbstractConfigurationSource}
        """
        return list(self.iter_sources())

    def get_names(self):
        """
        Returns a sorted list of the names of all loaded configuration sources.

        @return:  sorted list of config source names
        @rtype:   C{list} of C{str}
        """
        return [s.name for s in self.iter_sources()]

    def get_source_key(self, source):
        """Returns a key
        for storing a configuration source in the sources mapping.

        This should return a str, and the return value of
        get_source_key(s) must be equal to that of get_source_name_key(s.name)

           get_source_key(source) == get_source_name_key(source.name)

        @param source:  configuration source object
        @type  source:  subclass of L{AbstractConfigurationSource}

        @return:  key
        @rtype:   C{str}
        """
        return self.get_source_name_key(source.name)

    def get_source_name_key(self, source_name):
        """Returns a key
        for retrieving a configuration source from the sources mapping.

        No inverse function exists, it is not possible to convert
        a key to a source name, only via sources[key].name.

        @param source_name:  configuration source name
        @type  source_name:  C{str}

        @return:  key
        @rtype:   C{str}
        """
        if not source_name:
            raise ValueError()
        return source_name.lower()

    def register_source(self, source, assert_key=None):
        """
        Adds a configuration source to the sources mapping.

        The source's key is determined with get_source_key(source).

        The 'assert_key' parameter can be used to assure that the
        calculated key matches the expected key.

        On success, the configuration source object is "taken over"
        (a.k.a. "ref-copy with sole claim"), its logger gets reassigned.

        @raises ValueError: if key could not be determined,
                            or if key != assert_key (and assert_key is set)

        @raises KeyError:   if a source with the same key exists already


        @param   source:      configuration source
        @type    source:      subclass of L{AbstractConfigurationSource}
        @keyword assert_key:  if not-None: verify that the calculated key
                              is equal to this key
        @type    assert_key:  C{str}

        @return:  None (implicit)
        """
        key = self.get_source_key(source)

        if not key:
            raise ValueError("key must be non-empty")

        elif assert_key is not None and (key != assert_key):
            raise ValueError(
                "key does not meet callers expectations: {} != {}".format(
                    key, assert_key
                )
            )

        elif key in self._sources:
            raise KeyError("duplicate entry for {}".format(key))

        if hasattr(source, "set_logger"):
            source.set_logger(self.get_child_logger(source.name))
        # --

        self._sources[key] = source
    # --- end of register_source (...) ---

    def get_existing_source(self, source_name):
        """Returns a configuration source, referenced by name.

        Does not try to create it if it doesn't exist yet,
        raises a KeyError instead.

        @param source_name:  configuration source name
        @type  source_name:  C{str}

        @return:  configuration source object
        @rtype:   subclass of L{AbstractConfigurationSource}
        """
        source_key = self.get_source_name_key(source_name)
        return self._sources[source_key]
    # --- end of get_existing_source (...) ---

    def get_source(self, source_name):
        """Returns a configuration source, referenced by name.

        If the configuration source is already loaded,
        this method returns it immediately.

        Otherwise, create_source_by_name() is called,
        which should construct the configuration source if it is available,
        and raise appropriate exceptions on errors,
        e.g. ConfigurationSourceNotFound.

        It can also return None, in which case this method takes care of
        raising a "not found" exception.

        This may involve arbitrary code - e.g. filesystem operations.

        @param source_name:  configuration source name
        @type  source_name:  C{str}

        @return:  configuration source object
        @rtype:   subclass of L{AbstractConfigurationSource}
        """
        source_key = self.get_source_name_key(source_name)
        try:
            return self._sources[source_key]
        except KeyError:
            pass

        source = self.create_source_by_name(source_name)
        if source is None:
            raise exc.ConfigurationSourceNotFound(source_name)

        self.register_source(source, source_key)
        return source
    # --- end of get_source (...) ---

    def load_source(self, source_name):
        """Tries to return a configuration source, referenced by name.

        Mostly identical to get_source(),
        but catches errors and returns a 2-tuple (conf_source, exc_info).
        conf_source is always None on errors,
        and exc_info may be None even on errors.

        The following result tuples are possible:
        * (None,   None)    --  error: source not found
        * (None,  <obj>)    --  error: source failed to load
        * (<obj>,  None)    --  success: source loaded

        This method is named "load_source" because of its intended use case,
        load_available_sources().

        @param source_name:  configuration source name
        @type  source_name:  C{str}

        @return:  2-tuple (configuration source object, exc_info),
                  not-None exc_info implies None configuration source object
        @rtype:   2-tuple (
                    C{None} or subclass of L{AbstractConfigurationSource},
                    C{None} or exc_info 3-tuple
                  )
        """
        try:
            source = self.get_source(source_name)

        except exc.ConfigurationSourceNotFound:
            return (None, None)

        except exc.ConfigurationSourceError:
            return (None, sys.exc_info())

        else:
            return (source, None)
    # --- end of load_source (...) ---

    def get_configuration_basis(self, source_name, source_argv=None):
        """
        Returns a configuration basis
        for the given configuration source and requested input parameters.

        @param   source_name:  configuration source name
        @type    source_name:  C{str}

        @keyword source_argv:  optional arguments passed to the source
                               (get_configuration_basis())
                               May be None for no args, defaults to None.
        @type    source_argv:  C{None} or C{list} of C{str}


        @return:  configuration basis (a list of config files)
        @rtype:   C{list} of C{str}
        """
        source = self.get_source(source_name)
        return source.get_configuration_basis(source_argv)
    # --- end of get_configuration_basis (...) ---

# --- end of AbstractConfigurationSources ---
