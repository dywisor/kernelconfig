# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os.path
import urllib.parse


__all__ = ["normalize_file_uri"]


def normalize_file_uri(file_uri):
    """
    Normalizes file uris referencing local files.

    @param file_uri:  input file uri, may be a filesystem path
                      ("/file/here", "relpath/to/file")
                      or a file uri ("http://...", "file://...", ...)
    @type  file_uri:  C{str}

    @return:  2-tuple (file uri scheme, normalized file uri)
              file uri scheme is None if the file uri points to a local file,
              otherwise it is a str, e.g. "http".
              For local files, the normalized file uri is a filesystem path,
              for remote files, it is the input file uri (e.g. "http://...")
    @rtype:   2-tuple (C{str}|C{None}, C{str})
    """
    file_uri_parsed = urllib.parse.urlparse(file_uri)
    file_uri_scheme = file_uri_parsed.scheme

    if not file_uri_scheme:
        # local file #1
        return (None, os.path.normpath(file_uri))

    elif file_uri_scheme == "file":
        # local file #2
        # file_uri.partition("://")[-1]
        return (None, os.path.normpath("".join(file_uri_parsed[1:])))

    else:
        # (probably) a remote file
        return (file_uri_scheme, file_uri)
# --- end of normalize_file_uri (...) ---
