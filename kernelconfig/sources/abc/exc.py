# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

CONFIG_SOURCE_EXCEPTIONS = [
    "ConfigurationSourceError",
    "ConfigurationSourceInvalidError",
    "ConfigurationSourceNotFound",
]


__all__ = CONFIG_SOURCE_EXCEPTIONS


class ConfigurationSourceError(Exception):
    """
    General error concerning configuration source objects and their creation.
    """
    pass


class ConfigurationSourceInvalidError(ConfigurationSourceError):
    """
    Uncreatable configuration source due to invalid/incomplete definition.
    """
    pass


class ConfigurationSourceNotFound(KeyError):
    """
    Uncreatable configuration source due to file not found or similar.
    """
    pass
