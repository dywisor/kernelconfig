# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
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

        file_uri = args[0]
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

        if self.file_uri_scheme:
            # remote file
            arg_config.set_need_tmpdir()

        arg_config.file_uri = self.file_uri

        return arg_config
    # ---

    def do_prepare_set_outfiles(self, arg_config):
        if self.file_uri_scheme:
            assert not arg_config.outconfig
            arg_config.outconfig = os.path.join(arg_config.tmpdir, "config")
    # ---

    def do_get_conf_basis(self, arg_config):
        if self.file_uri_scheme:
            assert arg_config.outconfig
            fileget.get_file_write_to_file(
                arg_config.outconfig, arg_config.file_uri, logger=self.logger
            )
            return self.create_conf_basis_for_file(arg_config.outconfig)
        else:
            assert not arg_config.outconfig
            return self.create_conf_basis_for_file(arg_config.file_uri)
    # ---

# --- end of FileConfigurationSource ---
