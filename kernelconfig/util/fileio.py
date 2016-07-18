# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import bz2
import codecs
import gzip
import io
import mimetypes
import os


__all__ = ["read_text_file_lines", "write_text_file_lines"]


class _Compression(object):
    MIME_TYPES = mimetypes.MimeTypes()

    COMP_MAP = {
        "bzip2":  bz2.BZ2File,
        "gzip":   gzip.GzipFile,
    }

    @classmethod
    def _guess_file_type(cls, filepath):
        return cls.MIME_TYPES.guess_type(filepath)

    @classmethod
    def guess_compression(cls, filepath):
        return cls.COMP_MAP.get(cls._guess_file_type(filepath)[-1])

# --- end of _Compression ---


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


def read_text_file_lines(infile, filename=None, encoding="utf-8", **kwargs):
    """Generator that reads lines from a text file.

    Supports reading of gzip- or bzip2-compressed files
    based on mimetypes detection.

    @param   infile:    input file, may be a file object or path
    @type    infile:    fileobj or C{str}
    @keyword filename:  name of the file. Defaults to None.
    @type    filename:  C{str} or C{None}
    @keyword encoding:  input file encoding, defaults to "utf-8"
    @type    encoding:  C{str}
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
        open_compressed = _Compression.guess_compression(infile)

        if open_compressed is not None:
            enc_reader = codecs.getreader(encoding)

            with open_compressed(infile, "rb") as ch:
                yield from read_text_file_lines_from_fh(
                    enc_reader(ch), filename=(filename or infile), **kwargs
                )
            # -- end with
        else:
            with open(infile, "rt", encoding=encoding) as fh:
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


class LineContBuffer(object):

    def __init__(self):
        super().__init__()
        self.buf = []

    def __bool__(self):
        return bool(self.buf)

    def append(self, line):
        self.buf.append(line.lstrip() if self.buf else line)

    def emit(self):
        ret = "".join(self.buf)
        self.buf = []
        return ret
# ---


def accumulate_line_cont(lines, ignore_eof=True):
    lbuf = LineContBuffer()
    for line in lines:
        if line and line[-1] == '\\':
            lbuf.append(line[:-1])
        else:
            lbuf.append(line)
            yield lbuf.emit()

    if not lbuf:
        pass
    elif ignore_eof:
        yield lbuf.emit()
    else:
        raise ValueError(
            "reached EOF while reading a line continuation sequence"
        )
# ---
