# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections
import os

from ..abc import loggable
from . import cond
from . import parser


__all__ = ["KernelConfigLangInterpreter"]


class KernelConfigLangInterpreterError(Exception):
    pass


class KernelConfigLangInterpreterCondOpNotSupported(
    KernelConfigLangInterpreterError
):
    pass


class AbstractKernelConfigLangInterpreter(loggable.AbstractLoggable):
    """Base class for kernelconfig's interpreter.

    @ivar _file_input_queue:  file input queue
    @type _file_input_queue:  C{collections.deque}

    @ivar _parser:            parser
    @type _parser:            L{KernelConfigLangParser}
    """

    DEFAULT_COND_RESULT_BUFFER_SIZE = 1

    def __init__(self, cond_result_buffer_size=True, **kwargs):
        super().__init__(**kwargs)
        self._file_input_queue = collections.deque()
        self._parser = self.create_loggable(
            parser.KernelConfigLangParser, logger_name="Parser"
        )

        if cond_result_buffer_size is True:
            cond_result_buffer_size = self.DEFAULT_COND_RESULT_BUFFER_SIZE

        self._conditional_result_buffer = collections.deque(
            maxlen=cond_result_buffer_size
        )

    # --- end of __init__ (...) ---

    def peek_cond_result(self):
        """Returns the value of the most recent conditional expression.

        @return:  True or False
        @rtype:   C{bool}
        """
        return self._conditional_result_buffer[-1]
    # ---

    def push_cond_result(self, cond_value):
        """Appends a value to the conditional expression result buffer.

        @param cond_value:
        @type  cond_value:  C{bool}

        @return:  cond_value
        """
        self._conditional_result_buffer.append(cond_value)
        return cond_value
    # ---

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

    def soft_reset(self):
        self._conditional_result_buffer.clear()
    # ---

    def reset(self):
        self.soft_reset()
        self._clear_file_input_queue()
    # ---

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
        self.logger.debug("Adding %r to the input file queue", infile)
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

    @abc.abstractmethod
    def lookup_cmp_operand(self, arg):
        """
        @return:  None if arg is not a cmp variable,
                  else 2-tuple (operand, str-to-operand converter)

        @rtype:   C{None} or 2-tuple (C{object}, callable a :: str -> object)
        """
        raise NotImplementedError()

    def evaluate_cmp(self, cmp_func, cmp_args, source=None):
        def create_operand(arg, constructor, reference_arg):
            try:
                oper = constructor(arg)
            except (ValueError, TypeError):
                self.logger.error(
                    "Failed to create comparison operand for %r from %r",
                    reference_arg, arg
                )
                raise KernelConfigLangInterpreterCondOpNotSupported(
                    "Uncomparable operands (constructor error): %r" % arg
                )
            else:
                return oper
        # ---

        assert len(cmp_args) == 2

        loperv = self.lookup_cmp_operand(cmp_args[0])
        roperv = self.lookup_cmp_operand(cmp_args[1])

        if loperv is None:
            if roperv is None:
                self.logger.error(
                    (
                        'Uncomparable operands - '
                        'at least one most be a variable: %r'
                    ),
                    cmp_args
                )
                raise KernelConfigLangInterpreterCondOpNotSupported(
                    "Uncomparable operands (no-var): %r" % cmp_args
                )

            else:
                loper = create_operand(cmp_args[0], roperv[1], roperv[0])
                roper = roperv[0]

        elif roperv is None:
            loper = loperv[0]
            roper = create_operand(cmp_args[1], loperv[1], loperv[0])

        else:
            loper = loperv[0]
            roper = roperv[0]

        try:
            cmp_ret = cmp_func(loper, roper)
        except TypeError:
            self.logger.error(
                "Uncomparable operands - type error: %r",
                (loper, roper)
            )
            raise KernelConfigLangInterpreterCondOpNotSupported(
                "Uncomparable operands (type-err): %r" % cmp_args
            ) from None
        # --

        return (False, cmp_ret)
    # --- end of evaluate_cmp (...) ---

    def evaluate_conditional(self, conditional, context, source=None):
        """Evaluates a conditional expression.

        @param   conditional:  the "conditional"
                               a 2-tuple (cond value (un)negated?, cond expr)
                               where cond_expr is a nested list structure
                               where each list contains 3 elements
                               cond_type, cond_func, cond_args
                               (and the recursion may appear in cond_args).

        @type    conditional:  2-tuple (C{bool}, C{list})

        @param   context:      dict-like structure that provides functions
                               for context-sensitive conditions
        @type    context:      dict-like :: KernelConfigOp -> callable c,
                               c :: cond_func, cond_args -> 2-tuple of C{bool}


        @keyword source:       additional information about the conditional's
                               origin. May be and defaults to None.
        @type    source:       undef or C{None}

        @return:               2-tuple (is dynamic, value)
                               a conditional is dynamic if any condition
                               uses implicit args (e.g. KW_PLACEHOLDER).
        @rtype:                2-tuple (C{bool}, C{bool})
        """
        def eval_subret(cond_exprv):
            sub_retv = []
            sub_retv_dynamic = False
            for subcexpr in cond_exprv:
                sub_dynamic, sub_ret = dfs_inner(subcexpr)
                if sub_dynamic:
                    sub_retv_dynamic = True
                sub_retv.append(sub_ret)
            # --

            return (sub_retv_dynamic, sub_retv)
        # ---

        def dfs_inner(cexpr, *, _KernelConfigOp=parser.KernelConfigOp):
            nonlocal context
            nonlocal source

            cond_type, cond_func, cond_args = cexpr

            if cond_type in context:
                rval = context[cond_type](cond_func, cond_args)
                if rval is not None:
                    return rval
            # --

            if cond_type is _KernelConfigOp.condop_const:
                if cond_args is True or cond_args is False:
                    return (False, cond_args)

                elif cond_args is None:
                    try:
                        # whether cond_result was dynamic or not,
                        # it this point it is considered const
                        return (False, self.peek_cond_result())
                    except IndexError:
                        self.logger.warning(
                            'Referencing previous conditional,'
                            ' but there is none. Assuming true.'
                        )
                        return (False, True)

                # elif isinstance(cond_args, int):  previous cond by index

                else:
                    self.logger.error(
                        "Unknown const condition for %s context: %r",
                        (
                            context.get_context_desc()
                            if hasattr(context, "get_context_desc")
                            else "<unknown>"
                        ),
                        cond_args
                    )

                    raise KernelConfigLangInterpreterCondOpNotSupported(
                        "unknown const cond expr: %r" % cond_args
                    )
                # --

            elif cond_type is _KernelConfigOp.condop_operator_star_func:
                subdyn, subret = eval_subret(cond_args)
                return (subdyn, cond_func(*subret))

            elif cond_type is _KernelConfigOp.condop_operator_func:
                subdyn, subret = eval_subret(cond_args)
                return (subdyn, cond_func(subret))

            elif cond_type is _KernelConfigOp.condop_operator_cmp_func:
                return self.evaluate_cmp(cond_func, cond_args, source=source)

            else:
                self.logger.error(
                    "Unknown condition for %s context: %r (%r, %r)",
                    (
                        context.get_context_desc()
                        if hasattr(context, "get_context_desc")
                        else "<unknown>"
                    ),
                    getattr(cond_type, "name", cond_type),
                    cond_func, cond_args
                )

                raise KernelConfigLangInterpreterCondOpNotSupported(
                    "unknown condition %r: %r" % (cond_type, cond_args)
                )
        # --- end of evaluate_conditional (...) ---

        if conditional is None:
            cond_dynamic = False
            cond_result = True
            positive_cond = True
        else:
            positive_cond, cond_expr = conditional
            cond_dynamic, cond_result = dfs_inner(cond_expr)
        # --

        self.push_cond_result(cond_result)
        if positive_cond:
            return (cond_dynamic, cond_result)
        else:
            return (cond_dynamic, not cond_result)
    # --- end of evaluate_conditional (...) ---

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
        if cmdlist is None:
            return False

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
            self.logger.error("Error while parsing str")

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
                self.logger.error("Error while parsing file %r", infile)
                return None

            combined_cmdlist.extend(cmdlist)
        # --

        return combined_cmdlist
    # --- end of _parse_files (...) ---

# --- end of AbstractKernelConfigLangInterpreter ---


class KernelConfigLangInterpreter(AbstractKernelConfigLangInterpreter):

    def __init__(self, source_info, config_choices, **kwargs):
        super().__init__(**kwargs)
        self.source_info = None
        self.config_choices = None
        self._choice_op_dispatchers = None
        self._choice_str_op_dispatchers = None
        self._config_option_cond_context = None
        self._include_file_cond_context = cond.IncludeFileConditionContext()
        self._cmp_vars = None

        self.bind_config_choices(config_choices)
        self.bind_source_info(source_info)
        self.bind_cmp_vars()
    # --- end of __init__ (...) ---

    def bind_config_choices(self, config_choices):
        _KernelConfigOp = parser.KernelConfigOp

        self.config_choices = config_choices

        if config_choices is None:
            self._choice_op_dispatchers = {}
            self._choice_str_op_dispatchers = {}
            self._config_option_cond_context = None

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

            self._config_option_cond_context = (
                cond.ConfigOptionConditionContext(config_choices)
            )
        # ---
    # ---

    def bind_source_info(self, source_info):
        self.source_info = source_info
    # ---

    def bind_cmp_vars(self):
        cmp_vars = {}

        def add_cmp_var(name, value, str_constructor):
            nonlocal cmp_vars

            key = name.lower()

            assert key not in cmp_vars
            cmp_vars[key] = (value, str_constructor)
            return key
        # ---

        self._cmp_vars = cmp_vars

        source_info = self.source_info
        if source_info is not None:
            if hasattr(source_info, "kernelversion"):
                # otherwise, it is not a KernelInfo object
                add_cmp_var(
                    "kver",
                    source_info.kernelversion,
                    source_info.kernelversion.__class__.new_from_version_str
                )

                add_cmp_var(
                    "kmaj", source_info.kernelversion.version, int
                )

                add_cmp_var(
                    "kmin", source_info.kernelversion.sublevel, int
                )

                add_cmp_var(
                    "kpatch", source_info.kernelversion.patchlevel, int
                )
            # -- end hasattr kernelversion
        # -- end if source info
    # --- end of bind_cmp_vars (...) ---

    def lookup_cmp_operand(self, arg):
        lowarg = arg.lower()
        try:
            entry = self._cmp_vars[lowarg]
        except KeyError:
            return None
        else:
            return entry
    # ---

    def lookup_load_file(self, load_file, *, _osp_realpath=os.path.realpath):
        return _osp_realpath(load_file)

    lookup_include_file = lookup_load_file

    def process_command(self, cmdv, conditional):
        _KernelConfigOp = parser.KernelConfigOp

        cmd_arg = cmdv[0]

        if cmd_arg is _KernelConfigOp.op_include:
            include_file = self.lookup_include_file(cmdv[1])
            try:
                cond_dynamic, cond_eval = self.evaluate_conditional(
                    conditional,
                    self._include_file_cond_context.bind(include_file)
                )
            except KernelConfigLangInterpreterCondOpNotSupported:
                return False

            if not cond_eval:
                self.logger.debug(
                    "Include directive disabled by unmet conditions: %r",
                    include_file or cmdv[1]
                )
                return True

            elif not include_file:
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

            # When processing multiple options,
            # try to reuse the conditional part.
            # This is not possible if it contains "placeholder" conditions
            # such as a plain "exists" condition.
            cached_cond = None
            for option in cmdv[1]:
                if cached_cond is None:
                    try:
                        cond_dynamic, cond_eval = self.evaluate_conditional(
                            conditional,
                            self._config_option_cond_context.bind(option)
                        )
                    except KernelConfigLangInterpreterCondOpNotSupported:
                        return False

                    if not cond_dynamic:
                        cached_cond = cond_eval
                    # --

                else:
                    # FIXME: push one cond_eval per directive,
                    #         and not one cond_eval per option
                    self.push_cond_result(cached_cond)
                    cond_eval = cached_cond
                # --

                if not cond_eval:
                    pass

                elif not dispatcher(option):
                    return False
            # -- end for

            return True

        elif cmd_arg in self._choice_str_op_dispatchers:
            # dispatcher X option X value
            dispatcher = self._choice_str_op_dispatchers[cmd_arg]
            option = cmdv[1]

            try:
                cond_dynamic, cond_eval = self.evaluate_conditional(
                    conditional,
                    self._config_option_cond_context.bind(option)
                )
            except KernelConfigLangInterpreterCondOpNotSupported:
                return False

            if not cond_eval:
                return True
            else:
                return dispatcher(option, cmdv[2])

        else:
            self.logger.error("Unknown command %r", cmd_arg)
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
