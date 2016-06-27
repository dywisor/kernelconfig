# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections.abc
import re

from . import fileio


__all__ = ["SettingsFileReader"]


class SettingsFileReader(collections.abc.Mapping):

    # ^"["<name>"]" ["#"...]$
    SECTION_REGEXP = re.compile(
        '^[\[](?P<header>[^\[\]]+)[\]]\s*(?:[#].*)?$'
    )

    COMMENT_LINE_REGEXP = re.compile(r'^\s*[#]')

    @classmethod
    def new_from_file(cls, filepath):
        obj = cls()
        obj.read_file(filepath)
        return obj
    # --- end of new_from_file (...) ---

    def __init__(self):
        super().__init__()
        self.data = {}

    def __len__(self):
        return len(self.data)

    def get_section_key(self, sect_name):
        if isinstance(sect_name, str):
            return sect_name.lower().replace("-", "_")
        else:
            return sect_name

    def __getitem__(self, key):
        return self.data[self.get_section_key(key)]

    def __iter__(self):
        return iter(self.data)

    def _get_or_create_section(self, sect_key):
        try:
            sect = self.data[sect_key]
        except KeyError:
            sect = []
            self.data[sect_key] = sect
        return sect
    # ---

    def read_file(self, filepath):
        """Reads a kernelconfig settings file.

        A settings file is in ini-like file format,
        and consists of several sections,
        e.g. "[source]" for curated source-related configuration.

        Each section has its own format which is usually not compatible
        with configparser, and therefore this function exists.

        The "[options]" section that is used to modify
        the kernel configuration, is in "macros lang" format.

        The "[source]" section that is used for specifying the input .config
        file, is in a shell script-like format.

        This function simply splits reads the sections of the settings file
        into a dict :: section name => list of text lines.

        Note: does not handle a few configparser/.ini features correctly,
              for example indented sections (not important for this project)

        @param filepath:         path to settings file (or file obj)
        @type  filepath:         C{str} (or file obj)
        """

        _get_or_create_section = self._get_or_create_section
        sect_regexp = self.SECTION_REGEXP

        nosection_lines = []

        dst = nosection_lines
        for lino, line in fileio.read_text_file_lines(filepath):
            sect_match = sect_regexp.match(line)

            if sect_match:
                dst = _get_or_create_section(
                    self.get_section_key(sect_match.group("header"))
                )
                # no-append section header

            elif dst or line:
                dst.append(line)
            # --
        # --

        if nosection_lines:
            _get_or_create_section(None).extend(nosection_lines)
    # ---

    def iter_section(self, name, ignore_missing=False, skip_comments=False):
        def filter_comments(lines):
            nonlocal skip_comments
            is_comment = self.COMMENT_LINE_REGEXP.match

            if skip_comments:
                for line in lines:
                    if line and not is_comment(line):
                        yield line

            else:
                for line in lines:
                    yield line
        # ---

        try:
            sect_lines = self[name]
        except KeyError:
            if ignore_missing:
                return
            raise

        yield from filter_comments(sect_lines)
    # --- end of iter_section (...) ---

    def get_section(self, name, **kwargs):
        return list(self.iter_section(name, **kwargs))
    # --- end of get_section (...) ---

# --- end of SettingsFileReader ---
