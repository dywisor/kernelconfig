# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import io


__all__ = ["read_text_file_lines"]


def _read_text_file_lines_from_fh(fh, filename, strip):
    if strip is True:
        preprocess_line = lambda l: (l[:-1] if (l and l[-1] == '\n') else l)
    elif strip is False:
        preprocess_line = lambda l: l
    else:
        preprocess_line = lambda l, _c=strip: l.strip(_c)

    for lino_m, line in enumerate(fh):
        yield ((lino_m + 1), preprocess_line(line))
    # --
# --- end of _read_text_file_lines_from_fh (...) ---


def read_text_file_lines(infile, filename=None, strip=True):
    # or hasattr(infile, read|readlines + __iter__),
    #  but this would also allow IO objects that read bytes, not str
    if isinstance(infile, io.TextIOBase):
        # infile is an already opened file (opened in text mode)
        # #fname = filename or getattr(infile, "name", None)
        yield from _read_text_file_lines_from_fh(infile, filename, strip)

    else:
        # infile is filepath
        fpath = str(infile)
        # #fname = filename or fpath
        with open(fpath, "rt") as fh:
            yield from _read_text_file_lines_from_fh(fh, filename, strip)
    # --
# ---
