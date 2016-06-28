# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import urllib.parse
import urllib.request

from ..abc import loggable
from . import fs


__all__ = ["GetFile", "get_file", "get_file_write_to_file"]


def get_file(url, data=None, **kwargs):
    with GetFile(url, data, **kwargs) as file_getter:
        ret_data = file_getter.get_data()
    return ret_data
# --- end of get_file (...) ---


def get_file_write_to_file(filepath, url, data=None, **kwargs):
    with GetFile(url, data, **kwargs) as file_getter:
        file_getter.write_to_file(filepath)
# --- end of get_file_write_to_file (...) ---


class GetFile(loggable.AbstractLoggable):
    """Provides methods for getting files via urlopen().

    Example:
    >>> with GetFile("http://...") as file_getter:
    >>>     file_getter.write_to_file("./file")
    """

    # TODO: exception handling: some status codes/timeouts are worth a retry

    DEFAULT_TIMEOUT = 30
    DEFAULT_BLOCK_SIZE = 2**14

    def __init__(
        self, url, data=None, *,
        timeout=True, urlopen_kwargs=None, block_size=None, **kwargs
    ):
        super().__init__(**kwargs)
        self.request_url = url
        self.request_data = data
        self.request_timeout = (
            self.DEFAULT_TIMEOUT if timeout is True else timeout
        )
        self.request_kwargs = (
            {} if urlopen_kwargs is None else dict(urlopen_kwargs)
        )

        self.block_size = block_size

        self.info = None
        self._webh = None
    # ---

    def assert_webh_open(self):
        webh = self._webh
        if webh is None:
            raise AssertionError("not opened")
        return webh
    # ---

    def assert_webh_not_open(self):
        webh = self._webh
        if webh is not None:
            raise AssertionError("already opened")
    # ---

    def _urlopen(self):
        self.logger.debug("Opening file uri %r", self.request_url)
        return urllib.request.urlopen(
            self.request_url,
            data=self.request_data,
            timeout=self.request_timeout,
            **self.request_kwargs
        )
    # ---

    def __enter__(self):
        self.assert_webh_not_open()
        webh = self._urlopen()
        try:
            self.info = webh.info()
            self._webh = webh
        except:
            webh.close()
            raise

        return self
    # ---

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.info = None
        webh = self._webh
        if webh is not None:
            webh.close()
    # ---

    def read_blocks(self):
        block_size = self.block_size or self.DEFAULT_BLOCK_SIZE
        if not block_size:
            raise ValueError(block_size)

        webh = self.assert_webh_open()
        min_content_length = int(self.info.get("content-length", -1))

        self.logger.debug("Getting file from %r", self.request_url)

        data_length = 0
        block = webh.read(block_size)
        while block:
            data_length += len(block)
            yield block
            block = webh.read(block_size)
        # --

        if data_length < min_content_length:
            self.logger.warning(
                "Got incomplete file from %r", self.request_url
            )
            raise AssertionError("premature end of file")

        self.logger.debug("Successfully read file from %r", self.request_url)
    # ---

    def write_to_fh(self, fh):
        for block in self.read_blocks():
            fh.write(block)
    # ---

    def write_to_file(self, filepath):
        fs.prepare_output_file(filepath, move=True)
        with open(filepath, "wb") as fh:
            self.write_to_fh(fh)
    # ---

    def get_data(self):
        data = bytearray()
        for block in self.read_blocks():
            data.extend(block)
        return data
    # ---

# --- end of GetFile ---
