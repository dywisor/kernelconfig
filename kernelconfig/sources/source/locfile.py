# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

from . import _base
from ..abc import exc


__all__ = ["LocalFileConfigurationSource"]


class LocalFileConfigurationSource(_base.ConfigurationSourceBase):
    """
    Configuration source type for local files only.

    Although local files can also be handled by FileConfigurationSource,
    this type bypasses the "phase" system and simply the file path directly.

    @ivar filepath:  path to the input .config file
    @type filepath:  C{str}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filepath = None

    def init_from_settings(self, subtype, args, data):
        if data:
            raise exc.ConfigurationSourceInvalidError("non-empty data")
        # --

        if subtype:
            raise exc.ConfigurationSourceInvalidError("non-empty subtype")
        # --

        if not args or not args[0]:
            raise exc.ConfigurationSourceInvalidError("missing file path")
        elif len(args) > 1:
            raise exc.ConfigurationSourceInvalidError("too many args")
        # --

        self.filepath = args[0]
        return []
    # ---

    def get_configuration_basis(self, args):
        if args:
            raise exc.ConfigurationSourceInvalidError("non-empty args")
        # --

        # FIXME: str-format
        return self.create_conf_basis_for_file(self.filepath)
    # --- end of get_configuration_basis (...) ---

# --- end of LocalFileConfigurationSource ---
