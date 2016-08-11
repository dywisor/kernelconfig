# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import logging
import os
import signal
import sys
import traceback


from ..abc import loggable
from ..util import osmisc


__all__ = ["MainScriptBase"]


class MainScriptBase(loggable.AbstractLoggable):
    """A base class for implementing main scripts that can be executed
    calling the run_main() class method.

    Derived classes must implement the actual main() function
    in the run() method.

    @cvar EX_OK:             standard exit code indicating success
    @cvar EX_ERR:            standard exit code if errors occurred
    @cvar EX_USAGE:          exit code for script usage errors
    @cvar EX_KBD_INTERRUPT:  exit code for KeyboardInterrupt

    @cvar CONSOLE_LOG_FMT:   format string for console logging
    """

    EX_OK = getattr(os, "EX_OK", 0)
    EX_ERR = EX_OK ^ 1
    EX_USAGE = getattr(os, "EX_USAGE", 64)
    EX_KBD_INTERRUPT = EX_OK ^ 130

    CONSOLE_LOG_FMT = "%(levelname)-8s [%(name)s] %(message)s"

    SHOW_EXC_ON_KEYBOARD_INTERRUPT = osmisc.envbool_nonempty(
        "KERNELCONFIG_SHOW_EXC_CTRLC", False
    )

    @classmethod
    def handle_sigusr1(cls, signum, frame):
        # i/o from signal handler?
        traceback.print_stack(frame)

    @classmethod
    def run_main(cls, prog=None, argv=None, **kwargs):
        """Runs the script and exits (via sys.exit()).

        @keyword prog:    prog name or path, defaults to None (-> sys.argv[0])
        @keyword argv:    arguments, defaults to None (-> sys.argv[1:])
        @param   kwargs:  additional keyword arguments that will be passed
                          to the class constructor

        @return: does not return
        """
        if not prog:
            prog = sys.argv[0]

        if argv is None:
            argv = sys.argv[1:]

        exit_code = None
        try:
            signal.signal(signal.SIGUSR1, cls.handle_sigusr1)

            with cls(prog, **kwargs) as main_obj:
                exit_code = main_obj.run(argv)

        except KeyboardInterrupt:
            exit_code = cls.EX_KBD_INTERRUPT
            if cls.SHOW_EXC_ON_KEYBOARD_INTERRUPT:
                raise

        # except NonExitingArgumentParserExit:
        #     catch argparse exit
        #

        else:
            if exit_code is True or exit_code is None:
                exit_code = cls.EX_OK
            elif exit_code is False:
                exit_code = cls.EX_ERR

        finally:
            signal.signal(signal.SIGUSR1, signal.SIG_DFL)
        # --

        sys.exit(exit_code)
    # --- end of run_main (...) ---

    def __init__(self, prog):
        self.initial_working_dir = os.getcwd()
        self.stderr = sys.stderr
        self.prog = prog
        super().__init__(logger_name=self.get_prog_name())

    def get_prog_name(self):
        return os.path.basename(self.prog)

    prog_name = property(get_prog_name)

    def print_err(self, msg):
        """Prints a message to stderr."""
        self.stderr.write("%s\n" % msg)

    def cleanup(self):
        """Performs necessary cleanup actions."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.cleanup()

    def zap_log_handlers(self):
        """Removes all handlers from the logger."""
        log_handlers = list(self.logger.handlers)
        for log_handler in log_handlers:
            self.logger.removeHandler(log_handler)
    # ---

    def setup_console_logging(self, log_level, outstream=None):
        """Attaches a stream handler to the logger.
        By default, it writes to stderr.

        @param   log_level:  log level
        @keyword outstream:  output stream. Defaults to None (-> stderr).
        """
        streamhandler = logging.StreamHandler(
            self.stderr if outstream is None else outstream
        )
        streamhandler.setLevel(log_level)

        streamhandler.setFormatter(
            logging.Formatter(fmt=self.CONSOLE_LOG_FMT)
        )

        self.logger.addHandler(streamhandler)
        self.logger.setLevel(log_level)
    # ---

    @abc.abstractmethod
    def run(self, argv):
        """
        This method should implement the actual main script functionality.

        @param argv:  arguments (without argv[0])
        @type  argv:  C{list} of C{str}

        @return:  None, True, False or exit code
        @rtype:   C{None} or C{bool} or C{int}
        """
        raise NotImplementedError()

# --- end of MainScriptBase ---
