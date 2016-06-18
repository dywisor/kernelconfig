# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import configparser

from . import fileio


__all__ = ["read_settings_file"]


def read_settings_file(filepath, config_parser=None):
    """Reads a kernelconfig settings file.

    A settings file is in ini-like file format,
    and consists of several sections,
    e.g. "[source]" for curated source-related configuration.

    It also contains an "[options]" section that is used to modify the
    kernel configuration.
    The format inside this section is not compatible with configparser,
    and therefore this function exists.

    It filters out the "[options]" section of the input file,
    lets the config parser read all other sections,
    and returns a 2-tuple (config parser, lines from "[options]" or None).

    @param filepath:         path to settings file
    @type  filepath:         C{str}
    @keyword config_parser:  config parser to use
                             if None (the default), a new will be created

    @return:  2-tuple (config parser, lines from "[options]" or None)
    """
    if config_parser is None:
        config_parser = get_default_config_parser()

    cfg_parser_ret, unparsed_sections = _read_settings_file(
        config_parser, {"options", }, filepath
    )

    return (cfg_parser_ret, unparsed_sections.get("options"))
# --- end of read_settings_file (...) ---


def _read_settings_file(config_parser, passthrough_sections, filepath):
    """Reads a settings file.

    The content of a settings file is of mixed format.
    A considerable part is in ini-file format,
    whereas certain sections must be parsed separately.

    This section stores "unparseable" (non-ini) sections from the given
    input file in a section name => lines dict,
    and passes all other sections to the config parser's read_file() method.

    Note: does not handle a few configparser features correctly,
          for example indented sections (not important for this project)

    @param config_parser:         ini parser
    @param passthrough_sections:  sections whose text lines should not be
                                  parsed
    @param filepath:              input file

    @return:  2-tuple (config_parser, dict :: passthrough_section => lines)
    """
    sectcre = config_parser.SECTCRE

    config_lines = []
    unparsed_sections = {}

    dst = config_lines
    for lino, line in fileio.read_text_file_lines(filepath):
        sect_match = sectcre.match(line)

        if not sect_match:
            dst.append(line)

        else:
            sect_name = sect_match.group("header").lower()
            if sect_name in passthrough_sections:
                if sect_name in unparsed_sections:
                    dst = unparsed_sections[sect_name]
                else:
                    dst = []
                    unparsed_sections[sect_name] = dst

                # no-append section header

            else:
                dst = config_lines
                dst.append(line)
        # --
    # --

    config_parser.read_file(config_lines, source=filepath)
    return (config_parser, unparsed_sections)
# --- end of _read_settings_file (...) ---


def get_default_config_parser():
    # This is the config parser as it's used in the original project.
    #
    # However, settings files are not really ini files, except for the
    # section headers, so the ConfigParser part of this module may be replaced
    # in future.
    #
    return configparser.RawConfigParser(
        delimiters="|", allow_no_value=True, comment_prefixes="#"
    )
# --- end of get_default_config_parser (...) ---
