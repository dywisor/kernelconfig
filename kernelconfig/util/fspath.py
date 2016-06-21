# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import itertools
import os


__all__ = [
    "strip_relpath", "normalize_relpath",
    "join_relpath", "join_relpaths", "join_relpaths_v",
    "dirprefix", "dirsuffix", "dirproduct",
    "get_home_dir", "get_user_config_dir",
]


def strip_relpath(relpath, *, _osp_sep=os.path.sep):
    """Removes "/" chars from the beginning and end of a relative path."""
    return relpath.strip(_osp_sep)
# --- end of strip_relpath (...) ---


def normalize_relpath(relpath, *, _osp_normpath=os.path.normpath):
    """Remvoes "/" chars from the beginning and end of a relative path,
    and normalizes it.
    """
    return _osp_normpath(strip_relpath(relpath))
# --- end of normalize_relpath (...) ---


def normalize_relpath_if_nonempty(relpath):
    """Same as normalize_relpath(), but returns None for 'empty' relpaths."""
    return normalize_relpath(relpath) if relpath else None
# --- end of normalize_relpath_if_nonempty (...) ---


def join_relpath(dirpath, relpath, *, _osp_join=os.path.join):
    """Interprets 'relpath' relative to (dirpath + "/")
    and returns its absolute path.

    The relpath may be empty or None, in which case the dirpath is returned.

    @param dirpath:  directory path
    @type  dirpath:  C{str}
    @param relpath:  path relative to dirpath, may be None or False
    @type  relpath:  C{str} or C{None} or anything "false"

    @return:  absolute path
    @rtype:   C{str}
    """
    norm_relpath = normalize_relpath_if_nonempty(relpath)

    if norm_relpath and norm_relpath != ".":
        return _osp_join(dirpath, relpath)
    else:
        return dirpath
# --- end of join_relpath (...) ---


def join_relpaths_v(
    dirpath, relpath_elements, *,
    _osp_join=os.path.join, _osp_normpath=os.path.normpath
):
    """
    Interprets the first relpath relative to (dirpath + "/")
    and all subsequent relpaths relative to their predecessor.

    The 'relpath_elements' argument may be None or empty,
    in which case 'dirpath' is returned.

    The resulting path is normalized so that ".." references get eliminated.

    join_relpaths_v(D, [a, b]) ===
       os.path.normpath(join_relpath(join_relpath(D, a), b))

    @param dirpath:           directory path
    @type  dirpath:           C{str}
    @param relpath_elements:  None or list of relpath elements that should
                              be append to dirpath
    @type  relpath_elements:  C{None} or C{list} of C{str}

    @return:  absolute path
    @rtype:   C{str}
    """

    if not relpath_elements:
        return _osp_normpath(dirpath)

    parts = [
        w for w in map(normalize_relpath_if_nonempty, relpath_elements) if w
    ]

    if parts:
        return _osp_normpath(_osp_join(dirpath, *parts))
    else:
        return _osp_normpath(dirpath)
# --- end of join_relpaths_v (...) ---


def join_relpaths(dirpath, *relpath_elements):
    """var-args variant of join_relpaths_v()."""
    return join_relpaths_v(dirpath, *relpath_elements)
# --- end of join_relpaths (...) ---


def dirprefix(dirpath, names, *, _osp_join=os.path.join):
    """
    Prefixes each name in names with d + "/".

    @param dirpath:   directory path
    @type  dirpath:   C{str}
    @param names:     list of names
    @type  names:     C{list} of C{str}

    @return: list of filesystem paths
    @rtype:  C{list} of C{str}
    """
    return (
        _osp_join(dirpath, normalize_relpath(name)) for name in names
    )
# --- end of dirprefix (...) ---


def dirsuffix(dirpaths, name, *, _osp_join=os.path.join):
    """
    Suffixes each dir in dirpaths with "/" + name.

    @param dirpaths:  list of directory paths
    @type  dirpaths:  C{list} of C{str}
    @param name:      name
    @type  name:      C{str}

    @return: list of filesystem paths
    @rtype:  C{list} of C{str}
    """
    norm_name = normalize_relpath(name)
    return (_osp_join(dirpath, norm_name) for dirpath in dirpaths)
# --- end of dirsuffix (...) ---


def dirproduct(
    dirpaths, names, *,
    _osp_join=os.path.join, _it_product=itertools.product
):
    """Combines each dirpath in dirpaths with each name in names,
    separated by a "/" char.

    @param dirpaths:  list of directory paths
    @type  dirpaths:  C{list} of C{str}
    @param names:     list of names
    @type  names:     C{list} of C{str}

    @return: list of filesystem paths
    @rtype:  C{list} of C{str}
    """
    return (
        _osp_join(dirpath, name) for dirpath, name in _it_product(
            dirpaths, map(normalize_relpath, names)
        )
    )
# --- end of dirproduct (...) ---


def get_home_dir(user=None):
    """Returns the path to the user's home directory.

    @raises ValueError:  if home directory can not be determined,
                         or if home directory is "/".

    @keyword user:  if set and non-empty: get home dir path of another user
                    Defaults to None.
    @type    user:  C{None} or C{str}

    @return: home directory path
    @rtype:  C{str}
    """
    tilde_arg = "~" if not user else ("~%s" % user)

    home_dir = os.path.expanduser(tilde_arg)
    if (
        not home_dir
        or not strip_relpath(home_dir)
        or home_dir == tilde_arg
    ):
        # There might be cases where $HOME is actually "/",
        # but the "/" is also caused by expanduser("~") and empty $HOME
        raise ValueError(
            "Failed to get home directory for %s"
            % (user if user else "current user")
        )
    # --

    return home_dir
# --- end of get_home_dir (...) ---


if os.name == "posix":  # sys.platform.startswith("linux")
    def get_user_config_dir(confdir_name, *, user=None):
        """Returns the path to a config directory for 'confdir_name'."""
        return os.path.join(
            get_home_dir(user=user),
            ".config",
            normalize_relpath(confdir_name)
        )

else:
    def get_user_config_dir(confdir_name, *, user=None):
        raise NotImplementedError()
# --
