# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os.path
import urllib.parse

from . import _base
from ..abc import exc

from ...util import fileget


__all__ = ["FileConfigurationSource"]


class FileConfigurationSource(_base.PhasedConfigurationSourceBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_uri = None
        self.file_uri_scheme = None

    @property
    def file_is_local(self):
        return not self.file_uri_scheme

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

        str_formatter = self.get_str_formatter()

        # normpath() not strictly needed here (see locfile.py)
        file_uri = os.path.normpath(str_formatter.format(args[0]))
        file_uri_parsed = urllib.parse.urlparse(file_uri)

        if not file_uri_parsed.scheme:
            # local file
            self.file_uri = file_uri
            self.file_uri_scheme = None

        elif file_uri_parsed.scheme == "file":
            # local file #2
            self.file_uri = file_uri[0].partition("://")[-1]
            assert self.file_uri
            self.file_uri_scheme = None

        else:
            # (probably) remote file
            self.file_uri = file_uri
            self.file_uri_scheme = file_uri_parsed.scheme

        return []
    # --- end of init_from_settings (...) ---

    def do_parse_source_argv(self, argv):
        if argv:
            raise exc.ConfigurationSourceInvalidError("non-empty args")
        # --

        arg_config = _base.ConfigurationSourceArgConfig()
        arg_config.file_uri = None  # new attr

        file_uri = self.file_uri

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
            fileget.get_file_write_to_file(
                arg_config.get_outconfig_path(),
                arg_config.file_uri, logger=self.logger
            )

        return self.create_conf_basis_for_arg_config(arg_config)
    # ---

# --- end of FileConfigurationSource ---
