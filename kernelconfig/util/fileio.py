# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import io


__all__ = ["read_text_file_lines"]


class _TextFileIOWrapper(object):
    """
    An open(<file>) wrapper that deals with file objects and paths.

    @ivar is_filepath:   whether the file is a fspath or not
    @type is_filepath:   C{bool}

    @ivar _file:         the file object or path as passed to __init__()
    @type _file:         undef

    @ivar _mode:         mode for L{open()}, only used for file paths
    @type _mode:         C{str}
    @ivar _encoding:     file encoding, only used for file paths
    @type _encoding:     C{str} or C{None}
    @ivar _open_kwargs:  additional keyword args passed to open()
    @type _open_kwargs:  C{dict}

    @ivar _fh:           opened fileobj, only used for file paths
    @type _fh:           fileobj
    """

    @classmethod
    def check_is_fileobj(cls, suspect):
        """Checks whether 'suspect' is an already opened text file.

        @param suspect:  file object or path
        @type  suspect:  fileobj or C{str}

        @return: True/False
        @rtype:  C{bool}
        """
        # or hasattr(suspect, read|write + __iter__),
        #  but this would also allow IO objects that read bytes, not str
        return isinstance(suspect, io.TextIOBase)
    # --- end of check_is_fileobj (...) ---

    def __init__(self, fpath_or_fileobj, mode, encoding="utf-8", **kwargs):
        super().__init__()

        self._fh = None
        self._mode = mode
        self._encoding = encoding
        self._open_kwargs = kwargs

        if self.__class__.check_is_fileobj(fpath_or_fileobj):
            self.is_filepath = False
            self._file = fpath_or_fileobj
        else:
            self.is_filepath = True
            self._file = str(fpath_or_fileobj)
        # ---
    # ---

    def _open(self):
        if self.is_filepath:
            self._fh = open(
                self._file, self._mode,
                encoding=self._encoding, **self._open_kwargs
            )
            return self._fh
        else:
            return self._file
    # ---

    def _close(self):
        fh = self._fh
        if fh is not None:
            fh.close()
            self._fh = None
    # --- end of _close (...) ---

    def __enter__(self):
        return self._open()
    # ---

    def __exit__(self, exc_type, exc_value, exc_traceback):
        return self._close()
    # ---
# ---


def read_text_file_lines(infile, filename=None, rstrip=True):
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
    if rstrip is True:
        preprocess_line = lambda l: (l[:-1] if (l and l[-1] == '\n') else l)
    elif rstrip is False:
        preprocess_line = lambda l: l
    else:
        preprocess_line = lambda l, _c=rstrip: l.rstrip(_c)

    with _TextFileIOWrapper(infile, "rt") as fh:
        for lino_m, line in enumerate(fh):
            yield ((lino_m + 1), preprocess_line(line))
# --- end of read_text_file_lines (...) ---


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
