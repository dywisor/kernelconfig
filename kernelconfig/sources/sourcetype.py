# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import enum

from . import source as _source

__all__ = [
    "ConfigurationSourceTypeIdentifier",
    "get_source_types", "get_source_type"
]


@enum.unique
class ConfigurationSourceTypeIdentifier(enum.IntEnum):
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

    def is_of_type(self, source_type):
        return self.source_type is source_type

    def is_source(self):
        return self.is_of_type(ConfigurationSourceTypeIdentifier.s_source)

    def get_name(self):
        return self.source_type.get_name()

    def __str__(self):
        return "{!s}".format(self.source_type)

    def __repr__(self):
        return "{cls.__name__}({t!r})".format(
            t=self.source_type, cls=self.__class__
        )

# --- end of ConfigurationSourceType ---


class ConfigurationSourceTypes(object):
    __slots__ = ["source_types"]

    @classmethod
    def new_default_instance(cls):
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

    def _register_source_type_object(self, name, source_type_obj):
        lname = self.normalize_key(name)

        if lname in self.source_types:
            raise KeyError("duplicate entry for {}".format(lname))

        self.source_types[lname] = source_type_obj
    # ---

    def add_source_type_alias(self, name, alias_name):
        return self._register_source_type_object(
            alias_name, self.source_types[self.normalize_key(name)]
        )
    # ---

    def register_source_type_object(self, name, source_type_obj, aliases=None):
        lname = self.normalize_key(name)

        self._register_source_type_object(lname, source_type_obj)
        if aliases:
            for alias_name in aliases:
                self._register_source_type_object(alias_name, source_type_obj)
    # ---

    def add_source_type(
        self, name, *, source_type, source_subtype, source_cls, aliases=None
    ):
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
    _source_types = None

    @classmethod
    def get_source_types(cls):
        source_types = cls._source_types
        if source_types is None:
            source_types = ConfigurationSourceTypes.new_default_instance()
            cls._source_types = source_types
            assert source_types is not None
        return source_types

    @classmethod
    def get_source_type(cls, source_type_name):
        return cls.get_source_types()[source_type_name]
# ---


get_source_types = _ConfigurationSourceTypeModuleVars.get_source_types
get_source_type = _ConfigurationSourceTypeModuleVars.get_source_type
