# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import weakref
import os.path


from . import fileget
from . import fileuri
from . import tmpdir as _tmpdir


__all__ = [
    "create_file_reference",
    "LocalFileReference", "RemoteFileReference", "GetFileReference",
]


def create_file_reference(file_uri_arg, **remote_kwargs):
    is_remote_file, file_uri = fileuri.normalize_file_uri(file_uri_arg)

    if is_remote_file:
        return GetFileReference(file_uri, **remote_kwargs)
    else:
        return LocalFileReference(file_uri)
# --- end of create_file_reference (...) ---


class AbstractFileReference(object, metaclass=abc.ABCMeta):
    __slots__ = []

    def __str__(self):
        return self.get_file()

    @abc.abstractmethod
    def get_file(self, *, logger=None):
        """
        @param logger:  logger or None, defaults to None

        @return:  path to the file
        @rtype:   C{str}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_local(self):
        """
        @return:  whether the referenced file is local or not
        @rtype:   C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_ready(self):
        """
        @return:  whether the referenced file is ready
                  (exists locally // has been downloaded)
        @rtype:   C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_file(self):
        """
        @return:  whether the referenced file is a regular file
        @rtype:   C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_dir(self):
        """
        @return:  whether the referenced file is a directory
        @rtype:   C{bool}
        """
        raise NotImplementedError()

# --- end of AbstractFileReference ---


class LocalFileReference(AbstractFileReference):
    """Reference to a file that exists locally,
    i.e. does not need to be downloaded.

    @ivar _filepath:  path to the file
    @type _filepath:  C{str}
    """
    __slots__ = ["_filepath"]

    def is_local(self):
        return True

    def __init__(self, filepath):
        super().__init__()
        self._filepath = filepath

    def get_file(self, *, logger=None):
        return self._filepath

    def is_file(self):
        return os.path.isfile(self.get_file())

    def is_dir(self):
        return os.path.isdir(self.get_file())

    def is_ready(self):
        return True

# --- end of LocalFileReference ---


class RemoteFileReference(AbstractFileReference):
    """
    Reference to a file that has to be downloaded.

    Base class, derived classes need to implement one method, fetch_file().
    It receives a tmpfile object and a logger as args
    and should download the file and write it to tmpfile.fh
    (or tmpfile.path after tmpfile.close()).

    Derived classes may also implement a release_get_file_data(),
    which is called after downloading the file, and can be used to destroy
    data structures that were only necessary for fetch_file().

    @cvar _shared_tmpdir_ref:   weak reference to the shared tmpdir
                                that is used for storing the downloaded files
                                unless a RemoteFileReference specifies its
                                own tmpdir.

                                It points to the same tmpdir as long as one
                                RemoteFileReference object using it is alive.
                                Otherwise, it may need to be reinitialized,
                                which is handled in get_shared_tmpdir().
    @type _shared_tmpdir_ref:   weakref to L{Tmpdir}

    @ivar _filepath:            path to the downloaded file
                                Initially None, since the file needs to
                                be retrieved first.
    @type _filepath:            C{None} or C{str}

    @ivar _tmpdir:              tmpdir used by this file ref
                                Initially None, set to the default tmpdir
                                when downloading the file.
                                May be overridden via __init__(tmpdir=...).
    @type _tmpdir:              C{None} or L{TmpdirView}

    @ivar _is_text_file:        whether the file to-be-downloaded is a text
                                file or a binary file,
                                this affects how the temporary file is opened.
                                Defaults to binary (False).
    @type _is_text_file:        C{bool}
    """
    __slots__ = ["_filepath", "_tmpdir", "_is_text_file"]

    _shared_tmpdir_ref = None

    @classmethod
    def get_shared_tmpdir(cls):
        shared_tmpdir_ref = cls._shared_tmpdir_ref
        if shared_tmpdir_ref is None:
            shared_tmpdir = None
        else:
            shared_tmpdir = shared_tmpdir_ref()
        # --

        if shared_tmpdir is None:
            shared_tmpdir = _tmpdir.Tmpdir(suffix=".fileref")
            assert shared_tmpdir is not None
            cls._shared_tmpdir_ref = weakref.ref(shared_tmpdir)
        # --

        return shared_tmpdir
    # --- end of get_shared_tmpdir (...) ---

    def __init__(self, *, text=False, tmpdir=None):
        super().__init__()
        self._filepath = None
        self._tmpdir = tmpdir
        self._is_text_file = text

    def is_local(self):
        return False

    def is_ready(self):
        return bool(self._filepath)

    def is_file(self):
        # by assumption, all remote files are regular files
        return True

    def is_dir(self):
        return False

    def _get_tmpdir(self):
        tmpdir = self._tmpdir
        if tmpdir is None:
            tmpdir = self.get_shared_tmpdir()
            # it is important to keep a ref to tmpdir in self as long
            # as _tmpfile is set, otherwise it gets removed too early
            self._tmpdir = tmpdir
        # --
        return tmpdir
    # --- end of _get_tmpdir (...) ---

    def _open_tmpfile(self):
        return self._get_tmpdir().open_new_file(text=self._is_text_file)
    # --- end of _open_tmpfile (...) ---

    @abc.abstractmethod
    def fetch_file(self, tmpfile, *, logger=None):
        """
        @param tmpfile:  fetch-file destination, an object with two attributes
                           * fh   -- an already opened file handle
                           * path -- path to the tmpfile
        @type  tmpfile:  L{tmpdir._FileWrapper}

        @return: None
        """
        raise NotImplementedError()

    def release_get_file_data(self):
        pass

    def get_file(self, *, logger=None):
        filepath = self._filepath
        # if unset, the file has to be retrieved first
        if filepath is None:
            with self._open_tmpfile() as tmpfile:
                self.fetch_file(tmpfile, logger=logger)
                filepath = tmpfile.path
            # --
            self._filepath = filepath
            # release data structs no longer necessary
            # after retrieving the file
            # (destructive - fetch_file() will no longer work)
            self.release_get_file_data()
        # --

        return filepath
    # --- end of get_file (...) ---

# --- end of RemoteFileReference ---


class GetFileReference(RemoteFileReference):
    """Reference to a remote file that is downloaded using fileget.GetFile.

    @ivar _file_getter:  get-file instance, released after fetch_file()
    @type _file_getter:  L{GetFile} or C{None}
    """
    __slots__ = ["_file_getter"]

    def __init__(self, url, data=None, *, text=False, tmpdir=None, **kwargs):
        super().__init__(text=text, tmpdir=tmpdir)
        self._file_getter = fileget.GetFile(url, data=data, **kwargs)

    def fetch_file(self, tmpfile, *, logger=None):
        file_getter = self._file_getter
        if logger is not None:
            file_getter.set_logger(logger)

        with file_getter:
            file_getter.write_to_fh(tmpfile.fh)

    def release_get_file_data(self):
        self._file_getter = None

# --- end of GetFileReference ---
