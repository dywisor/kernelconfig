# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import subprocess

from ...abc import loggable
from ...util import subproc
from ...util import objcache
from ...kernel import kversion

from ..abc import exc

from . import _fileget


__all__ = ["PymConfigurationSourceRunEnv"]


class PymConfigurationSourceRunEnv(loggable.AbstractLoggable):
    """
    This is the runtime environment that gets passed
    to configuration source python modules, version 1.

    The python module's run() function
    receives the environment as first arg,
    interfacing with kernelconfig should only occur via this environment.

    The following attributes can be referenced by the python module,
    they should all be treated as readonly except where noted otherwise,
    see the @property in-code doc for details:

    @ivar logger:         logger, can also be accessed via log_*() methods
    @type logger:

    @ivar name:           conf source name
    @ivar exc_types:      exception types (namespace object/module)
    @ivar parameters:     arg parse result (namespace object)
    @ivar environ:        extra-env vars dict
    @ivar format_vars:    str-format vars dict
    @ivar kernelversion:  kernel version object
    @ivar tmpdir:         temporary dir object
    @ivar tmpdir_path:    path to temporary dir

    The following methods can be used for communicating with kernelconfig:

    * log_debug(...)         --  log a debug-level message
    * log_info(...)          --  log an info-level message
    * log_warning(...)       --  log a warning-level message
    * log_error(...)         --  log an error-level message

    * error(msg)             --  signal a "config uncreatable" error
                                 (log an error-level message
                                  and raise an appropriate exception)

    * add_config_file(file)  --  add a .config file that will later be
                                 used as configuration basis
                                 (can be called multiple times
                                 in splitconfig scenarios)

    The pym-environment also offers some helper methods, including:

    * download(url)          --  download url, return bytes
    * download_file(url)     --  download url to temporary file
    * run_command(cmdv)      --  run a command
    * get_tmpfile()          --  create new temporary file


    A few class-wide attributes exist,
    but they are of lesser importance to the loaded py module:

    @cvar VERSION:         version of the environment
                             on incompatible changes,
                             this number should be increased
                             (consider introducing a new (sub)class)
    @type VERSION:         C{int}

    @cvar OBJ_CACHE_SIZE:  the max. size of the shared object cache
    @type OBJ_CACHE_SIZE:  C{int}
    """

    # __slots__ usage here is mostly motivated by having control over
    # which attrs the environment has
    __slots__ = [
        "_exc_types", "_obj_cache",
        "_name", "_senv", "_arg_config"
    ]

    VERSION = 1

    OBJ_CACHE_SIZE = 128

    @property
    def exc_types(self):
        """
        Provides access to conf-source related exception types.

        Example usage:

        >>> raise env.exc_types.ConfigurationSourceFileMissingError("file")

        @return: exceptions module  (or namespace)
        """
        return self._exc_types

    @property
    def name(self):
        """Name of the confguration source."""
        return self._name

    @property
    def parameters(self):
        """
        Parameters from arg parsing.

        Accessing the parameters without having defined an arg parser
        (i.e. no source definition file)
        raises an ConfigurationSourceFeatureError.

        The parameters should not be modified.

        @return:  parsed parameters (namespace object)
        """
        params = self._arg_config.get_params()
        if not params:
            raise exc.ConfigurationSourceFeatureError(
                "this source has no parameters"
            )
        return params
    # ---

    @property
    def environ(self):
        """
        Environment variables which are used in addition to os.environ
        when creating subprocess, e.g. with run_command().

        Entries can be added to or removed from this dict freely.
        The values of existing entries must not be modified,
        removing the entries is fine.

        Keys should be strings, values can be anything.
        A 'None' value causes the environment variable to be removed
        when creating the subprocess.

        @return: dict of environment variables
        @rtype:  C{dict} :: C{str} => C{object}
        """
        return self._arg_config.env_vars

    @property
    def format_vars(self):
        """
        Format variables which may be passed to a string formatter.

        Similar to environ,
        entries can be added or removed freely,
        but existing values should not be modified (removing the entry is ok).

        Keys must be strings, values can be anything, but setting a format
        variable to None may result in printing out "None".

        @return: dict of format variables
        @rtype:  C{dict} :: C{str} => C{object}
        """
        return self._arg_config.fmt_vars

    @property
    def kernelversion(self):
        """
        Version of the sources for which a kernel config is being created.

        The kernel version is an object that provides information about
        specific version parts via attributes:
           * kver.version
           * kver.patchlevel
           * kver.sublevel
           * kver.extraversion
              only if kver.extraversion is not None:
              - kver.extraversion.subsublevel
              - kver.extraversion.rclevel
              - kver.extraversion.dirty
              - kver.extraversion.localversion

        It is also comparable to other kernel version objects,
        which can be constructed with create_kernelversion() and
        create_kernelversion_from_str().

        The kernel version object must not be modified in any way.

        Note that, although currently not implemented,
        this version is not necessarily the actual version of the sources,
        but instead may be overridden via command line args.

        @raises AttributeError:  when not processing a kernel source

        @return:  kernel version object
        @rtype:   L{KernelVersion}
        """
        return self._senv.source_info.kernelversion

    @property
    def tmpdir(self):
        """
        Temporary directory that can be used freely.

        In contrast to tmpdir_path, this returns a tmpdir object,
        which provides helper methods, e.g. tmpdir.get_new_file(),
        which creates an anonymous empty file and returns its path,
        and tmpdir.get_new_subdir_path(),
        which creates an anon new directory and returns its path.

        The tmpdir object's attributes should not be modified directly,
        using its public methods (not underscore "_" prefixed) is fine.

        @return:  tmpdir object
        @rtype:   ]subclass of] L{TmpdirView}
        """
        return self.get_tmpdir()

    @property
    def tmpdir_path(self):
        """
        Path to the temporary directory.
        """
        return self.get_tmpdir_path()

    def __init__(self, name, conf_source_env, arg_config, **kwargs):
        super().__init__(**kwargs)
        self._exc_types = exc
        self._obj_cache = objcache.ObjectCache(maxsize=self.OBJ_CACHE_SIZE)
        self._name = name
        self._senv = conf_source_env
        self._arg_config = arg_config

    def __repr__(self):
        return "{cls.__name__}<{ver}>({name!r})".format(
            cls=self.__class__,
            ver=self.VERSION,
            name=self.name
        )

    def __str__(self):
        return "pym run() environment for {name}, version {ver}".format(
            ver=self.VERSION, name=self.name,
        )

    def log_debug(self, *args, **kwargs):
        """Writes a "debug"-level log message."""
        return self.logger.debug(*args, **kwargs)

    def log_info(self, *args, **kwargs):
        """Writes an "info"-level log message."""
        return self.logger.info(*args, **kwargs)

    def log_warning(self, *args, **kwargs):
        """Writes a "warning"-level log message."""
        return self.logger.warning(*args, **kwargs)

    def log_error(self, *args, **kwargs):
        """Writes an "error"-level log message."""
        return self.logger.error(*args, **kwargs)

    def error(self, message, *, exc_type=exc.ConfigurationSourceExecError):
        """
        Writes an "error"-level log message
        and raises a "cannot get config source" exception.

        @param    message:   (formatted) error message
        @type     message:   C{str}
        @keyword  exc_type:  type of the exception that should be created,
                             defaults to ConfigurationSourceExecError
        @type     exc_type:  type a, a is subclass of BaseException
        """
        self.log_error(message)
        raise exc_type(message)

    def get_tmpdir(self):
        """Returns the tmpdir object, see tmpdir() for details."""
        arg_config = self._arg_config

        arg_config.set_need_tmpdir()

        if not arg_config.has_tmpdir():
            # then create it now
            arg_config.assign_tmpdir(
                self._senv.get_tmpdir().get_new_subdir()
            )

        return arg_config.get_tmpdir()
    # --- end of get_tmpdir (...) ---

    def get_tmpdir_path(self):
        """Returns the tmpdir path, see tmpdir_path() for details."""
        return self.get_tmpdir().get_path()
    # --- end of get_tmpdir_path (...) ---

    def get_tmpfile(self):
        """Creates a new, empty temporary file and returns its path.

        @return:  path to new temporary file
        @rtype:   C{str}
        """
        return self.get_tmpdir().get_new_file()
    # --- end of get_tmpfile (...) ---

    def add_config_file(self, path):
        """Registers the given path as output .config file.

        Relative paths are looked up in the current working directory.

        The file must exist,
        otherwise an ConfigurationSourceFileMissingError is raised.

        Calling this method more than once instructs kernelconfig
        to load *all* files in the order they have been added.

        @return:  None (implicit)
        """
        # not returning the Outfile object here
        filepath = os.path.abspath(path)

        if not os.path.isfile(filepath):
            raise self.exc_types.ConfigurationSourceFileMissingError(path)

        self._arg_config.add_outconfig(filepath)
    # --- end of add_config_file (...) ---

    def download_file(self, url, data=None):
        """
        Downloads a file from the given url
        and stores its content in a temporary file whose path is then returned.

        A ConfigurationSourceFileGetError is raised on errors.

        @param   url:   remote file path, e.g. "http:/...."
        @type    url:   usually C{str}
        @keyword data:  request data, defaults to None

        @return:  path to downloaded file
        @rtype:   C{str}
        """
        outfile = self.get_tmpfile()
        self.logger.info("Downloading %s to file", url)
        _fileget.get_file_write_to_file(
            outfile, url, data=data, logger=self.logger
        )
        return outfile

    def download(self, url, data=None):
        """
        Downloads a file from the given url
        and returns its content as bytes object.

        A ConfigurationSourceFileGetError is raised on errors.

        @param   url:   remote file path, e.g. "http:/...."
        @type    url:   usually C{str}
        @keyword data:  request data, defaults to None

        @return:  received data
        @rtype:   C{bytes}
        """
        self.logger.info("Downloading %s", url)
        # get_file() returns bytearray
        return bytes(_fileget.get_file(url, data=data, logger=self.logger))

    def create_subproc(self, cmdv, stdin=subprocess.DEVNULL, cwd=None):
        """
        Creates a subprocess using the pym-environment's
        logger, env vars and temporary directory.

        The initial working directory of the process defaults to the
        temporary dir, but can be overridden via the cwd keyword.

        The process's stdin defaults to /dev/null,
        and can be overridden via the stdin keyword.

        The command may be str, which is then splitted with shlex.split().

        Note that this method creates the subprocess, but does not start it!
        See run_command() for an easy-to-use solution.

        @param   cmdv:   the command to be run
        @type    cmdv:   C{list} or C{str}

        @keyword stdin:  stdin

        @keyword cwd:    initial working directory of the process

        @return: subprocess object
        @rtype:  L{SubProc}
        """
        tmpdir_path = self.get_tmpdir_path()
        return subproc.SubProc(
            cmdv,
            logger=self.logger,
            tmpdir=tmpdir_path,
            extra_env=self.environ,
            cwd=(os.path.join(tmpdir_path, cwd) if cwd else None),
            stdin=stdin
        )

    def _join_subproc(self, proc, return_success=True):
        """
        Waits for a subprocess to finish and returns its exit code.

        Similar to SubProc.join(),
        but rewrites the exception on process timeout.

        @raises ConfigurationSourceExecError:  on timeout

        @return:  retcode
        @rtype:   C{int} or C{bool}, depending on return_success
        """
        retcode = None
        try:
            retcode = proc.join(return_success=return_success)
        except subprocess.TimeoutExpired:
            raise self.exc_types.ConfigurationSourceExecError(
                "process timed out"
            ) from None
        # --
        return retcode
    # --- end of _join_subproc (...) ---

    def run_command_get_returncode(self, cmdv, return_success=True, **kwargs):
        with self.create_subproc(cmdv, **kwargs) as proc:
            retcode = self._join_subproc(proc, return_success=return_success)
        return retcode
    # --- end of run_command_get_returncode (...) ---

    def run_command(self, cmdv, *, exit_codes_ok=None, **kwargs):
        """Runs a command as subprocess.

        The subprocess must succeed,
        otherwise an ConfigurationSourceExecError is raised.
        By default, only os.EX_OK is considered to indicate success,
        but the exit_codes_ok can be used to pass an iterable
        of acceptable exit codes to override this behavior.
        (In that case, it should include os.EX_OK if desired.)

        See create_subproc() for details.

        @return: None
        """
        if exit_codes_ok is None:
            exit_codes_ok = {os.EX_OK, }

        with self.create_subproc(cmdv, **kwargs) as proc:
            retcode = self._join_subproc(proc, return_success=False)

        if retcode not in exit_codes_ok:
            raise self.exc_types.ConfigurationSourceExecError(
                "command failed", cmdv
            )
    # --- end of run_command (...) ---

    def create_object(self, constructor, *args):
        """
        Object creator that makes use of a cache.

        The returned object should be considered readonly
        since it is shared with other instances/create_object() calls.

        The constructor can be a class or a callable (function/method).
        The passed arguments must be hashable.

        A typical use is caching string to object conversion
        by wrapping the converter function/method.

        The pym-environment also offers a constructor wrapper,
        see cache_constructor below.

        @param constructor:  class/method/function that can create the
                             requested object from *args

        @param args:         constructor arguments
        @type  args:         iterable

        @return:  cached object
        """
        return self._obj_cache.get(constructor, *args)
    # --- end of create_object (...) ---

    def cache_constructor(self, constructor):
        """This wrapper turns a constructor into a cached constructor.

        @param constructor:  class/method/function that can create the
                             requested object from *args

        @return:  cached constructor
        """
        return self._obj_cache.wraps(constructor)
    # --- end of cache_constructor (...) ---

    def create_kernelversion_from_str(self, kver_str):
        """
        Parses a string and creates a kernel version object.

        This method makes use of the object cache,
        returned objects should be considered readonly.

        @param kver_str:  version string
        @type  kver_str:  C{str}

        @return:  cached kernel version object
        @rtype:   L{KernelVersion}
        """
        return self.create_object(
            kversion.KernelVersion.new_from_version_str,
            kver_str
        )
    # --- end of create_kernelversion_from_str (...) ---

    def create_kernelversion(
        self, version, patchlevel, sublevel=0, subsublevels=None, rclevel=None
    ):
        """
        Creates a new kernel version object from the given version parts.

        @param   version:       version (e.g. 3.x.y -> 3)
        @type    version:       C{int} or C{None}
        @param   patchlevel:    patchlevel (e.g. 4.6.y -> 6)
        @type    patchlevel:    C{int} or C{None}
        @keyword sublevel:      sublevel version component (e.g. 4.7.1 -> 1)
                                Defaults to 0.
        @type    sublevel:      C{int} or C{None}
        @keyword subsublevels:  further int version components
                                (e.g. for 2.6.32.x -> subsublevels=(x))
        @type    subsublevels:  C{None} or iterable of C{int}
        @keyword rclevel:       rc version number, defaults to None
        @type    rclevel:       C{None} or C{int}

        @return:  new kernel version object
        @rtype:   L{KernelVersion}
        """
        extraver = kversion.KernelExtraVersion(
            subsublevel=(tuple(subsublevels) if subsublevels else None),
            rclevel=rclevel
        )

        return kversion.KernelVersion(version, patchlevel, sublevel, extraver)
    # --- end of create_kernelversion (...) ---

# --- end of PymConfigurationSourceRunEnv ---
