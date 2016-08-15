# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections

from . import _outfile
from . import _misc


__all__ = ["ConfigurationSourceArgConfig"]


class ConfigurationSourceArgConfig(object):
    """
    Data object that is passed around during the various phases
    of PhasedConfigurationSourceBase.

    Consumers may add new attributes freely.

    @ivar argv:
    @type argv:        undef

    @ivar _params:     argparse parameters
    @type _params:

    @ivar fmt_vars:    dict containing additional vars for str-formatting
    @type fmt_vars:    C{dict} :: C{str} => object

    @ivar env_vars:    dict of environment vars
    @type env_vars:    C{dict} :: C{str} => C{str}

    @ivar _outfiles:   an unordered mapping of to-be-created files/dirs
    @type _outfiles:   C{dict} :: C{str}
                          => 2-tuple(C{bool}, sub-of L{AbstractOutfile})
    @ivar _outconfig:  an ordered mapping of output config files
                       in constrast to _outfiles,
                       these files may or may not already exist,
                       and should not be touched (e.g. removed)
                       Files may appear in both _outfiles and _outconfig.
    @type _outconfig:  C{OrderedDict} :: C{str} => [sub-of] L{Outfile}

    @ivar _tmpdir:
    @type _tmpdir:     C{None} or C{bool} or L{TmpdirView}
    """

    # no __slots__ here! -- "consumers may add new attrs freely"

    def __init__(self):
        super().__init__()
        self.argv = []
        self.fmt_vars = {}
        self.env_vars = {}
        self._tmpdir = None
        self._params = None
        self._outfiles = {}
        self._outconfig = collections.OrderedDict()
    # ---

    def set_params(self, params_namespace):
        if self._params is not None:
            raise AssertionError("params are already set!")

        if params_namespace is None:
            self._params = False
            return

        param_vars = _misc.get_parameter_format_vars_from_parsed_args(
            params_namespace
        )

        self._params = params_namespace
        self.fmt_vars.update(
            ((k, (v or "")) for k, v in param_vars.items())
        )
        self.env_vars.update(
            ((k.upper(), v) for k, v in param_vars.items())
        )
    # --- end of set_params (...) ---

    def get_params(self):
        return self._params or None

    def _iter_outfiles(self, outfile_type):
        for of_type, outfile in self._outfiles.values():
            if of_type is outfile_type:
                yield outfile
    # ---

    def iter_all_outfiles(self):
        for of_type, outfile in self._outfiles.values():
            yield outfile
    # ---

    def iter_outfiles(self):
        """
        @return:  iterator over all outfile objects
        """
        return self._iter_outfiles(False)
    # ---

    def iter_outfile_paths(self):
        """
        @return:  iterator over all outfile paths
        """
        for outfile in self.iter_outfiles():
            yield outfile.get_path()
    # ---

    def iter_outdirs(self):
        """
        @return:  iterator over all outdir objects
        """
        return self._iter_outfiles(True)
    # ---

    def iter_outdir_paths(self):
        for outfile in self.iter_outdirs():
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

    def register_outconfig(self, outfile):
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

    def register_outconfigs(self, outfiles, **kwargs):
        for outfile in outfiles:
            self.register_outconfig(outfile, **kwargs)
    # ---

    def _register_outfile(self, outfile_type, outfile, is_outconfig):
        key = outfile.get_key()

        if key in self._outfiles:
            raise KeyError("outfile already exists", key)

        elif (is_outconfig and key in self._outconfig):
            raise KeyError("outconfig already exists", key)

        else:
            self._outfiles[key] = (outfile_type, outfile)
            if is_outconfig:
                self._outconfig[key] = outfile
            return outfile
    # ---

    def register_outfile(self, outfile, is_outconfig=True):
        """Registers an outfile, optionally also as outconfig file.

        @raises KeyError:  if file is already registered

        @param   outfile:       outfile object
        @keyword is_outconfig:  whether to also register the outfile object
                                in outconfig. Defaults to True.

        @return:  outfile
        """
        return self._register_outfile(False, outfile, is_outconfig)

    def register_outfiles(self, outfiles, is_outconfig=True):
        for outfile in outfiles:
            self.register_outfile(outfile, is_outconfig=is_outconfig)
    # ---

    def register_outdir(self, outfile):
        return self._register_outfile(True, outfile, False)
    # ---

    def register_outdirs(self, outfiles):
        for outfile in outfiles:
            self.register_outdir(outfile)
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
        return self.register_outfile(
            _outfile.Outfile(path), is_outconfig=is_outconfig
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
        outfile = self.register_outfile(
            _outfile.TmpOutfile(name), is_outconfig=is_outconfig
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
        return self.register_outconfig(_outfile.Outfile(path))
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

        @param tmpdir:  tmpdir view object (or tmpdir)
        @type  tmpdir:  L{TmpdirView} | L{Tmpdir}

        @return:  None (implicit)
        """
        if tmpdir is True or not tmpdir:
            # can only change tmpdir from None/True to non-empty path
            raise ValueError(tmpdir)

        elif self._tmpdir is True:
            self._tmpdir = tmpdir
            for outfile in self.iter_all_outfiles():
                outfile.assign_tmpdir(tmpdir)

        elif self._tmpdir:
            raise AttributeError("tmpdir is already set")
    # --- end of assign_tmpdir (...) ---

    def get_tmpdir(self):
        """
        @raises AttributeError:  if tmpdir requested but not assigned

        @return:  None or tmpdir object
        @rtype:   C{None} or [sub-of] L{TmpdirView}
        """
        if self._tmpdir is True:
            raise AttributeError("referencing tmpdir=True is not allowed")
        else:
            return self._tmpdir
    # ---

    tmpdir = property(get_tmpdir)

    def get_tmpdir_path(self):
        """
        @raises AttributeError:  if tmpdir requested but not assigned,
                                 or if tmpdir not requested

        @return:  path to tmpdir
        @rtype:   C{str}
        """
        self.get_tmpdir().get_path()  # pylint: disable=E1101
    # ---

    tmpdir_path = property(get_tmpdir_path)

# --- end of ConfigurationSourceArgConfig ---
