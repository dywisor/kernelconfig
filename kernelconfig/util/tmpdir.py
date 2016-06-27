# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import errno
import os
import sys
import shutil
import tempfile
import weakref

from . import fs
from . import fspath


__all__ = ["Tmpdir"]


class _Tmpdir(object):
    __slots__ = ["__weakref__", "_path"]

    def __init__(self, **kwargs):
        super().__init__()
        self._path = None
        self._setup_finalizer()
        self._init_tmpdir(**kwargs)

    def _setup_finalizer(self):
        raise NotImplementedError()

    def _init_tmpdir(self, **kwargs):
        assert self._path is None
        self._path = tempfile.mkdtemp(**kwargs)

    def __str__(self):
        return str(self._path)

    def get_filepath(self, relpath=None):
        return fspath.join_relpath(self._path, relpath)
    # ---

    def copyfile(self, relpath, dst):
        src = self.get_filepath(relpath)
        shutil.copyfile(src, dst)
    # ---

    def rmfile(self, relpath):
        filepath = self.get_filepath(relpath)
        os.unlink(filepath)

    def rmfile_ifexist(self, relpath):
        try:
            self.rmfile(relpath)
        except OSError as oserr:
            if oserr.errno != errno.ENOENT:
                raise

    def _cleanup(self):
        if not self._path:
            return

        shutil.rmtree(self._path)
        self._path = None
    # ---

    def mkdir(self, relpath):
        """
        @return:  path to created directory
        @rtype:   C{str}
        """
        filepath = self.get_filepath(relpath)
        os.mkdir(filepath)
        return filepath

    def dodir(self, relpath, mkdir_p=False):
        """
        @return:  path to existing/created directory
        @rtype:   C{str}
        """
        filepath = self.get_filepath(relpath)
        fs.dodir(filepath, mkdir_p)
        return filepath

    def get_new_subdir(self):
        """
        Creates a new, unique subdirectory in the tmpdir,
        and returns its fspath.

        The subdir is cleaned up together with its parent,
        but can also be removed prior to that manually.

        @return:  path to sub-tmpdir
        @rtype:   C{str}
        """
        return tempfile.mkdtemp(prefix="privtmp", dir=self._path)
# ---


def _finalize_tmpdir(obj_ref):
    obj = obj_ref()
    if obj is not None:
        obj._cleanup()


if sys.hexversion >= 0x3040000:
    class Tmpdir(_Tmpdir):
        _finalizers = []

        def _setup_finalizer(self):
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

        def _setup_finalizer(self):
            atexit.register(_finalize_tmpdir, weakref.ref(self))
