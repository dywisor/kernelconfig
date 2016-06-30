# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import os.path


from ...util import fspath


__all__ = ["Outfile", "TmpOutfile"]


class AbstractOutfile(object, metaclass=abc.ABCMeta):
    """An output file whose path is known at initialization time.

    @param path:  path to the file (None if unknown, which should only
                  be used by subclasses)
    @type  path:  C{str} or C{None}

    @ivar  name:  name of the file (readonly)
    @type  name:  C{str}
    @ivar  dir:   directory path of the file (dirname(file)) (readonly)
    @type  dir:   C{str}
    """
    __slots__ = ["path"]

    @abc.abstractmethod
    def get_key(self):
        """Returns a unique identifier for the outfile.

        @return: unique identifier
        @rtype:  C{str}
        """
        raise NotImplementedError()

    def __hash__(self):
        return hash(self.get_key())

    def __init__(self, path):
        super().__init__()
        self.path = os.path.normpath(path) if path else path

    @abc.abstractmethod
    def copy(self):
        raise NotImplementedError()

    def get_path(self):
        """
        @raises AttributeError:  if path is not set

        @return:  path to outfile
        @rtype:   C{str}
        """
        path = self.path
        if not path:
            raise AttributeError("path is not set")
        return path

    @property
    def name(self):
        return os.path.basename(self.get_path())

    @property
    def dir(self):  # builtin name
        return os.path.dirname(self.get_path())

    @abc.abstractmethod
    def assign_tmpdir(self, tmpdir):
        """
        Assigns the outfile to a temporary directory,
        modifying the outfile's path.

        May be a no-op if the outfile's path does not depend on a tmpdir.
        """
        raise NotImplementedError()

    def __str__(self):
        return str(self.get_path())

    def __repr__(self):
        return "{cls.__name__}({path!r})".format(
            cls=self.__class__, path=self.path
        )

# --- end of AbstractOutfile ---


class Outfile(AbstractOutfile):
    __slots__ = []

    def get_key(self):
        return self.get_path()

    def copy(self):
        return self.__class__(self.path)

    def assign_tmpdir(self, tmpdir):
        pass
# --- end of Outfile ---


class TmpOutfile(AbstractOutfile):
    """
    An output file whose path is unknown until a temporary directory
    has been assigned to the config source arg config object.

    @ivar _name:  name of the file (path relative to tmpdir)
    @type _name:  C{str}
    """
    __slots__ = ["_name"]

    def get_key(self):
        return self._name

    def __init__(self, name):
        super().__init__(None)
        self._name = fspath.normalize_relpath(name)

    def copy(self):
        # path is not copied
        return self.__class__(self._name)

    def assign_tmpdir(self, tmpdir):
        # if not self.path:
        self.path = os.path.join(tmpdir, self._name)

    def __repr__(self):
        return "{cls.__name__}({name!r})".format(
            cls=self.__class__, name=self._name
        )

# --- end of TmpOutfile ---
