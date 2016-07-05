# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

CONFIG_SOURCE_EXCEPTIONS = [
    "ConfigurationSourceError",
    "ConfigurationSourceInvalidError",
    "ConfigurationSourceNotFound",
]


__all__ = CONFIG_SOURCE_EXCEPTIONS


def get_tuple(item):
    # duplicate function?!
    if isinstance(item, str):
        return (item, )
    elif hasattr(item, "__iter__") or hasattr(item, "__next__"):
        return tuple(item)
    else:
        return (item, )
# --- end of get_tuple (...) ---


class ConfigurationSourceError(Exception):
    """
    General error concerning configuration source objects and their creation.
    """
    pass


class ConfigurationSourceNotFound(KeyError):
    """
    Uncreatable configuration source due to file not found or similar.
    """
    pass


class ConfigurationSourceInitError(ConfigurationSourceError):
    pass


class ConfigurationSourceInvalidError(ConfigurationSourceInitError):
    """
    Uncreatable configuration source due to invalid/incomplete definition.
    """
    pass


class ConfigurationSourceMissingType(ConfigurationSourceInvalidError):
    pass


class ConfigurationSourceInvalidParameterDef(
    ConfigurationSourceInvalidError
):
    pass


class ConfigurationSourceArchNotSupported(ConfigurationSourceInitError):

    def __init__(self, source_name, *, archs=None, supported_archs=None):
        self.archs = get_tuple(archs)
        self.supported_archs = get_tuple(supported_archs)

        message = (
            (
                'source {name!s} does not support '
                'the requested target architecture '
                '(have: {archs}; supported: {sup_archs})'
            ).format(
                name=(source_name or "???"),
                archs=(", ".join(map(str, self.archs)) or "???"),
                sup_archs=(", ".join(map(str, self.supported_archs)) or "???")
            )
        )

        super().__init__(message)
    # ---
#


class ConfigurationSourceRunError(ConfigurationSourceError):
    pass


class ConfigurationSourceExecError(ConfigurationSourceRunError):
    """
    Uncreatable configuration source due to failing command.
    """
    pass


class ConfigurationSourceFeatureError(ConfigurationSourceRunError):
    pass


class ConfigurationSourceFeatureNotSupported(ConfigurationSourceFeatureError):
    pass


class ConfigurationSourceFeatureUnknown(ConfigurationSourceFeatureError):
    pass


class ConfigurationSourceFeatureUsageError(ConfigurationSourceFeatureError):
    pass
