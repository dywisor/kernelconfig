# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import errno
import os
import sys
import shutil
import tempfile
import weakref

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

    def get_filepath(self, relpath=None):
        norm_relpath = (
            os.path.normpath(relpath.strip(os.path.sep))
            if relpath else None
        )
        if norm_relpath and norm_relpath != ".":
            return os.path.join(self._path, norm_relpath)
        else:
            return self._path
    # ---

    def copyfile(self, relpath, dst):
        src = self.get_filepath(relpath)
        shutil.copyfile(src, dst)
    # ---

    def rmfile(self, relpath):
        fspath = self.get_filepath(relpath)
        os.unlink(fspath)

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
