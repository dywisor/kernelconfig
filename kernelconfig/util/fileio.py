# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import io
import os


__all__ = ["read_text_file_lines", "write_text_file_lines"]


def check_is_fileobj(suspect):
    return isinstance(suspect, io.TextIOBase)
# ---


def read_text_file_lines_from_fh(infile_fh, filename=None, rstrip=True):
    """Generator that reads lines from an already opened text file.

    @param   infile_fh:  input file obj
    @type    infile_fh:  fileobj
    @keyword filename:   name of the file. Defaults to None.
    @type    filename:   C{str} or C{None}
    @keyword rstrip:     chars to strip from the end of each text line;
                         May to False to disable rstrip altogether,
                         None for removing any whitespace,
                         or True for removing one '\n' newline char at the
                         end of each line. Defaults to True.
    @type    rstrip:     C{str} | C{None} | C{bool}

    @return: 2-tuple (line number, text line)
    @rtype:  2-tuple (C{int}, C{str})
    """
    if rstrip is True:
        preprocess_line = lambda l: (l[:-1] if (l and l[-1] == '\n') else l)
    elif rstrip is False:
        preprocess_line = lambda l: l
    else:
        preprocess_line = lambda l, _c=rstrip: l.rstrip(_c)
    # --

    for lino_m, line in enumerate(infile_fh):
        yield ((lino_m + 1), preprocess_line(line))
    # --
# --- end of read_text_file_lines_from_fh (...) ---


def read_text_file_lines(infile, filename=None, **kwargs):
    """Generator that reads lines from a text file.

    @param   infile:    input file, may be a file object or path
    @type    infile:    fileobj or C{str}
    @keyword filename:  name of the file. Defaults to None.
    @type    filename:  C{str} or C{None}
    @keyword rstrip:    chars to strip from the end of each text line;
                        May to False to disable rstrip altogether,
                        None for removing any whitespace,
                        or True for removing one '\n' newline char at the
                        end of each line. Defaults to True.
    @type    rstrip:    C{str} | C{None} | C{bool}

    @return: 2-tuple (line number, text line)
    @rtype:  2-tuple (C{int}, C{str})
    """
    if check_is_fileobj(infile):
        yield from read_text_file_lines_from_fh(
            infile, filename=filename, **kwargs
        )
    else:
        with open(infile, "rt") as fh:
            yield from read_text_file_lines_from_fh(
                fh, filename=(filename or infile), **kwargs
            )
# --- end of read_text_file_lines (...) ---


def write_text_file_lines_to_fh(
    outfile_fh, lines, filename=None, append_newline=True
):
    """Writes text lines to an already opened file.

    @param   outfile_fh:      output fileobj
    @type    outfile_fh:      fileobj
    @param   lines:           text lines / iterable of __str__()-able objects
    @type    lines:           iterable (list, genexpr, ...) of objects
    @keyword filename:        name of the output file. Defaults to None.
    @type    filename:        C{str} or C{None}
    @keyword append_newline:  str sequence that gets appended to each text line
                              May be True for L{os.linesep},
                              or any false value for disabling this behavior.
                              Defaults to True.
    @type    append_newline:  C{bool}|C{None} or C{str}

    @return: None (implicit)
    """
    if append_newline is True:
        append_newline = os.linesep
    # --

    if append_newline:
        outlines = ((str(l) + append_newline) for l in lines)  # genexpr
    else:
        outlines = map(str, lines)
    # --

    for line in outlines:
        outfile_fh.write(line)
# --- end of write_text_file_lines_to_fh (...) ---


def write_text_file_lines(outfile, lines, filename=None, **kwargs):
    """Writes text lines to a file.

    @param   outfile:         output file
    @type    outfile:         fileobj or C{str}
    @param   lines:           text lines / iterable of __str__()-able objects
    @type    lines:           iterable (list, genexpr, ...) of objects
    @keyword filename:        name of the output file. Defaults to None.
    @type    filename:        C{str} or C{None}
    @keyword append_newline:  str sequence that gets appended to each text line
                              May be True for L{os.linesep},
                              or any false value for disabling this behavior.
                              Defaults to True.
    @type    append_newline:  C{bool}|C{None} or C{str}

    @return: None (implicit)
    """
    if check_is_fileobj(outfile):
        write_text_file_lines_to_fh(
            outfile, lines, filename=filename, **kwargs
        )
    else:
        with open(outfile, "wt") as fh:
            write_text_file_lines_to_fh(
                fh, lines, filename=(filename or outfile), **kwargs
            )
# --- end of write_text_file_lines (...) ---
