# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import os.path

from ...util import fspath


__all__ = ["ConfigurationSourceArgConfig"]


class Outfile(object):
    """An output file whose path is known at initialization time.

    @param path:  path to the file (None if unknown, which should only
                  be used by subclasses)
    @type  path:  C{str} or C{None}
    """

    def get_key(self):
        """Returns a unique identifier for the outfile.

        @return: unique identifier
        @rtype:  C{str}
        """
        return self.path

    def __hash__(self):
        return hash(self.get_key())

    def __init__(self, path):
        super().__init__()
        self.path = os.path.normpath(path) if path else path

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

    def assign_tmpdir(self, tmpdir):
        """
        Assigns the outfile to a temporary directory,
        modifying the outfile's path.

        For this class, this is a no-op, because the path does not depend
        on a tmpdir. Derived classes may vary.
        """
        pass
# --- end of Outfile ---


class TmpOutfile(Outfile):
    """
    An output file whose path is unknown until a temporary directory
    has been assigned to the config source arg config object.

    @ivar name:  name of the file (path relative to tmpdir)
    @type name:  C{str}
    """

    def get_key(self):
        return self.name

    def __init__(self, name):
        super().__init__(None)
        self.name = fspath.normalize_relpath(name)

    def assign_tmpdir(self, tmpdir):
        # if not self.path:
        self.path = os.path.join(tmpdir, self.name)
# --- end of TmpOutfile ---


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

    def __init__(self):
        super().__init__()
        self.argv = []
        self._tmpdir = None
        self._outfiles = {}
        self._outconfig = collections.OrderedDict()
    # ---

    def iter_outfiles(self):
        """
        @return:  iterator over all outfile objects
        """
        return iter(self._outfiles.values())
    # ---

    def iter_outfile_paths(self):
        """
        @return:  iterator over all outfile paths
        """
        for outfile in self.iter_outfiles():
            yield outfile.get_path()
    # ---

    def iter_outconfig(self):
        """
        @return:  iterator over all outconfig objects
        """
        return iter(self._outconfig.values())
    # ---

    def iter_outconfig_paths(self):
        """
        @return:  iterator over all outconfig paths
        """
        for outfile in self.iter_outconfig():
            yield outfile.get_path()
    # ---

    def get_outconfig_path(self):
        """
        @raises AssertionError:  if there is not exactly one outconfig file

        @return:  path to outconfig file
        @rtype:   C{str}
        """
        if len(self._outconfig) == 1:
            return next(iter(self._outconfig.values())).get_path()
        else:
            raise AssertionError(
                'get_outconfig() can only be used '
                'if there is exactly one outconfig file'
            )
    # ---

    def _add_outconfig(self, outfile):
        """Registers an outconfig file (w/o registering it in _outfiles).

        @raises KeyError:  if file is already registered

        @param outfile:  outfile object

        @return:  outfile
        """
        key = outfile.get_key()
        if key in self._outconfig:
            raise KeyError(key)
        self._outconfig[key] = outfile
        return outfile
    # ---

    def _add_outfile(self, outfile, is_outconfig=True):
        """Registers an outfile, optionally also as outconfig file.

        @raises KeyError:  if file is already registered

        @param   outfile:       outfile object
        @keyword is_outconfig:  whether to also register the outfile object
                                in outconfig. Defaults to True.

        @return:  outfile
        """
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
        """Adds an output file.

        Output files may or may not be .config files.
        They are expected to be created by the configuration source,
        and are thus subject to removal/backup-moving (prepare_output_file()).

        @param path:            path to outfile
        @keyword is_outconfig:  whether outfile is an output config file
                                Defaults to True.

        @return:  outfile object
        """
        return self._add_outfile(
            Outfile(path), is_outconfig=is_outconfig
        )
    # --- end of add_outfile (...) ---

    def add_tmp_outfile(self, name, is_outconfig=True):
        """Adds a temporary output file.

        The file's path is not known until a temporary directory
        has been assigned.

        @param name:            name of the outfile
        @keyword is_outconfig:  whether outfile is an output config file
                                Defaults to True.

        @return:  outfile object
        """
        outfile = self._add_outfile(
            TmpOutfile(name), is_outconfig=is_outconfig
        )

        if self.has_tmpdir():
            outfile.assign_tmpdir(self._tmpdir)
        else:
            self.set_need_tmpdir()

        return outfile
    # --- end of add_tmp_outfile (...) ---

    def add_outconfig(self, path):
        """Adds an output config file.

        Output config files should be .config files.
        They may already exist,
        and should not be removed/backup-moved unless they have also been
        added as "outfile", in which case add_outfile(path, is_outconfig=True)
        should be used instead.

        @param name:  path to the outconfig file

        @return:  outfile object
        """
        return self._add_outconfig(Outfile(path))
    # --- end of add_outconfig (...) ---

    def has_tmpdir(self):
        """
        Returns True if a tmpdir has been assigned, and False otherwise.

        The return value is also False if a tmpdir has been requested,
        but not assigned yet.
        """
        return self._tmpdir and self._tmpdir is not True
    # --- end of has_tmpdir (...) ---

    def check_need_tmpdir(self):
        """
        Returns True if a tmpdir should be assigned, and False otherwise.
        """
        return (self._tmpdir is True)
    # --- end of check_need_tmpdir (...) ---

    def set_need_tmpdir(self):
        """
        Requests that a tmpdir should be assigned later on.

        No-op if a tmpdir has already been assigned (or requested).

        @return:  None (implicit)
        """
        if not self._tmpdir:
            self._tmpdir = True
    # --- end of set_need_tmpdir (...) ---

    def assign_tmpdir(self, tmpdir):
        """
        Assigns a tmpdir, should only be called after check_need_tmpdir():

        >>> if obj.check_need_tmpdir():
        >>>    obj.assign_tmpdir(...)

        Also takes care of settings the path of the temporary outfiles.

        @param tmpdir:  path to tmpdir
        @type  tmpdir:  C{str}

        @return:  None (implicit)
        """
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
        """
        @raises AttributeError:  if tmpdir requested but not assigned

        @return:  None or path to tmpdir
        @rtype:   C{None} or C{str}
        """
        if self._tmpdir is True:
            raise AttributeError("referencing tmpdir=True is not allowed")
        else:
            return self._tmpdir
    # ---

    tmpdir = property(_get_tmpdir)

# --- end of ConfigurationSourceArgConfig ---
