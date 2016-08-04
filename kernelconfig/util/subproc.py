# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import fnmatch
import re
import shlex
import subprocess
import time

from ..abc import loggable
from . import tmpdir as _tmpdir


__all__ = [
    "SubProcException",
    "SubProcAlreadyStarted",
    "SubProcNotStarted",
    "SubProc",
]


class SubProcException(Exception):
    pass


class SubProcAlreadyStarted(SubProcException):
    pass


class SubProcNotStarted(SubProcException):
    pass


def catch_process_lookup_err(func):
    try:
        func()
    except ProcessLookupError:
        return True
    else:
        return False
# ---


def merge_env_dicts_add_item(
    base_env, key, value, *,
    _match_pat_regexp=re.compile(r'[\*\?\[\]]'), _fnmatch=fnmatch.fnmatch
):
    if not key:
        raise ValueError(key)

    elif _match_pat_regexp.search(key):
        # key is a pattern
        keylist = [k for k in base_env if _fnmatch(k, key)]
        if value is None:
            for matched_key in keylist:
                base_env.pop(matched_key, None)
        else:
            str_val = str(value)
            for matched_key in keylist:
                base_env[matched_key] = str_val

    elif value is None:
        base_env.pop(key, None)

    else:
        base_env[key] = str(value)
# ---


def _merge_env_dicts_inplace_v(base_env, env_dicts):
    """
    Modifies an environment dict 'base_env'
    with entries from 'env_dicts',
    which is a list of environment dicts that may contain patterns as keys
    and also None as "delete-key" value.

    This operation modifies the base_env dict.

    @param base_env:    env vars dict
    @type  base_env:    C{str} => C{str}
    @param env_dicts:   env vars modification dicts
    @type  env_dicts:   C{list} of C{dict} :: C{str} => C{str}|C{None}

    @return: base_env
    """
    # filter out anything false, e.g. None
    for env_dict in filter(None, env_dicts):
        for key, value in env_dict.items():
            merge_env_dicts_add_item(base_env, key, value)
    # --
    return base_env
# ---


def merge_env_dicts_inplace(base_env, *env_dicts):
    return _merge_env_dicts_inplace_v(base_env, env_dicts)
# ---


def merge_env_dicts(base_env, *env_dicts):
    return _merge_env_dicts_inplace_v(base_env.copy(), env_dicts)
# ---


class SubProc(loggable.AbstractLoggable):
    """
    A class for running processes in a controlled environment:

    * redirect to stdin to /dev/null (by default)
    * use a private tmpdir, create it automatically (optionally)
    * set working directory to the private tmpdir (default if tmpdir enabled)

    >>> with SubProc(cmdv, tmpdir=True) as p:
    >>>     if p.join(timeout=10):
    >>>         os.listdir(p.tmpdir)
    >>>     else:
    >>>         # handle non-zero exit code

    When not used in "with" context,
    the object can be modified after instantiation.

    @ivar _tmpdir:
    @type _tmpdir:

    @ivar cmdv:
    @type cmdv:
    @ivar env:
    @type env:
    @ivar tmpdir:
    @type tmpdir:
    @ivar popen_kwargs:
    @type popen_kwargs:

    @ivar proc:
    @type proc:
    @ivar stdout:
    @type stdout:
    @ivar stderr:
    @type stderr:
    """

    MATCH_PATTERN_REGEXP = re.compile(r'[\*\?\[\]]')

    @classmethod
    def split_command_str(cls, command_str):
        return shlex.split(command_str)
    # ---

    def __init__(
        self, command, *,
        env=None, extra_env=None, cwd=True, stdin=subprocess.DEVNULL,
        quiet=False, split_command_str=True, tmpdir=None, logger=None, **kwargs
    ):
        """
        @param   command:            the command
        @type    command:            C{list} of C{str} or C{str}

        @keyword env:                environment variables
                                     If None, os.environ will be used.
        @type    env:                C{dict}

        @keyword extra_env:          additional environment variables
                                     These will be merged with env.
                                     Unlike env, keys can be patterns
                                     ("*", "?", "[chars]"),
                                     and C{None} values can be used
                                     for deleting environment vars.
                                     This arg will be copied (into a dict).
        @type    extra_env:          C{None} or C{dict} or iterable
                                     of 2-tuples(C{str}, C{str}|C{None})

        @keyword cwd:                change working directory to _
                                     May be True, in which case the temporary
                                     directory is used.
        @type    cwd:                C{None} or C{str} or C{bool}

        @keyword stdin:              stdin, defaults to subprocess.DEVNULL
        @type    stdin:

        @keyword quiet:              whether to default unset stdio to devnull
                                     Defaults to False.
        @type    quiet:              C{bool}

        @keyword split_command_str:  whether to split command with
                                     split_command_str() if it is a string
        @type    split_command_str:  C{bool}

        @keyword tmpdir:             temporary directory
                                     This can be
                                     * None (no tmpdir),
                                     * a str (path to tmp dir)
                                     * True (create and cleanup own tmp dir)
                                     * a Tmpdir instance
                                       (create separate subdirectories
                                       for $TMPDIR and $T, no cleanup done)
        @type    tmpdir:             C{None} or C{str} or L{Tmpdir} or C{bool}

        @param   kwargs:             additional keyword arguments
                                     for subprocess.Popen
        @type    kwargs:             C{dict} :: C{str} => _
        """
        super().__init__(logger=logger)
        # if it is necessary to create a new tmpdir, this attr will hold it
        self._tmpdir = None

        self.cmdv = None
        self.env = None
        self.tmpdir = None
        self.popen_kwargs = None

        self.proc = None
        self.stdout = None
        self.stderr = None

        self._setup(
            command,
            env=env,
            extra_env=extra_env,
            cwd=cwd,
            stdin=stdin,
            quiet=quiet,
            popen_kwargs=kwargs,
            tmpdir=tmpdir,
            split_command_str=split_command_str
        )
    # ---

    @property
    def returncode(self):
        proc = self.proc
        return proc.returncode if proc is not None else None

    def zap(self):
        self.proc = None
        self.stdout = None
        self.stderr = None
    # --- end of zap (...) ---

    def _get_cwd(self):
        return self.popen_kwargs.get("cwd")

    def _set_cwd(self, value):
        if value is True:
            cwd_val = self.tmpdir or None  # redundant or
        else:
            cwd_val = value

        self.popen_kwargs["cwd"] = cwd_val

    cwd = property(_get_cwd, _set_cwd)

    def _set_cmdv(self, command, split_command_str):
        if command is None:
            self.cmdv = None
        elif split_command_str and isinstance(command, str):
            self.cmdv = self.split_command_str(command)
        else:
            self.cmdv = command
    # ---

    def _setup(
        self, command, *,
        env, extra_env, cwd, stdin, quiet, popen_kwargs, tmpdir,
        split_command_str
    ):
        self._set_cmdv(command, split_command_str)

        kwargs = popen_kwargs.copy()
        kwargs["stdin"] = stdin
        for key in ["stdin", "stdout", "stderr"]:
            try:
                value = kwargs[key]
            except KeyError:
                # unreachable for "stdin"
                if quiet:
                    kwargs[key] = subprocess.DEVNULL
            else:
                if value is False:
                    kwargs[key] = subprocess.DEVNULL
        # --

        # COULDFIX: avoid env copy,
        #            but non-empty popen_tmpdir always requires a copy
        # FIXME:    extra_env copy is not necessary,
        #            dict.items(), iter(tuple|list), ...
        env = merge_env_dicts(
            (env if env is not None else os.environ),  # empty env: ok!
            (dict(extra_env) if extra_env is not None else extra_env)
        )

        self.popen_kwargs = kwargs
        self.env = env

        self._setup_tmpdir(tmpdir, env)
        self._set_cwd(cwd)  # must not be called before setting popen_kwargs

        # cmdv already set
    # --- end of _setup (...) ---

    def _setup_tmpdir(self, tmpdir_arg, env):
        """Creates the temporary directory/directories
        and sets relevant environment variables in 'env'.

        If the tmpdir passed to __init__() is a string,
        then $TMPDIR will be set to that path.

        If it is a Tmpdir object,
        two directories will be created,
        a shared "tmp" directory (which may already exist),
        and a private directory (by means of mkdtemp()).
        $TMPDIR will point to the shared directory,
        and $T will point to the private directory.

        If it is True, then a new Tmpdir object will be created,
        same behavior as described above.

        Otherwise, no temporary directory will be created,
        and the environment vars will not be modified.
        (Possible future extension: set $TMPDIR = "/tmp" if unset.)

        @raises ValueError:  if string-tmpdir is not an absolute path

        @param tmpdir_arg:  tmpdir passed to __init__()
        @type  tmpdir_arg:  C{None} or C{str} or L{Tmpdir} or C{bool}
        @param env:         dict of environment variables
        @type  env:         C{dict} :: C{str} => C{str}
        """
        def setup_tmpdir_obj(tmpdir):
            nonlocal env

            priv_tmpdir_path = tmpdir.get_new_subdir_path()
            shared_tmpdir_path = tmpdir.dodir("tmp")

            env["T"] = priv_tmpdir_path
            env["TMPDIR"] = shared_tmpdir_path
            self.tmpdir = priv_tmpdir_path
        # ---

        if not tmpdir_arg:
            self.tmpdir = env.get("TMPDIR") or None

        elif tmpdir_arg is True:
            self._tmpdir = _tmpdir.Tmpdir()
            setup_tmpdir_obj(self._tmpdir)

        elif isinstance(tmpdir_arg, _tmpdir.TmpdirView):
            setup_tmpdir_obj(tmpdir_arg)

        else:
            tmpdir_path = str(tmpdir_arg)
            if not os.path.isabs(tmpdir_path):
                raise ValueError(
                    "invalid tmpdir path {!r}".format(tmpdir_arg)
                )

            env["TMPDIR"] = tmpdir_path
            self.tmpdir = tmpdir_path
    # --- end of _setup_tmpdir (...) ---

    def setenv(self, varname, value):
        merge_env_dicts_add_item(self.env, varname, value)

    def delenv(self, *varnames):
        merge_env_dicts_inplace(self.env, {vname: None for vname in varnames})

    def start(self):
        """Starts the subprocess.

        @raises SubProcAlreadyStarted: if already started
        """
        if self.proc is None:
            # FIXME: remove/adjust logging
            self.logger.debug("Running command %r", self.cmdv)
            self.proc = subprocess.Popen(
                self.cmdv, env=self.env, **self.popen_kwargs
            )
        else:
            raise SubProcAlreadyStarted()
    # ---

    def stop(self, kill_timeout_centisecs=10):
        """
        Tries to terminate the subprocess and proceeds with killing it
        if the process is still alive after the timeout expired.

        @param kill_timeout_centisecs:  time in centiseconds after which
                                        the process is killed
                                        (any "false" value is interpreted
                                        as "no timeout" == 0)
        @type  kill_timeout_centisecs:  C{int} or C{None}

        @return:  None (implicit)
        """
        proc = self.proc

        if proc is None or proc.poll() is not None:
            return

        if catch_process_lookup_err(proc.terminate):
            return

        try:
            if proc.poll() is not None:
                return

            for t in range(kill_timeout_centisecs or 0):
                time.sleep(0.1)

                if proc.poll() is not None:
                    return
            # -- end for
        except:
            catch_process_lookup_err(proc.kill)
            proc.poll()
            raise
        else:
            catch_process_lookup_err(proc.kill)
            proc.poll()
    # ---

    def stop_now(self):
        """Same as stop(0)."""
        return self.stop(kill_timeout_centisecs=0)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.stop()

    def join(self, *, timeout=None, return_success=True, **kwargs):
        """Waits for the process to exit and returns its exit code,
        or a boolean value indicating success or failure.

        @raises SubProcNotStarted: if not process has been started

        @raises subprocess.TimeoutExpired:  process still alive
                                            after not-None timeout seconds

        @keyword timeout:         wait up to timeout seconds
                                  Defaults to None (infinite).
        @type    timeout:         C{None} or C{int}
        @keyword return_success:  whether return a bool indicating
                                  success/failure (True)
                                  or the exit code (False)
                                  Defaults to True.
        @type    return_success:  C{bool}

        @return:  exit code or status bool
        @rtype:   C{int} or C{bool}
        """
        proc = self.proc

        if proc is None:
            raise SubProcNotStarted()

        outv = proc.communicate(timeout=timeout, **kwargs)
        self.stdout, self.stderr = outv

        if return_success:
            return proc.returncode == os.EX_OK
        else:
            return proc.returncode
    # --- end of join (...) ---

# ---
