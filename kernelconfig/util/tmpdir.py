# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import errno
import os
import sys
import shutil
import tempfile
import weakref

from . import fs


__all__ = ["Tmpdir", "TmpdirView", "get_tmpdir_or_view"]


class _FileWrapper(object):

    def __init__(self, fh, path):
        super().__init__()
        self.fh = fh
        self.path = path

    def close(self):
        return self.fh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
# ---


class _FsDir(fs.FsView):
    __slots__ = []

    def copyfile(self, relpath, dst):
        src = self.get_filepath(relpath)
        shutil.copyfile(src, dst)
    # ---

    def rmfile(self, relpath):
        filepath = self.get_filepath(relpath)
        os.unlink(filepath)
    # ---

    def rmfile_ifexist(self, relpath):
        try:
            self.rmfile(relpath)
        except OSError as oserr:
            if oserr.errno != errno.ENOENT:
                raise
    # ---

    def mkdir(self, relpath):
        """
        @return:  path to created directory
        @rtype:   C{str}
        """
        filepath = self.get_filepath(relpath)
        os.mkdir(filepath)
        return filepath
    # ---

    def dodir(self, relpath, mkdir_p=False):
        """
        @return:  path to existing/created directory
        @rtype:   C{str}
        """
        filepath = self.get_filepath(relpath)
        fs.dodir(filepath, mkdir_p)
        return filepath
    # ---

# --- end of _FsDir (...) ---


class TmpdirView(_FsDir):
    __slots__ = []

    def __bool__(self):
        return bool(self.path)

    def get_new_subdir_path(self):
        """
        Creates a new, unique subdirectory in the tmpdir,
        and returns its fspath.

        The subdir is cleaned up together with its parent,
        but can also be removed prior to that manually.

        @return:  path to sub-tmpdir
        @rtype:   C{str}
        """
        return tempfile.mkdtemp(prefix="privtmp", dir=self.path)

    def _create_subdir_view(self, absolute_path):
        # not self.__class__!
        return TmpdirView(absolute_path)

    def get_new_subdir(self):
        """
        Creates a new, unique subdirectory in the tmpdir,
        and returns a TmpdirView object.

        The subdir is cleaned up together with its parent,
        but can also be removed prior to that manually.

        @return:  tmpdir view object
        @rtype:   L{TmpdirView}
        """
        # not self.__class__()!
        return self._create_subdir_view(self.get_new_subdir_path())

    def get_subdir(self, relpath, mkdir_p=True):
        """
        Creates a named subdirectory in the tmpdir if it does not exist yet,
        and returns a TmpdirView object.

        The subdir is cleaned up together with its parent,
        but can also be removed prior to that manually.

        @param   relpath:  name of the subdirectory
        @type    relpath:  C{str} or C{None}
        @keyword mkdir_p:  whether to create parent directories if necessary
                           Defaults to True.
        @type    mkdir_p:  C{bool}

        @return:  tmpdir view object
        @rtype:   L{TmpdirView}
        """
        # empty relpath is accepted, results in a view of self
        return self._create_subdir_view(self.dodir(relpath, mkdir_p=True))

    def _mkstemp(self, text=True):
        return tempfile.mkstemp(dir=self.path, text=text)

    def get_new_file(self):
        """Creates a new, unique file in the tmpdir and returns its fspath.

        The file is cleaned up together with its parent,
        but can also be removed prior to that manually.

        @return:  path to file
        @rtype:   C{str}
        """
        file_fd, file_path = self._mkstemp()
        os.close(file_fd)
        return file_path

    def open_new_file(self, text=True):
        """Creates a new, unique file in the tmpdir
        and returns a file object for writing to it and its fspath.

        The file is cleaned up together with its parent,
        but can also be removed prior to that manually.

        @return:  object with fh, path attributes
        @rtype:   L{_FileWrapper}
        """
        file_fd, file_path = self._mkstemp(text=text)
        try:
            file_fh = os.fdopen(file_fd, "w" + ("t" if text else "b"))
        except:
            os.close(file_fd)
            raise

        return _FileWrapper(file_fh, file_path)
    # ---

# --- end of TmpdirView ---


class _Tmpdir(TmpdirView):
    __slots__ = []

    def __init__(self, **kwargs):
        super().__init__(None)
        self._setup_finalizer()
        self._init_tmpdir(**kwargs)

    def _setup_finalizer(self):
        raise NotImplementedError()

    def _init_tmpdir(self, **kwargs):
        assert self.path is None
        self.path = tempfile.mkdtemp(**kwargs)

    def _cleanup(self):
        if not self.path:
            return

        shutil.rmtree(self.path)
        self.path = None
    # ---

    def __del__(self):
        self._cleanup()

# ---


def _finalize_tmpdir(obj_ref):
    obj = obj_ref()
    if obj is not None:
        obj._cleanup()


if sys.hexversion >= 0x3040000:
    class Tmpdir(_Tmpdir):
        __slots__ = []
        _finalizers = []

        def _setup_finalizer(self):
            # pylint: disable=E1101
            self.__class__._finalizers.append(
                weakref.finalize(self, _finalize_tmpdir, weakref.ref(self))
            )

else:
    import atexit

    def _atexit_tmpdir_cleanup(obj_ref):
        obj = obj_ref()
        if obj is not None:
            obj._cleanup()

    class Tmpdir(_Tmpdir):
        __slots__ = []

        def _setup_finalizer(self):
            atexit.register(_finalize_tmpdir, weakref.ref(self))
# -- end if


def get_tmpdir_or_view(arg, parent=None):
    """
    @param   arg:
    @type    arg:     C{None} | C{str} | [subclass-of] L{TmpdirView}
    @keyword parent:  either None or parent tmpdir [view] object
                      whose get_new_subdir() method is called to create a
                      tmpdir when arg is None
    @type    parent:  C{None} | [subclass-of] L{TmpdirView}

    @return:  tmpdir or tmpdir view
    @rtype:   [subclass-of] L{TmpdirView}
    """
    if arg is None:
        if parent is not None:
            return parent.get_new_subdir()
        else:
            return Tmpdir()

    elif isinstance(arg, str):
        return TmpdirView(arg)

    elif isinstance(arg, TmpdirView):
        return arg

    else:
        raise TypeError(arg)
# --- end of get_tmpdir_or_view (...) ---
