# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import os.path

from ...util import fspath


__all__ = ["ConfigurationSourceArgConfig"]


class ConfigurationSourceArgConfig(object):
    """
    Data object that is passed around during the various phases
    of PhasedConfigurationSourceBase.

    Consumers may add new attributes freely.

    @ivar argv:
    @type argv:        undef
    @ivar _outfiles:   an unordered mapping of to-be-created files
    @type _outfiles:   C{dict} :: C{str} => [sub-of] L{Outfile}
    @ivar _outconfig:  an ordered mapping of output config files
                       in constrast to _outfiles,
                       these files may or may not already exist,
                       and should not be touched (e.g. removed)
                       Files may appear in both _outfiles and _outconfig.
    @type _outconfig:  C{OrderedDict} :: C{str} => [sub-of] L{Outfile}

    @ivar _tmpdir:
    @type _tmpdir:     C{None} or C{bool} or C{str}
    """

    # no __slots__ here! -- "consumers may add new attrs freely"

    class Outfile(object):

        def get_key(self):
            return self.path

        def __hash__(self):
            return hash(self.get_key())

        def __init__(self, path):
            super().__init__()
            self.path = os.path.normpath(path) if path else path

        def get_path(self):
            path = self.path
            if not path:
                raise AttributeError("path is not set")
            return path

        def assign_tmpdir(self, tmpdir):
            pass
    # ---

    class TmpOutfile(Outfile):

        def get_key(self):
            return self.name

        def __init__(self, name):
            super().__init__(None)
            self.name = fspath.normalize_relpath(name)

        def assign_tmpdir(self, tmpdir):
            # if not self.path:
            self.path = os.path.join(tmpdir, self.name)
    # ---

    def __init__(self):
        super().__init__()
        self.argv = []
        self._tmpdir = None
        self._outfiles = {}
        self._outconfig = collections.OrderedDict()
    # ---

    def iter_outfiles(self):
        return iter(self._outfiles.values())
    # ---

    def iter_outfile_paths(self):
        for outfile in self.iter_outfiles():
            yield outfile.get_path()
    # ---

    def iter_outconfig(self):
        return iter(self._outconfig.values())
    # ---

    def iter_outconfig_paths(self):
        for outfile in self.iter_outconfig():
            yield outfile.get_path()
    # ---

    def get_outconfig_path(self):
        if len(self._outconfig) == 1:
            return next(iter(self._outconfig.values())).get_path()
        else:
            raise AssertionError(
                'get_outconfig() can only be used '
                'if there is exactly one outconfig file'
            )
    # ---

    def _add_outconfig(self, outfile):
        key = outfile.get_key()
        if key in self._outconfig:
            raise KeyError(key)
        self._outconfig[key] = outfile
        return outfile
    # ---

    def _add_outfile(self, outfile, is_outconfig=True):
        key = outfile.get_key()

        if key in self._outfiles:
            raise KeyError("outfile already exists", key)

        elif (is_outconfig and key in self._outconfig):
            raise KeyError("outconfig already exists", key)

        else:
            self._outfiles[key] = outfile
            if is_outconfig:
                self._outconfig[key] = outfile
            return outfile
    # ---

    def add_outfile(self, path, is_outconfig=True):
        return self._add_outfile(
            self.Outfile(path), is_outconfig=is_outconfig
        )
    # --- end of add_outfile (...) ---

    def add_tmp_outfile(self, name, is_outconfig=True):
        outfile = self._add_outfile(
            self.TmpOutfile(name), is_outconfig=is_outconfig
        )
        self.set_need_tmpdir()
        return outfile
    # --- end of add_tmp_outfile (...) ---

    def add_outconfig(self, path):
        return self._add_outconfig(self.Outfile(path))
    # --- end of add_outconfig (...) ---

    def has_tmpdir(self):
        return self._tmpdir and self._tmpdir is not True
    # --- end of has_tmpdir (...) ---

    def check_need_tmpdir(self):
        return (self._tmpdir is True)
    # --- end of check_need_tmpdir (...) ---

    def set_need_tmpdir(self):
        if not self._tmpdir:
            self._tmpdir = True
    # --- end of set_need_tmpdir (...) ---

    def assign_tmpdir(self, tmpdir):
        if tmpdir is True or not tmpdir:
            # can only change tmpdir from None/True to non-empty path
            raise ValueError(tmpdir)

        elif self._tmpdir is True:
            self._tmpdir = tmpdir
            for outfile in self.iter_outfiles():
                outfile.assign_tmpdir(tmpdir)

        elif self._tmpdir:
            raise AttributeError("tmpdir is already set")
    # --- end of assign_tmpdir (...) ---

    def _get_tmpdir(self):
        if self._tmpdir is True:
            raise AttributeError("referencing tmpdir=True is not allowed")
        else:
            return self._tmpdir
    # ---

    tmpdir = property(_get_tmpdir)

# --- end of ConfigurationSourceArgConfig ---
