# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os

from . import _sourcebase
from ..abc import exc
from .._util import _misc


__all__ = ["LocalFileConfigurationSource"]


class LocalFileConfigurationSource(_sourcebase.ConfigurationSourceBase):
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
        self.filepath_is_dynamic = None

    def check_source_valid(self):
        if not self.filepath:
            raise exc.ConfigurationSourceInvalidError("empty filepath")

        elif (
            not self.filepath_is_dynamic
            and not os.access(self.filepath, os.R_OK)
        ):
            raise exc.ConfigurationSourceInvalidError(
                "config file does not exist or is not readable: {!r}".format(
                    self.filepath
                )
            )
        # --
    # --- end of check_source_valid (...) ---

    def add_auto_var(self, varname, varkey):
        # automatic vars are not supported by this class
        return False

    def _set_file_uri(self, file_uri_arg, allow_dynamic_uri):
        """
        @param file_uri_arg:       (input) file uri
        @type  file_uri_arg:       C{str}
        @param allow_dynamic_uri:  whether dynamic file uris should be allowed
                                   or not.
                                   Dynamic file uris are get str-formatted
                                   after argparsing in get_configuration_basis
        @type  allow_dynamic_uri:  C{bool}

        @return:  None (implicit)
        """
        str_formatter = self.get_str_formatter()
        try:
            file_uri = str_formatter.format(file_uri_arg)

        except (KeyError, IndexError):
            if allow_dynamic_uri:
                file_uri = file_uri_arg
                file_uri_is_dynamic = True
            else:
                raise exc.ConfigurationSourceInvalidError(
                    "file uri needs dynamic str-formatting", file_uri_arg
                )

        else:
            file_uri_is_dynamic = False
        # --

        # --- copy of fileuri.py, _set_file_uri() ends here ---

        self.filepath_is_dynamic = file_uri_is_dynamic
        if file_uri_is_dynamic:
            self.filepath = file_uri
        else:
            # normpath() for eliminating redundant leading slashes
            #  this is an limitation caused by how "local file" source types
            #  are created from settings (they must start with "/")
            self.filepath = os.path.normpath(file_uri)
    # --- end of _set_file_uri (...) ---

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

        self._set_file_uri(args[0], False)
        return []
    # --- end of init_from_settings (...) ---

    def init_from_def(self, source_def):
        super().init_from_def(source_def)

        file_uri_arg = source_def.get("path")
        if file_uri_arg:
            self._set_file_uri(file_uri_arg, True)
            # else check_source_valid() will complain about it
    # --- end of init_from_def (...) ---

    def get_configuration_basis(self, args):
        fmt_vars = {}

        if self.arg_parser is not None:
            # allow None args
            params, argv_rem = self.arg_parser.parse_args(args or [])
            if argv_rem:
                raise exc.ConfigurationSourceFeatureUsageError(
                    'this configuration source does not accept '
                    'arbitrary parameters'
                )
            # --
            fmt_vars.update(
                _misc.get_parameter_format_vars_from_parsed_args(params)
            )

        elif args:
            raise exc.ConfigurationSourceFeatureUsageError(
                "this configuration source does not accept parameters"
            )
        # --

        if self.filepath_is_dynamic:
            str_formatter = self.get_str_formatter()
            # this behaves slightly different than the 'dynamic' str formatter
            # from PhasedConfigurationSourceBase,
            # uppercase/mixedcase param_ vars do not get recognized
            # and lead to KeyErrors
            filepath = str_formatter.vformat(self.filepath, (), fmt_vars)
        else:
            filepath = self.filepath
        # --

        if os.path.isabs(filepath):
            outconfig = filepath
        else:
            outconfig = self.senv.get_config_file_path(filepath)
            if not outconfig:
                raise exc.ConfigurationSourceNotFound("files", filepath)

        return self.create_conf_basis_for_file(outconfig)
    # --- end of get_configuration_basis (...) ---

# --- end of LocalFileConfigurationSource ---
