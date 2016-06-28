# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import errno
import os
import shutil

__all__ = [
    "dodir", "dodir_for_file",
    "rmfile",
    "backup_file",
    "prepare_output_file"
]


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
