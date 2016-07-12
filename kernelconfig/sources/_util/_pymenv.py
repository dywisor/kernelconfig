# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import errno
import os
import re
import subprocess

from ...abc import loggable
from ...util import fs
from ...util import subproc
from ...util import objcache
from ...kernel import kversion

from ..abc import exc

from . import _fileget


__all__ = ["PymConfigurationSourceRunEnv"]


_RunCommandResult = collections.namedtuple(
    "RunCommandResult", "success returncode stdout stderr"
)


class RunCommandResult(_RunCommandResult):

    def __bool__(self):
        return bool(self.success)
# ---


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
    @ivar str_formatter:  string formatter
    @ivar format_vars:    string formatter's vars dict
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

    * run_command(cmdv)      --  run a command
    * get_tmpfile()          --  create new temporary file

    * download(url)          --  download url, return bytes
    * download_file(url)     --  download url to temporary file


    * git_clone_configured_repo()
                             --  clone the repo configured in [config]
                                 and change the working dir to its path

    * git_clone(url)         --  clone a git repo and returns it path,
                                  using a per-confsource cache dir
    * git_checkout_branch(branch)
                             --   switch to git branch

    * run_git(argv)          --  run a git command in $PWD
    * run_git_in(dir, argv)  --  run a git command in <dir>


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
        "_name", "_senv", "_config", "_arg_config", "_str_formatter"
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
    def config(self):
        """
        Configuration from [config] section of the source definition file.
        """
        return self._config

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
    def str_formatter(self):
        """
        The "configuration source" string formatter,
        which is charged with config-source format variables.

        Example:

            >>> env.str_formatter.format("{arch}-{kver.version}")
            x86-4

        For a list of format variables,
        refer to the config source documentation
        or see kernelconfig.sources.sourceenv.SourcesEnv._create_base_vars().

        @return:  string formatter
        @rtype:   L{ConfigurationSourceStrFormatter}
        """
        return self._str_formatter

    @property
    def format_vars(self):
        """
        Format variables which may be passed to a string formatter.

        Similar to environ,
        entries can be added or removed freely,
        but existing values should not be modified (removing the entry is ok).

        Keys must be strings, values can be anything, but setting a format
        variable to None may result in printing out "None".

        Note that unlike environ, this dict is only useful
        for adding new entries, since it does not exhibit all the variables
        used by the string formatter, only those that have been added by
        e.g. argument parsing.

        @return: dict of format variables
        @rtype:  C{dict} :: C{str} => C{object}
        """
        return self._str_formatter.fmt_vars

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
        @rtype:   [subclass of] L{TmpdirView}
        """
        return self.get_tmpdir()

    @property
    def tmpdir_path(self):
        """
        Path to the temporary directory.
        """
        return self.get_tmpdir_path()

    def __init__(
        self, name, conf_source_env, config, arg_config, str_formatter,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._exc_types = exc
        self._obj_cache = objcache.ObjectCache(maxsize=self.OBJ_CACHE_SIZE)
        self._name = name
        self._senv = conf_source_env
        self._config = config
        self._arg_config = arg_config
        self._str_formatter = str_formatter

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

    def str_format(self, fmt_str, *args, **kwargs):
        return self._str_formatter.vformat(fmt_str, args, kwargs)

    def str_vformat(self, fmt_str, args=(), kwargs={}):
        return self._str_formatter.vformat(fmt_str, args, kwargs)

    def get_config(self, key, fallback=None):
        """
        Returns the value of an option in the
        [config] section of the source definition file.
        """
        if not key:
            raise ValueError(key)

        normkey = key.lower()
        try:
            return self._config[normkey]
        except KeyError:
            return fallback
    # --- end of get_config (...) ---

    def get_config_check_value(self, key, fallback=None, fcheck=bool):
        self.exc_types.ConfigurationSourceInvalidError
        value = self.get_config(key, fallback=fallback)
        if fcheck(value):
            return value
        elif not value:
            self.error("{} is not set.".format(key))

        else:
            self.error("{} has bad value {!r}".format(key, value))
    # --- end of get_config_check_value (...) ---

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

        self.log_info("Adding config file %s", path)  # not filepath
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

    def create_subproc(self, cmdv, *, cwd=None, **kwargs):
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

        @keyword stdin:  stdin  (defaults to /dev/null)
        @keyword stdout:
        @keyword stderr:

        @keyword cwd:    initial working directory of the process

        @return: subprocess object
        @rtype:  L{SubProc}
        """
        if any(
            (k in kwargs for k in ("extra_env", "logger", "tmpdir"))
        ):
            raise exc.ConfigurationSourceExecError(
                "duplicate or forbidden keyword arg passed to create_subproc",
                kwargs
            )
        # --

        tmpdir_path = self.get_tmpdir_path()
        return PymConfigurationSourceRunEnvSubProc(
            cmdv,
            logger=self.logger,
            tmpdir=tmpdir_path,
            extra_env=self.environ,
            cwd=(os.path.join(tmpdir_path, cwd) if cwd else None),
            **kwargs
        )
    # --- end of create_subproc (...) ---

    def _run_command(
        self, cmdv, *, nofail, timeout=None, exit_codes_ok=None, **kwargs
    ):
        with self.create_subproc(cmdv, **kwargs) as proc:
            result = proc.join(
                nofail=nofail, exit_codes_ok=exit_codes_ok, timeout=timeout
            )

        return result
    # --- end of _run_command (...) ---

    def run_command_get_result(self, cmdv, *, nofail=False, **kwargs):
        return self._run_command(cmdv, nofail=nofail, **kwargs)
    # --- end of run_command_get_result (...) ---

    def run_command(self, cmdv, **kwargs):
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
        self._run_command(cmdv, nofail=False, **kwargs)
    # --- end of run_command (...) ---

    def run_command_get_returncode(self, cmdv, return_success=True, **kwargs):
        result = self._run_command(cmdv, nofail=True, **kwargs)
        return result.success if return_success else result.returncode
    # --- end of run_command_get_returncode (...) ---

    def run_command_get_stdout(
        self, cmdv, *, nofail=False,
        stdout=subprocess.PIPE, universal_newlines=True, **kwargs
    ):
        return self._run_command(
            cmdv, nofail=False,
            stdout=stdout, universal_newlines=universal_newlines, **kwargs
        ).stdout
    # --- end of run_command_get_stdout (...) ---

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

    def create_kernelversion_from_vtuple(self, vtuple, rclevel=None):
        numparts = len(vtuple)
        if not numparts:
            raise self.exc_types.ConfigurationSourceExecError("empty vtuple")

        return self.create_kernelversion(
            version=vtuple[0],
            patchlevel=(vtuple[1] if numparts > 1 else 0),
            sublevel=(vtuple[2] if numparts > 2 else 0),
            subsublevels=vtuple[3:],
            rclevel=rclevel
        )
    # --- end of create_kernelversion_from_vtuple (...) ---

    def create_kernelversion_from_vtuple_str(
        self, vtuple_str, rclevel_str=None, *, vsep="."
    ):
        return self.create_kernelversion_from_vtuple(
            [int(w, 10) for w in vtuple_str.split(vsep)] if vtuple_str else [],
            int(rclevel_str) if rclevel_str else None
        )
    # --- end of create_kernelversion_from_vtuple_str (...) ---

    def _run_git_in(self, git_dir, argv, *, nofail=False, kwargs={}):
        if not argv or not argv[0]:
            self.error("empty git command")

        cmdv = ["git", "--no-pager"]
        if git_dir:
            cmdv.extend(["-C", str(git_dir)])

        cmdv.extend(argv)

        return self._run_command(cmdv, nofail=nofail, **kwargs)
    # --- end of _run_git_in (...) ---

    def _run_git_in_capture_stdout(
        self, git_dir, argv, *, nofail=False, **kwargs
    ):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["universal_newlines"] = True
        return self._run_git_in(git_dir, argv, nofail=nofail, kwargs=kwargs)
    # ---

    def run_git(self, argv, *, git_dir=None, nofail=False, **kwargs):
        """Runs a 'git' command.

        @param   argv:     arguments
        @keyword git_dir:  git directory. Defaults to None (use cwd)
        @keyword nofail:   whether failure is tolerated (True) or not (False)
                           Defaults to False, causing the conf source
                           to fail on git errors
        @param   kwargs:   additional keyword arguments for subproc.SubProc()

        @return:  command result object
        @rtype:   L{RunCommandResult}
        """
        return self._run_git_in(git_dir, argv, nofail=nofail, kwargs=kwargs)
    # --- end of run_git (...) ---

    def run_git_in(self, git_dir, argv, *, nofail=False, **kwargs):
        """Same as run_git(argv, git_dir=git_dir, **kwargs)."""
        return self._run_git_in(git_dir, argv, nofail=nofail, kwargs=kwargs)
    # --- end of run_git_in (...) ---

    def git_clone(self, repo_url, *, name=None, chdir=False):
        """
        Clones a git repo and makes use of the per-confsource cache.

        @param   repo_url:   url to clone from
        @keyword name:       name of the remote repo.
                             Defaults to None (-> autoset)
        @keyword chdir:      whether to change the working directory
                             to the clone repo (True) or not (False)
                             Defaults to False.

        @return:  path to cloned repository (a temporary directory)
        """
        if not name:
            # use (up to) two components of the url as name
            name = "_".join(
                os.path.splitext(w)[0]
                for w in repo_url.rpartition("://")[-1].split("/")[-2:]
            )
            if not name:
                self.error(
                    "Could not determine name for repo url {!r}".format(
                        repo_url
                    )
                )
        # --

        # get tmpdir path first,
        #  it will be cleaned up on exit/error and there is no point
        #  in continuing if this operation would fail
        clone_dst = self.get_tmpdir().get_new_subdir_path()
        clone_args = []

        use_cache = True
        try:
            git_cache_root = (
                self._senv.install_info.get_cache_dir_path("git/0")
            )
        except StopIteration:
            use_cache = False

        if use_cache:
            fs.dodir(git_cache_root)

            # caching strategy:
            #
            #   one git repo per source that contains all repos
            #
            cache_dir = os.path.join(git_cache_root, self.name)
            cache_dir_need_init = False

            try:
                os.mkdir(cache_dir)
            except OSError as oserr:
                if oserr.errno == errno.EEXIST:
                    # probe
                    cache_dir_need_init = not os.access(
                        os.path.join(cache_dir, "HEAD"), os.F_OK
                    )
                    if cache_dir_need_init:
                        self.logger.warning(
                            "cache dir %s exists and needs to be initialized",
                            cache_dir
                        )
                else:
                    raise
                pass
            else:
                cache_dir_need_init = True
            # --

            # init the git cache if necessary
            if cache_dir_need_init:
                self.logger.debug(
                    "Initializing git cache dir %s", cache_dir
                )
                self.run_git_in(cache_dir, ["init", "--bare"])
            # --

            # add/change remote
            if (
                cache_dir_need_init
                or not self.run_git_in(
                    cache_dir, ["remote", "set-url", name, repo_url],
                    stderr=subprocess.DEVNULL, nofail=True
                ).success
            ):
                self.logger.debug("Adding new remote %s to git cache", name)
                self.run_git_in(cache_dir, ["remote", "add", name, repo_url])
            # --

            # fetch
            self.logger.info("Updating git cache for %s", name)
            self.run_git_in(cache_dir, ["fetch", name])

            # add --reference cache_dir to clone args
            clone_args.append("--reference")
            clone_args.append(cache_dir)

            self.logger.info("Cloning git repo %s (using cache)", repo_url)
        else:
            self.logger.info("Cloning git repo %s", repo_url)
        # --

        # clone
        self.run_git(["clone"] + clone_args + [repo_url, clone_dst])

        if chdir:
            os.chdir(clone_dst)

        return clone_dst
    # --- end of git_clone (...) ---

    def git_checkout_branch(self, branch, git_dir=None):
        """Switches the git branch.

        @param   branch:   branch to switch to
        @keyword git_dir:  path to git repo directory

        @return:  path to git directory
        """
        if not git_dir:
            git_dir = os.getcwd()

        self.logger.debug("Checking out git branch %s", branch)
        self.run_git_in(git_dir, ["checkout", "-q", branch])
        return git_dir
    # --- end of git_checkout_branch (...) ---

    def git_list_remote(
        self, repo_url, *refs,
        opts=["-q", "--refs"], allow_empty=False, nofail=False
    ):
        def parse_git_list_remote(proc_output):
            for line in filter(
                None, (l.strip() for l in proc_output.splitlines())
            ):
                lparts = line.split(None, 1)
                if len(lparts) == 2:
                    yield lparts
                else:
                    self.logger.warning(
                        "Could not parse ls-remote line %r", line
                    )
                    # raise?
        # ---

        argv = ["ls-remote"]
        if opts:
            argv.extend(opts)

        if not allow_empty:
            argv.append("--exit-code")

        argv.append(repo_url)
        argv.extend(refs)

        result = self._run_git_in_capture_stdout(None, argv, nofail=nofail)
        if result.success:
            return list(parse_git_list_remote(result.stdout))
        else:
            return []
    # --- end of git_list_remote (...) ---

    def git_clone_configured_repo(self, *, fallback_repo_url=None, chdir=True):
        """
        Clones the repo configured in the [config] section
        of the source definition file.

        Relevant config fields are currently only "Repo=",
        which sets the repo's remote url.

        @keyword fallback_repo_url:  passed as fallback to
                                     get_config_check_value

        @keyword chdir:  whether to change the working directory to the
                         cloned git repo dir (True) or not (False)
                         Defaults to True (unlike git_clone()).
        @type    chdir:  C{bool}

        @return:  path to cloned git repo
        """
        repo_url = self.get_config_check_value(
            "repo", fallback=fallback_repo_url
        )
        return self.git_clone(repo_url, chdir=chdir)
    # --- end of git_clone_configured_repo (...) ---

    def git_rev_parse_object(
        self, filepath, branch="HEAD", *, git_dir=None, nofail=False
    ):
        """
        Returns the git identifier for a blob-type object,
        which can be used to retrieve the file's content,
        e.g. with git show or git cat-file.

        @param filepath:  path of the file
                          (relative to the git_dir
                          or relative to os.getcwd() if it starts with "./")
        @param branch:    branch/tag/commit containing the requested file

        @return: the file's object identifier
        @rtype:  C{str}
        """
        if not filepath:
            raise ValueError()

        # branch may be empty

        argv = [
            "rev-parse", "--verify", "--quiet",
            "{}:{}".format((branch or ""), filepath)
        ]

        result = self._run_git_in_capture_stdout(git_dir, argv, nofail=nofail)
        if not result.success:
            return None

        object_id = None
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) != 1:
                self.log_warning(
                    "Could not interpret git-rev-parse result line %r",
                    line
                )
            elif object_id is not None:
                self.log_warning("FIXME: got multiple git-rev-parse results")
            else:
                object_id = parts[0]
        # --

        return object_id
    # --- end of git_rev_parse_object (...) ---

    def git_get_text_file_content(
        self, filepath, branch="HEAD", *, git_dir=None, nofail=False
    ):
        object_id = self.git_rev_parse_object(
            filepath, branch=branch, git_dir=git_dir, nofail=nofail
        )
        if object_id is None:
            return None

        argv = ["cat-file", "blob", object_id]

        # the object is known to exist, pass nofail=False
        result = self._run_git_in_capture_stdout(git_dir, argv, nofail=False)
        return result.stdout if result.success else None   # ifexpr redundant
    # --- end of git_get_text_file_content (...) ---

    def get_git_remote_branch_regexp(
        self, branch_name_pattern=None, remote_pattern=None, do_compile=True
    ):
        """
        Returns a regular expression string that can be used for filtering
        the output of "git rev-parse --symbolic-full-name".

        @keyword branch_name_pattern:  regular expression string for
                                       matching the branch's name
                                       Defaults to '\S+'.
                                       Example: '\S+-(?P<ver>\d+(?:[.]\d+))'
        @keyword remote_pattern:       regular expression string for
                                       matching the remote's name
                                       Defaults to '[^/]+'.
                                       Example: 'origin'

        @return:  regular expression string
        @rtype:   C{str}
        """
        regexp_str = (
            (
                r'^refs/remotes/'
                r'(?P<branch>(?P<remote>(?:{rpat}))/(?P<name>(?:{bpat})))$'
            ).format(
                rpat=(remote_pattern or r'[^/]+'),
                bpat=(branch_name_pattern or r'\S+')
            )
        )

        return regexp_str
    # ---

    def git_list_branches(self, regexp=None, *, git_dir=None, nofail=False):
        """Generator.

        Runs "git rev-parse --symbolic-full-name --all" to get list of
        symbolic names, and yields those who match the input regexp.
        When no regexp is given, get_git_remote_branch_regexp() is called
        to create the default expression.
        The result are a 2-tuples (name, dict of regexp match group vars).

        When using the default regexp, the following named groups exist
        in the group vars dict:

        * branch -- branch name, e.g. origin/a/b
        * remote -- remote name, e.g. origin
        * name   -- name,        e.g. a/b
        """
        if regexp is None:
            regexp = re.compile(self.get_git_remote_branch_regexp())
        elif isinstance(regexp, str):
            regexp = re.compile(regexp)

        argv = ["rev-parse", "--symbolic-full-name", "--all"]
        result = self._run_git_in_capture_stdout(git_dir, argv, nofail=nofail)
        if not result.success:
            return

        for line in result.stdout.splitlines():
            match = regexp.match(line)
            if match:
                match_vars = dict(enumerate(match.groups()))
                match_vars.update(match.groupdict())
                yield (line, match_vars)
    # --- end of git_list_branches (...) ---

# --- end of PymConfigurationSourceRunEnv ---


class PymConfigurationSourceRunEnvSubProc(subproc.SubProc):

    def join(self, *, nofail, timeout=None, exit_codes_ok=None, **kwargs):
        """
        Waits for a subprocess to finish and returns its exit code.

        Similar to SubProc.join(),
        but rewrites the exception on process timeout.

        @raises ConfigurationSourceExecError:  on timeout

        @return:  command result object
        @rtype:   L{RunCommandResult}
        """
        if exit_codes_ok is None:
            exit_codes_ok = {os.EX_OK, }

        try:
            returncode = super().join(
                timeout=timeout, return_success=False, **kwargs
            )
        except subprocess.TimeoutExpired:
            raise exc.ConfigurationSourceExecError(
                "process timed out"
            ) from None

        result = RunCommandResult(
            (returncode in exit_codes_ok),
            returncode,
            self.stdout,
            self.stderr
        )

        if not nofail and not result.success:
            raise exc.ConfigurationSourceExecError(
                "command failed", returncode, self.cmdv
            )

        return result
    # --- end of join (...) ---

# --- end of PymConfigurationSourceRunEnvSubProc ---
