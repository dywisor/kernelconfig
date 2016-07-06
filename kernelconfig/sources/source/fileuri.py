# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os.path
import urllib.parse

from . import _sourcebase
from ..abc import exc
from .._util import _fileget


__all__ = ["FileConfigurationSource"]


class FileConfigurationSource(_sourcebase.PhasedConfigurationSourceBase):
    """
    @ivar file_uri:
    @type file_uri:             C{str} (or C{None})
    @ivar file_uri_scheme:      remote file scheme (e.g. "http"),
                                None for local files
    @type file_uri_scheme:      C{None} or C{str}
    @ivar file_uri_is_dynamic:  whether the file uri needs to be str-formatted
                                after arg parsing or not
    @type file_uri_is_dynamic:  C{bool}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_uri = None
        self.file_uri_scheme = None
        self.file_uri_is_dynamic = None

    @property
    def file_is_local(self):
        return not self.file_uri_scheme

    def check_source_valid(self):
        if not self.file_uri:
            raise exc.ConfigurationSourceInvalidError("empty file uri")

    def add_auto_var(self, varname, varkey):
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

        #  urllib.parse.urlparse on format str?
        file_uri_parsed = urllib.parse.urlparse(file_uri)
        file_uri_scheme = file_uri_parsed.scheme

        if file_uri_is_dynamic:
            if file_uri_scheme and any((c in "{}" for c in file_uri_scheme)):
                raise exc.ConfigurationSourceInvalidError(
                    "format var in scheme part of dynamic file uri",
                    file_uri
                )
        # --

        self.file_uri_is_dynamic = file_uri_is_dynamic

        if not file_uri_scheme:
            # local file
            self.file_uri = os.path.normpath(file_uri)
            self.file_uri_scheme = None

        elif file_uri_scheme == "file":
            # local file #2
            self.file_uri = os.path.normpath("".join(file_uri_parsed[1:]))
            # self.file_uri = file_uri[0].partition("://")[-1]
            self.file_uri_scheme = None

        else:
            # (probably) remote file
            self.file_uri = file_uri
            self.file_uri_scheme = file_uri_scheme
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

    def do_parse_source_argv(self, argv):
        arg_config = super().do_parse_source_argv(argv)
        arg_config.file_uri = None  # new attr

        if self.file_uri_is_dynamic:
            str_formatter = self.get_dynamic_str_formatter(arg_config)
            file_uri = str_formatter.format(self.file_uri)
        else:
            file_uri = self.file_uri
        # --

        if self.file_uri_scheme:
            # remote file
            arg_config.add_tmp_outfile("config")
            arg_config.file_uri = file_uri

        else:
            if os.path.isabs(file_uri):
                outconfig = file_uri
                # if not file-like outconfig exists: outconfig = None
            else:
                outconfig = self.senv.get_config_file_path(file_uri)
            # --

            if not outconfig:
                raise exc.ConfigurationSourceNotFound(file_uri)

            arg_config.add_outconfig(outconfig)
            # arg_config.file_uri not used
        # --
        return arg_config
    # ---

    def do_get_conf_basis(self, arg_config):
        if self.file_uri_scheme:
            _fileget.get_file_write_to_file(
                arg_config.get_outconfig_path(),
                arg_config.file_uri, logger=self.logger
            )

        return self.create_conf_basis_for_arg_config(arg_config)
    # ---

# --- end of FileConfigurationSource ---
