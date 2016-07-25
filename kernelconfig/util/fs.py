# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import errno
import os
import stat
import shutil

from . import fspath


__all__ = [
    "check_stat_mode_readable_file", "is_readable_file",
    "dodir", "dodir_for_file",
    "rmfile",
    "backup_file",
    "prepare_output_file",
    "walk_relpath"
]


class AbstractFsView(object, metaclass=abc.ABCMeta):
    __slots__ = []

    @abc.abstractmethod
    def get_path(self):
        raise NotImplementedError()

    def __str__(self):
        return str(self.get_path())

    def __repr__(self):
        return "{cls.__name__!s}({path!r})".format(
            path=self.get_path(), cls=self.__class__
        )

    def get_filepath(self, relpath=None):
        return fspath.join_relpath(self.get_path(), relpath)

# --- end of AbstractFsView ---


class FsView(AbstractFsView):
    __slots__ = ["__weakref__", "path"]

    def __init__(self, path):
        super().__init__()
        self.path = path

    def get_path(self):
        return self.path

# --- end of FsView ---


def check_stat_mode_readable_file(mode):
    """
    Returns True if the given stat mode indicates
    that the file could be opened for reading.
    """
    if stat.S_ISDIR(mode):
        return False

    elif stat.S_ISLNK(mode):
        return False

    # BLK, CHR, FIFO, REG, SOCK

    # in Python 3.4,
    # stat.S_ISDOOR(...)
    # stat.S_ISPORT(...)
    # stat.S_ISWHT(...)

    else:
        # assume true
        return True
# --- end of check_stat_mode_readable_file (...) ---


def is_readable_file(filepath, follow_symlinks=True):
    """Returns True if filepath points
    a regular file or a file that behaves similarily when opened for reading.
    """
    try:
        if follow_symlinks:
            sb = os.stat(filepath)
        else:
            sb = os.lstat(filepath)
    except OSError:
        return False

    return check_stat_mode_readable_file(sb.st_mode)
# --- end is_readable_file (...) ---


def dodir(dirpath, mkdir_p=True):
    try:
        if mkdir_p:
            os.makedirs(dirpath, exist_ok=True)
        else:
            os.mkdir(dirpath)
    except OSError:
        if not os.path.isdir(dirpath):
            raise
# --- end of dodir (...) ---


def dodir_for_file(filepath, mkdir_p=True):
    dodir(os.path.dirname(filepath), mkdir_p=mkdir_p)
# --- end of dodir_for_file (...) ---


def rmfile(filepath):
    try:
        os.unlink(filepath)
    except OSError:
        if os.path.lexists(filepath):
            raise
        else:
            return False
    return True
# --- end of rmfile (...) ---


def backup_file(
    orig_file, *, move=False, ignore_missing=False, bak_suffix=".bak"
):
    """
    Creates a backup of orig_file, either by copying or moving it.

    @param   orig_file:       file path
    @type    orig_file:       C{str}
    @keyword move:            whether to move (True) or copy the file (False)
                              Defaults to False.
    @type    move:            C{bool}
    @keyword ignore_missing:  whether to suppress OSError in case of missing
                              orig_file. Defaults to False.
    @type    ignore_missing:  C[bool}
    @keyword bak_suffix:      backup file suffix. Defaults to ".bak".
    @type    bak_suffix:      C{str}

    @return:  True if a backup has been created, else False
    @rtype:   C{bool}
    """
    dest = "%s%s" % (orig_file, bak_suffix)

    try:
        if move:
            shutil.move(orig_file, dest)
        else:
            shutil.copyfile(orig_file, dest)
    except (OSError, IOError) as err:
        if ignore_missing and err.errno == errno.ENOENT:
            return False
        raise
    else:
        return True
# --- end of backup_file (...) ---


def prepare_output_file(filepath, move=False):
    """Creates the directory for filepath,
    and a backup of the file if it exists.
    """
    dodir_for_file(filepath)
    backup_file(filepath, move=move, ignore_missing=True)
# --- end of prepare_output_file (...) ---


def walk_relpath(root, **walk_kwargs):
    abs_root = os.path.abspath(root)
    relpath_begin = 1 + len(abs_root)

    for dirpath, dirnames, filenames in os.walk(abs_root, **walk_kwargs):
        yield (dirpath, dirpath[relpath_begin:], dirnames, filenames)
# --- end of walk_relpath (...) ---
