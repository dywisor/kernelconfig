# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections
import os

from ..abc import loggable
from . import parser


__all__ = ["KernelConfigLangInterpreter"]


class AbstractKernelConfigLangInterpreter(loggable.AbstractLoggable):
    """Base class for kernelconfig's interpreter.

    @ivar _file_input_queue:  file input queue
    @type _file_input_queue:  C{collections.deque}

    @ivar _parser:            parser
    @type _parser:            L{KernelConfigLangParser}
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._file_input_queue = collections.deque()
        self._parser = parser.KernelConfigLangParser()
    # --- end of __init__ (...) ---

    def get_parser(self):
        """
        Returns the configuration language parser,
        performs initialization if necessary.

        @return:  initialized parser
        @rtype:   L{KernelConfigLangParser}
        """
        p = self._parser
        p.build_if_needed()
        return p
    # --- end of get_parser (...) ---

    def _clear_file_input_queue(self):
        """Empties the file input queue.

        Note: "private"

        @return:  None (implicit)
        """
        self._file_input_queue.clear()
    # --- end of _clear_file_input_queue (...) ---

    def assert_empty_file_input_queue(self):
        """
        Helper method that makes sure
        that the file input queue is currently empty.

        @raises AssertionError:  if the file input queue is not empty

        @return:  None (implicit)
        """
        if self._file_input_queue:
            raise AssertionError("unclean interpreter state")
    # --- end of assert_empty_file_input_queue (...) ---

    def add_input_file(self, infile):
        """Adds a file to the end of the file input queue.

        Note: the file should be "normalized" first by looking it up
              with either lookup_include_file() or lookup_load_file(),
              depending on whether it is an "include" command-type
              or process_file()-type input file.


        @param infile:  input file
        @type  infile:  C{str}

        @return:  None (implicit)
        """
        self._file_input_queue.append(infile)
    # --- end of add_input_file (...) ---

    def get_realpath(self, filepath, *, _osp_realpath=os.path.realpath):
        """Returns the real path of a filepath.

        By default, this method just calls os.path.realpath().

        @param filepath:  filepath
        @type  filepath:  C{str}

        @return: real filepath
        @rtype:  C{str}
        """
        return _osp_realpath(filepath)
    # --- end of get_realpath (...) ---

    @abc.abstractmethod
    def lookup_include_file(self, include_file):
        """Locates a file for the "include" command.

        Should return None (or an empty str) if no file found.

        @param include_file:  "key", e.g. file name
        @type  include_file:  C{str}

        @return:  filepath or C{None}
        @rtype:   C{str} or C{None}
        """
        raise NotImplementedError()
    # --- end of lookup_include_file (...) ---

    @abc.abstractmethod
    def lookup_load_file(self, load_file):
        """Locates a file for the process_files() methods.

        Should return None (or an empty str) if no file found.


        @param include_file:  "key", e.g. file path
        @type  include_file:  C{str}

        @return:  filepath or C{None}
        @rtype:   C{str} or C{None}
        """
        raise NotImplementedError()
    # --- end of lookup_load_file (...) ---

    @abc.abstractmethod
    def process_command(self, cmdv, conditional):
        """Interprets a single command.

        @param cmdv:         the command, a [opcode, ...] list
        @type  cmdv:         C{list}

        @param conditional:  conditional part or C{None}
        @type  conditional:  2-tuple(C{bool}, C{list}) or C{None}

        @return:  True or None if successful, False if not
        @rtype:   C{bool} or C{None}
        """
        raise NotImplementedError()
    # --- end of process_command (...) ---

    def process_structured_command(self, structured_command):
        """Splits a structured command into its command and conditional parts
        and calls process_command().

        @param structured_command:  command [opcode, ...]
                                    or condition [cond_type, cond, <command>]

        @return:  True or None if successful, False if not
        @rtype:   C{bool} or C{None}
        """
        _KernelConfigOp = parser.KernelConfigOp

        if structured_command[0] is _KernelConfigOp.cond_if:
            conditional = (True, structured_command[1])
            cmdv = structured_command[2]

        elif structured_command[1] is _KernelConfigOp.cond_unless:
            conditional = (False, structured_command[1])
            cmdv = structured_command[2]

        else:
            conditional = None
            cmdv = structured_command

        return self.process_command(cmdv, conditional)
    # --- end of process_structured_command (...) ---

    def _process_one_cmdlist(self, cmdlist):
        """Processes structured commands from a command list.

        Immediately returns False on the first unsuccessful command.

        @param cmdlist:  list of structured commands

        @return:  True or None if successful, False if not
        @rtype:   C{bool} or C{None}
        """
        for cmdv in cmdlist:
            ret = self.process_structured_command(cmdv)
            if ret is not None and not ret:
                return ret
        # --

        return True
    # --- end of _process_one_cmdlist (...) ---

    def _process_file_input_queue(self):
        """Processes commands from the file input queue until it is empty.

        Immediately returns False on the first unsuccessful command.

        @return:  True if successful, False if not
        @rtype:   C{bool}
        """
        while self._file_input_queue:
            # self._file_input_queue.popleft() a.s.o.
            cmdlist = self._parse_files(self._file_input_queue)
            self._clear_file_input_queue()
            ret = self._process_one_cmdlist(cmdlist)
            if not ret:
                return ret
        # --

        return True
    # --- end of _process_file_input_queue (...) ---

    def process_cmdlist(self, cmdlist):
        """Processes structured commands from a command list,
        and processes further files if commands instruct to do so.

        Immediately returns False on the first unsuccessful command.

        @param cmdlist:  list of structured commands

        @return:  True if successful, False if not
        @rtype:   C{bool} or C{None}
        """
        self.assert_empty_file_input_queue()
        ret = self._process_one_cmdlist(cmdlist)
        if not ret:
            return ret
        return self._process_file_input_queue()
    # --- end of process_cmdlist (...) ---

    def process_files(self, infiles):
        """Processes commands read from the given files.

        Immediately returns False on the first unsuccessful command.

        @param infiles:  iterable of input files
        @type  infiles:  iterable of C{str}

        @return:  True if successful, False if not
        @rtype:   C{bool}
        """
        self.assert_empty_file_input_queue()
        for infile in infiles:
            filepath = self.lookup_load_file(infile)
            if not filepath:
                self.logger.error("file does not exist: %s", infile)
                raise FileNotFoundError(infile)
            # --

            self.add_input_file(filepath)
        # -- end for
        self._process_file_input_queue()
    # --- end of process_files (...) ---

    def process_file(self, infile):
        """Process commands read from the given file.

        @param infile:  input file
        @type  infile:  C{str}

        @return:  True if successful, False if not
        @rtype:   C{bool}
        """
        return self.process_files([infile])
    # --- end of process_file (...) ---

    def process_str(self, text):
        """Processes commands read from the given string.

        @param text:  input string
        @type  text:  C{str}

        @return:  True if successful, False if not
        @rtype:   C{bool}
        """
        cmdlist = self._parse_str(text)
        return self.process_cmdlist(cmdlist)
    # --- end of process_str (...) ---

    def _parse_str(self, text):
        """Parses a string and returns a command list.

        @param text:  input string
        @type  text:  C{str}

        @return:  command list
        @rtype:   C{list}
        """
        cmdlist = self.get_parser().parse(text)
        if cmdlist is None:
            raise NotImplementedError("error while loading str", text)

        return cmdlist
    # --- end of _parse_str (...) ---

    def _parse_files(self, infiles):
        """Parses several files and returns a combined command list.

        @param infiles:  iterable of input files
        @type  infiles:  iterable of C{str}

        @return:  command list
        @rtype:   C{list}
        """
        combined_cmdlist = []
        p = self.get_parser()

        for infile in infiles:
            cmdlist = p.parse_file(infile)
            if cmdlist is None:
                raise NotImplementedError("error while loading file", infile)

            combined_cmdlist.extend(cmdlist)
        # --

        return combined_cmdlist
    # --- end of _parse_files (...) ---

# --- end of AbstractKernelConfigLangInterpreter ---


class KernelConfigLangInterpreter(AbstractKernelConfigLangInterpreter):

    def __init__(self, config_choices, **kwargs):
        super().__init__(**kwargs)
        self.config_choices = None
        self._choice_op_dispatchers = None
        self._choice_str_op_dispatchers = None
        self.bind_config_choices(config_choices)

    def bind_config_choices(self, config_choices):
        _KernelConfigOp = parser.KernelConfigOp

        self.config_choices = config_choices

        if config_choices is None:
            self._choice_op_dispatchers = {}
            self._choice_str_op_dispatchers = {}

        else:
            self._choice_op_dispatchers = {
                _KernelConfigOp.op_disable: config_choices.option_disable,
                _KernelConfigOp.op_module: config_choices.option_module,
                _KernelConfigOp.op_builtin: config_choices.option_builtin,
                _KernelConfigOp.op_builtin_or_module: (
                    config_choices.option_builtin_or_module
                )
            }

            self._choice_str_op_dispatchers = {
                _KernelConfigOp.op_set_to: config_choices.option_set_to,
                _KernelConfigOp.op_append: config_choices.option_append,
                _KernelConfigOp.op_add: config_choices.option_add
            }
        # ---
    # ---

    def lookup_load_file(self, load_file, *, _osp_realpath=os.path.realpath):
        return _osp_realpath(load_file)

    lookup_include_file = lookup_load_file

    def process_command(self, cmdv, conditional):
        _KernelConfigOp = parser.KernelConfigOp

        if conditional is not None:
            self.logger.error(
                "DROPPED condition, assuming true: %r", conditional
            )
        # --

        cmd_arg = cmdv[0]

        if cmd_arg is _KernelConfigOp.op_include:
            include_file = self.locate_include_file(cmdv[1])
            if not include_file:
                self.logger.error(
                    "include file %s does not exist", cmdv[1]
                )
                return False
            # --

            self.add_input_file(include_file)
            return True

        elif cmd_arg in self._choice_op_dispatchers:
            # dispatcher X options
            dispatcher = self._choice_op_dispatchers[cmd_arg]

            for option in cmdv[1]:
                if not dispatcher(option):
                    return False

            return True

        elif cmd_arg in self._choice_str_op_dispatchers:
            # dispatcher X option X value
            dispatcher = self._choice_str_op_dispatchers[cmd_arg]
            return dispatcher(cmdv[1], cmdv[2])

        else:
            raise NotImplementedError("unknown cmd_arg", cmd_arg)
    # --- end of process_command (...) ---

# --- end of KernelConfigLangInterpreter ---


if __name__ == "__main__":
    def main():
        import sys

        ipret = KernelConfigLangInterpreter(None)
        for arg in sys.argv[1:]:
            ipret.process_file(arg)
    # ---

    main()
