# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import collections.abc
import enum

from . import source as _source

__all__ = [
    "ConfigurationSourceTypeIdentifier",
    "get_source_types", "get_source_type"
]


@enum.unique
class ConfigurationSourceTypeIdentifier(enum.IntEnum):
    """
    An enum of all basic configuration source type identifiers.
    A complete source type consists of a type identifier (one of this enum)
    and a subtype, which denotes the type further.
    Not all types support subtypes, in that case it should be None.

    @cvar s_unknown:   a undefined source
    @cvar s_file:      a .config file-type source, no subtype accepted
    @cvar s_make:      a make target-type source,
                       subtype denotes the make target
    @cvar s_script:    a script-type source,
                       subtype denotes the interpreter
    @cvar s_pym:       a Python Module-type source, no subtype accepted
    @cvar s_source:    a curated source,
                       which needs to be resolved to one of the other types
                       before being usable, no subtype accepted
    """
    (
        s_unknown,
        s_file,
        s_command,
        s_make,
        s_script,
        s_pym,
        s_source
    ) = range(7)

    def get_name(self):
        return self.name[2:]  # pylint: disable=E1101

    __str__ = get_name

# ---


_ConfigurationSourceTypeBase = collections.namedtuple(
    "ConfigurationSourceType",
    "source_type source_subtype source_cls"
)


class ConfigurationSourceType(_ConfigurationSourceTypeBase):
    """
    A configuration source type descriptor.

    It consists of a type identifier,
    @ivar source_type:     source type identifier  (readonly)
    @type source_type:     L{ConfigurationSourceTypeIdentifier}

    a subtype, which may be None in case if the type does not support it,
    @ivar source_subtype:  source subtype identifier, optional (readonly)
    @type source_subtype:  undef, usually C{None} or C{str}

    and a configuration source class, which may be None if not supported.
    @ivar source_cls:      configuration source class or C{None} (readonly)
                           must implement two constructor (class) methods:
                           * new_from_settings([cls,] <4 args>, **kwargs)
                           * new_from_def([cls,] <3 args>, **kwargs)
    @type source_cls:      C{None}
                           or type T, T is subclass of ConfigurationSourceBase
    """

    def is_of_type(self, source_type):
        """
        Returns True if the type identifier of this source type
        is exactly the given identifier.

        @param source_type:  source type identifier
        @type  source_type:  L{ConfigurationSourceTypeIdentifier}

        @return:  "is of type <source_type>?"
        @rtype:   C{bool}
        """
        return self.source_type is source_type

    def is_source(self):
        """
        Returns True if this source type represents a "curated source",
        and False otherwise.

        @return: "is curated source?"
        @rtype:  C{bool}
        """
        return self.is_of_type(ConfigurationSourceTypeIdentifier.s_source)

    def get_name(self):
        """Returns the name of this type.

        @return:  type identifier name
        @rtype:   C{str}
        """
        return self.source_type.get_name()

    def __str__(self):
        return "{!s}".format(self.source_type)

    def __repr__(self):
        return "{cls.__name__}({t!r})".format(
            t=self.source_type, cls=self.__class__
        )

# --- end of ConfigurationSourceType ---


class ConfigurationSourceTypes(collections.abc.Mapping):
    """
    A collection of all known configuration source type descriptors.

    @ivar source_types:  type name (or alias) to type descriptor mapping
    @type source_types:  C{dict} :: C{str} => L{ConfigurationSourceType}
    """
    __slots__ = ["source_types"]

    @classmethod
    def new_default_instance(cls):
        """
        Creates a new instance and adds all known source types to it.

        @return:  configuration source types
        @rtype:   L{ConfigurationSourceTypes}
        """
        obj = cls()

        # an alternative to the source type creation here would be
        # source type creation inside the source type classes,
        # and just registering the objects here,
        # e.g.
        # obj.register_source_type_object(
        #     _source.FileConfigurationSource.SOURCE_TYPE
        # )
        #
        obj.add_source_type(
            "file",
            source_type=ConfigurationSourceTypeIdentifier.s_file,
            source_subtype=None,
            source_cls=_source.FileConfigurationSource,
            aliases=[]
        )

        obj.add_source_type(
            "local_file",
            source_type=ConfigurationSourceTypeIdentifier.s_file,
            source_subtype=None,
            source_cls=_source.LocalFileConfigurationSource,
            aliases=[]
        )

        obj.add_source_type(
            "command",
            source_type=ConfigurationSourceTypeIdentifier.s_command,
            source_subtype=None,
            source_cls=_source.CommandConfigurationSource,
            aliases=["cmd"]
        )

        obj.add_source_type(
            "make",
            source_type=ConfigurationSourceTypeIdentifier.s_make,
            source_subtype=None,
            source_cls=_source.MakeConfigurationSource,
            aliases=["mk"]
        )

        # make command w/ target source_subtype
        obj.add_source_type(
            "defconfig",
            source_type=ConfigurationSourceTypeIdentifier.s_make,
            source_subtype=True,
            source_cls=_source.MakeConfigurationSource,
            aliases=[]
        )

        obj.add_source_type(
            "script",
            source_type=ConfigurationSourceTypeIdentifier.s_script,
            source_subtype=None,
            source_cls=_source.ScriptConfigurationSource,
            aliases=[]
        )

        # embedded script w/ lang source_subtype
        obj.add_source_type(
            "sh",
            source_type=ConfigurationSourceTypeIdentifier.s_script,
            source_subtype=True,
            source_cls=_source.ScriptConfigurationSource,
            aliases=[]
        )

        obj.add_source_type(
            "pym",
            source_type=ConfigurationSourceTypeIdentifier.s_pym,
            source_subtype=None,
            source_cls=_source.PymConfigurationSource,
            aliases=["pymod"]
        )

        obj.add_source_type(
            "source",
            source_type=ConfigurationSourceTypeIdentifier.s_source,
            source_subtype=None,
            source_cls=None,
            aliases=[]
        )

        return obj
    # --- end of new_default_instance (...) ---

    def __init__(self):
        super().__init__()
        self.source_types = {}

    def normalize_key(self, key):
        return key.lower()

    def __getitem__(self, key):
        return self.source_types[self.normalize_key(key)]

    def __iter__(self):
        return iter(self.source_types)

    def __len__(self):
        return len(self.source_types)

    def _register_source_type_object(self, name, source_type_obj):
        """
        Adds a new configuration source type object.
        See register_source_type_object() for details.

        @raises KeyError:  if a type for the given name already exists

        @param   name:            name of the source type
        @type    name:            C{str}
        @param   source_type_obj: source type object
        @type    source_type_obj: L{ConfigurationSourceType}
        @keyword aliases:         either None or a list of alias names
                                  Defaults to None
        @type    aliases:         C{None} or iterable of C{str}

        @return:  None (implicit)
        """
        lname = self.normalize_key(name)

        if lname in self.source_types:
            raise KeyError("duplicate entry for {}".format(lname))

        self.source_types[lname] = source_type_obj
    # ---

    def add_source_type_alias(self, name, alias_name):
        """Creates an alias for an existing entry referenced by name.

        @raises KeyError:  if alias name already used

        @param name:        name of an existing type
        @type  name:        C{str}
        @param alias_name:  new alias name
        @type  alias_name:  C{str}

        @return:  None
        """
        return self._register_source_type_object(
            alias_name, self.source_types[self.normalize_key(name)]
        )
    # ---

    def register_source_type_object(self, name, source_type_obj, aliases=None):
        """
        Adds a new configuration source type object, its name must be unique.

        @raises KeyError:  if a type for the given name already exists

        @param   name:            name of the source type
        @type    name:            C{str}
        @param   source_type_obj: source type object
        @type    source_type_obj: L{ConfigurationSourceType}
        @keyword aliases:         either None or a list of alias names
                                  Defaults to None.
        @type    aliases:         C{None} or iterable of C{str}

        @return:  None (implicit)
        """
        self._register_source_type_object(name, source_type_obj)
        if aliases:
            for alias_name in aliases:
                self._register_source_type_object(alias_name, source_type_obj)
    # ---

    def add_source_type(
        self, name, *, source_type, source_subtype, source_cls, aliases=None
    ):
        """Creates a new configuration source type and adds it.

        @raises KeyError:  if a type for the given name already exists

        @param   name:            name of the source type
        @type    name:            C{str}
        @keyword source_type:     source type (mandatory kw)
        @type    source_type:     L{ConfigurationSourceTypeIdentifier}
        @keyword source_subtype:  source subtype (mandatory kw)
        @type    source_subtype:  undef, usually C{str} or C{Npne}
        @keyword source_cls:      source class  (mandatory kw)
        @type    source_cls:      C{type} or C{None}
        @keyword aliases:         either None or a list of alias names
                                  Defaults to None.
        @type    aliases:         C{None} or iterable of C{str}

        @return:  None (implicit)
        """
        source_type_obj = ConfigurationSourceType(
            source_type,
            (
                self.normalize_key(name) if source_subtype is True
                else source_subtype
            ),
            source_cls
        )
        self.register_source_type_object(
            name, source_type_obj, aliases=aliases
        )
    # ---

# --- end of ConfigurationSourceTypes ---


class _ConfigurationSourceTypeModuleVars(object):
    """
    Namespace for the default source_types instance.

    It provides two class-wide methods,

    * get_source_types()       --  get the source types, create if necessary
    * get_source_type(name)    --  get the source type descriptor for <name>

    Do not instantiate this class.
    """
    _source_types = None

    @classmethod
    def get_source_types(cls):
        """
        Returns the default configuration source types instances
        and creates it if necessary.

        @return:  configuration source types
        @rtype:   L{ConfigurationSourceTypes}
        """
        source_types = cls._source_types
        if source_types is None:
            source_types = ConfigurationSourceTypes.new_default_instance()
            cls._source_types = source_types
            assert source_types is not None
        return source_types

    @classmethod
    def get_source_type(cls, source_type_name):
        """Returns the type descriptor for the given type name.

        @raises KeyError:  unknown type name

        @return:  configuration source type descriptor
        @rtype:   L{ConfigurationSourceType}
        """
        return cls.get_source_types()[source_type_name]
# ---


get_source_types = _ConfigurationSourceTypeModuleVars.get_source_types
get_source_type = _ConfigurationSourceTypeModuleVars.get_source_type
