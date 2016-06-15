# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import argparse
import os
import stat


__all__ = ["ArgTypes", "UsageAction"]


class ArgTypes(object):
    DEFAULT_EXC_TYPE = argparse.ArgumentTypeError

    def __init__(self, exc_type=None):
        super().__init__()
        self.exc_type = (
            self.DEFAULT_EXC_TYPE if exc_type is None else exc_type
        )

    def arg_nonempty(self, arg):
        if arg:
            return arg
        raise self.exc_type("arg must not be empty")

    def arg_realpath(self, arg):
        return os.path.realpath(self.arg_nonempty(arg))

    def arg_fspath(self, arg):
        return os.path.abspath(self.arg_nonempty(arg))

    def arg_existing_file(self, arg):
        fspath = self.arg_realpath(arg)
        try:
            sb = os.stat(fspath)
        except OSError:
            raise self.exc_type("file does not exist: %s" % arg) from None

        if stat.S_ISDIR(sb.st_mode) or stat.S_ISLNK(sb.st_mode):
            # ISLNK is unrealistic, due to realpath()
            raise self.exc_type("not a file: %s" % arg)
        # --

        # S_IFCHR, S_IFBLK, S_IFREG, S_IFIFO, S_IFSOCK -- ok!
        return fspath
    # --- end of arg_existing_file (...) ---

    def arg_existing_dir(self, arg):
        fspath = self.arg_realpath(arg)
        if os.path.isdir(fspath):
            return fspath
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
