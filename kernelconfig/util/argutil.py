# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import argparse
import os
import re

from . import fs
from . import fspath


__all__ = ["ArgTypes", "UsageAction"]


class NonExitingArgumentParserExit(Exception):
    """
    This exception is raised by a NonExitingArgumentParser
    whenever a normal arg parser would exit() straightaway.
    """
    pass


class NonExitingArgumentParser(argparse.ArgumentParser):
    """An argument parser that raises an exception instead of exiting."""

    DEFAULT_EXIT_EXC_TYPE = NonExitingArgumentParserExit

    def __init__(self, *args, exit_exc_type=None, **kwargs):
        self.exit_exc_type = (
            self.DEFAULT_EXIT_EXC_TYPE if exit_exc_type is None
            else exit_exc_type
        )
        super().__init__(*args, **kwargs)

    def exit(self, status=0, message=None):
        if message:
            raise self.exit_exc_type(message)
        else:
            raise self.exit_exc_type()

    def error(self, message):
        raise self.exit_exc_type(message)

# --- end of NonExitingArgumentParser ---


class ArgTypes(object):
    DEFAULT_EXC_TYPE = argparse.ArgumentTypeError

    def __init__(self, exc_type=None):
        super().__init__()
        self.exc_type = (
            self.DEFAULT_EXC_TYPE if exc_type is None else exc_type
        )
        # abspath {"~*"}, relpath {".", "..", "./*", "../*"}
        #  empty str should be checked before using this regexp
        #  absolute paths are checked with os.path.isabs
        self.re_nonspecial_path = re.compile(
            r'^(?:[~]|[.]{{1,2}}(?:$|{sep}))'.format(sep=os.path.sep)
        )

    def arg_nonempty(self, arg):
        if arg:
            return arg
        raise self.exc_type("arg must not be empty")

    def _arg_expanduser(self, arg):
        return fspath.expand_home_dir(arg) if arg else arg

    def arg_realpath(self, arg):
        return os.path.realpath(self._arg_expanduser(self.arg_nonempty(arg)))

    def arg_fspath(self, arg):
        return os.path.abspath(self._arg_expanduser(self.arg_nonempty(arg)))

    def arg_existing_file(self, arg):
        filepath = self.arg_realpath(arg)
        if not fs.is_readable_file(filepath):
            raise self.exc_type("not a file: %s" % arg)

        return filepath
    # --- end of arg_existing_file (...) ---

    def arg_existing_file_special_relpath(self, arg):
        if not arg:
            raise self.exc_type("arg must not be empty")
        elif os.path.isabs(arg) or self.re_nonspecial_path.match(arg):
            return (False, self.arg_existing_file(arg))
        else:
            return (True, arg)
    # --- end of arg_existing_file_special_relpath (...) ---

    def arg_existing_dir(self, arg):
        filepath = self.arg_realpath(arg)
        if os.path.isdir(filepath):
            return filepath
        raise self.exc_type("not a dir: %s" % arg)
    # --- end of arg_existing_dir (...) ---

    def arg_output_file(self, arg):
        return self.arg_realpath(arg)

# --- end of ArgTypes ---


class SelfAttachingAction(argparse.Action):
    """An action that can be added to an argument parser as argument
    by calling the attach_to(<parser>) class method.

    @cvar DEFAULT_SHORTOPT:  shortopt or shortopts to use
                             when attaching to a parser
    @type DEFAULT_SHORTOPT:  C{None} or C{str} or C{list} of C{str}
    @cvar DEFAULT_LONGOPT:   longopt or longopts
    @type DEFAULT_LONGOPT:   C{None} or C{str} or C{list} of C{str}
    @cvar DEFAULT_HELP:      help message
    """

    DEFAULT_SHORTOPT = None
    DEFAULT_LONGOPT = None
    DEFAULT_HELP = None

    @classmethod
    def attach_to(cls, arg_parser, shortopt=None, longopt=None, **kwargs):
        if shortopt is None:
            shortopt = cls.DEFAULT_SHORTOPT

        if longopt is None:
            longopt = cls.DEFAULT_LONGOPT

        args = []
        for opts in (shortopt, longopt):
            if not opts:
                pass
            elif isinstance(opts, str):
                args.append(opts)
            else:
                args.extend(opts)

        if not args:
            raise ValueError("neither longopt nor shortopt")

        if "action" in kwargs:
            raise ValueError("action keyword in kwargs")

        if cls.DEFAULT_HELP:
            kwargs.setdefault("help", cls.DEFAULT_HELP)

        kwargs["action"] = cls
        return arg_parser.add_argument(*args, **kwargs)
    # --- end of attach_to (...) ---

# --- end of SelfAttachingAction ---


class UsageAction(SelfAttachingAction):

    DEFAULT_LONGOPT = "--usage"
    DEFAULT_HELP = "print usage"

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(
            option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs
        )

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_usage()
        parser.exit()

# --- end of UsageAction ---
