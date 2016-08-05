# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections
import logging
import os

from ..abc import loggable
from ..util import filequeue
from ..util import objcache
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

    @ivar _opcode_mask:       set of ignored instructions (as opcode)
    @type _opcode_mask:       C{set} of L{KernelConfigOp}

    @ivar _file_input_queue:  file input queue
    @type _file_input_queue:  C{collections.deque}

    @ivar _parser:            parser
    @type _parser:            L{KernelConfigLangParser}
    """

    DEFAULT_COND_RESULT_BUFFER_SIZE = 1

    def __init__(self, cond_result_buffer_size=True, **kwargs):
        super().__init__(**kwargs)
        self._file_input_queue = filequeue.FileInputQueue()
        self._parser = self.create_loggable(
            parser.KernelConfigLangParser, logger_name="Parser"
        )

        if cond_result_buffer_size is True:
            cond_result_buffer_size = self.DEFAULT_COND_RESULT_BUFFER_SIZE

        self._conditional_result_buffer = collections.deque(
            maxlen=cond_result_buffer_size
        )

        self._opcode_mask = set()
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
        # no-clear opcode mask
    # ---

    def get_opcode(self, opcode_arg):
        """
        Returns the KernelConfigOp opcode value for the given opcode arg,
        which can be an int, str or KernelConfigOp.

        @param opcode_arg:  input opcode "reference"
        @type  opcode_arg:  C{str} | C{int} | L{KernelConfigOp}

        @return: KernelConfigOp opcode
        @rtype:  L{KernelConfigOp}
        """
        if isinstance(opcode_arg, str):
            if opcode_arg.startswith("op_"):
                opcode_value = getattr(parser.KernelConfigOp, opcode_arg)
            else:
                opcode_value = getattr(
                    parser.KernelConfigOp, "op_{}".format(opcode_arg)
                )
        else:
            opcode_value = parser.KernelConfigOp(opcode_arg)

        if not opcode_value.name.startswith("op_"):
            raise ValueError("not an opcode: {!r}".format(opcode_value))

        return opcode_value
    # --- end of get_opcode (...) ---

    def clear_opcode_mask(self):
        """
        Resets the opcode mask to its initial value,
        which allows all instructions.
        """
        self._opcode_mask.clear()
    # --- end of clear_opcode_mask (...) ---

    def _disable_opcode(self, opcode_value):
        self._opcode_mask.add(opcode_value)

    def _enable_opcode(self, opcode_value):
        self._opcode_mask.discard(opcode_value)

    def disable_op(self, opcode_arg):
        """
        Disables an instruction,
        which can be given as int, str or KernelConfigOp opcode.

        Future instructions of this kind will be ignored by the interpreter.
        """
        self._disable_opcode(self.get_opcode(opcode_arg))
    # --- end of disable_opcode (...) ---

    def enable_op(self, opcode_arg):
        """
        (Re-)Enables an instruction,
        which can be given as int, str or KernelConfigOp opcode.

        Future instructions of this kind will be processed as usual.
        """
        self._enable_opcode(self.get_opcode(opcode_arg))
    # --- end of enable_opcode (...) ---

    def check_command_masked_opcode(self, cmdv):
        """
        @param cmdv:  a non-structured command,
                      must be non-empty and the first item should be an opcode
                      (otherwise, undefined return value)
        @type  cmdv:  C{list}

        @return:  True if the instruction is currently masked, else False
        @rtype:   C{bool}
        """
        return cmdv[0] in self._opcode_mask
    # --- end of check_command_masked_opcode (...) ---

    def log_command_masked_opcode(self, cmdv, conditional=None):
        """
        Logs that a command's instruction opcode is currently masked
        and returns True.

        @param cmdv:           a non-structured command,
                               must be non-empty
                               and the first item must be an opcode
        @type  cmdv:           C{list}
        @keyword conditional:  the command's conditional (if any), ignored

        @return: always True
        @rtype:  C{bool}
        """
        self.logger.debug(
            "Ignoring command (masked opcode): %s", cmdv[0].name
        )
        return True
    # --- end of log_command_masked_opcode (...) ---

    def assert_empty_file_input_queue(self):
        """
        Helper method that makes sure
        that the file input queue is currently empty.

        @raises AssertionError:  if the file input queue is not empty

        @return:  None (implicit)
        """
        if not self._file_input_queue.empty():
            raise AssertionError("unclean interpreter state")
    # --- end of assert_empty_file_input_queue (...) ---

    def add_input_file(self, infile):
        """Adds a file to the end of the file input queue.

        Note: the file should be "normalized" first by looking it up
              with either lookup_include_file() or lookup_load_file(),
              depending on whether it is an "include" command-type
              or process_file()-type input file.

        @raises filequeue.DuplicateItemKey:  passed through from
                                             filequeue.FileInputQueue.put

        @param infile:  input file
        @type  infile:  C{str}

        @return:  True if input file has been added, else False
        @rtype:   C{bool}
        """
        if self._file_input_queue.put(infile):
            self.logger.debug("Added %r to the input file queue", infile)
            return True
        else:
            self.logger.debug(
                "Not adding %r to the input file queue: already enqueued",
                infile
            )
            return False
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
        """Locates files for the "include" command.

        The include file is possibly subject to glob-expansion
        and thus the number of returned files varies.

        Should return None (or an empty list) if no file found.

        @param include_file:  "key", e.g. file name
        @type  include_file:  C{str}

        @return:  C{None} or filepath list
        @rtype:   C{None} or C{list} of C{str}
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

        Derived classes must implement this method.
        They should also check whether the command is currently masked,
        which can be done with check_command_masked_opcode(cmdv),
        and handle that case appropriately,
        e.g. by returning from log_command_masked_opcode(cmdv, conditional).

        @param cmdv:         the command, a [opcode, ...] list
        @type  cmdv:         C{list}

        @param conditional:  conditional part or C{None}
        @type  conditional:  2-tuple(C{bool}, C{list}) or C{None}

        @return:  True or None if successful, False if not
        @rtype:   C{bool} or C{None}
        """
        # this just an example
        if self.check_command_masked_opcode(cmdv):
            return self.log_command_masked_opcode(cmdv, conditional)

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

        if __debug__:
            # this should be guaranteed by the parser
            assert cmdv
            assert isinstance(cmdv[0], parser.KernelConfigOp)
        # --

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
        while True:
            try:
                input_file = self._file_input_queue.get()
            except filequeue.Empty:
                return True

            cmdlist = self._parse_files([input_file])
            ret = self._process_one_cmdlist(cmdlist)
            if not ret:
                return ret
        # --
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

        @raises filequeue.DuplicateItemKey:

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

            self.add_input_file(filepath)  # raises DuplicateItemKey
        # -- end for
        return self._process_file_input_queue()
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
    """
    @ivar object_cache:       a cache of recently used objects,
                              so that repeated str-to-object conversions
                              can be circumvented
    @type object_cache:       L{ObjectCache}
    """

    def __init__(
        self, install_info, source_info, config_choices, hwdetector, *,
        object_cache_size=32, **kwargs
    ):
        super().__init__(**kwargs)
        self.object_cache = objcache.ObjectCache(
            maxsize=object_cache_size, typed=True
        )
        self.install_info = install_info
        self.source_info = None
        self.config_choices = None
        self.hwdetector = None
        self._choice_op_dispatchers = None
        self._choice_str_op_dispatchers = None
        self._config_option_cond_context = None
        self._include_file_cond_context = cond.IncludeFileConditionContext()
        self._cmp_vars = None

        self.bind_config_choices(config_choices)
        self.bind_source_info(source_info)
        self.bind_hwdetector(hwdetector)
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

    def bind_hwdetector(self, hwdetector):
        self.hwdetector = hwdetector
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

        int_oper = self.object_cache.wraps(int)

        source_info = self.source_info
        if source_info is not None:
            if hasattr(source_info, "kernelversion"):
                # otherwise, it is not a KernelInfo object
                add_cmp_var(
                    "kver",
                    source_info.kernelversion,
                    self.object_cache.wraps(
                        source_info.kernelversion.__class__.
                        new_from_version_str
                    )
                )

                add_cmp_var(
                    "kmaj", source_info.kernelversion.version, int_oper
                )

                add_cmp_var(
                    "kmin", source_info.kernelversion.sublevel, int_oper
                )

                add_cmp_var(
                    "kpatch", source_info.kernelversion.patchlevel, int_oper
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

    def lookup_include_file(self, include_file):
        norm_include_file = os.path.normpath(include_file)

        if not os.path.isabs(norm_include_file):
            return self.install_info.get_include_files(norm_include_file)
        elif os.path.isfile(norm_include_file):
            return [norm_include_file]
        else:
            return None
    # --- end of lookup_include_file (...) ---

    def translate_module_names_to_config_options(self, module_names):
        """
        Translates a sequence of kernel module names into config option names.

        @param module_names:  iterable containing kernel module names
        @type  module_names:  iterable of C{str}

        @return: 2-tuple (
                    list of modules that could not be translated,
                    deduplicated list of config options
                 )
        @rtype:  2-tuple (C{list} of C{str}, C{list} of C{str})
        """
        modlist = list(module_names)

        hwdetector = self.hwdetector
        if hwdetector is None:
            self.logger.warning(
                (
                    "Cannot translate module names to config options,"
                    " no mapping has been provided: %r"
                ),
                modlist
            )

            return (modlist, None)

        else:
            return hwdetector.translate_module_names_to_config_options(modlist)
    # --- end of translate_module_names_to_config_options (...) ---

    def translate_modalias_to_config_options(self, modaliases):
        """
        Translate a sequence of module aliases to config options.

        This is done by translating module aliases into module names first,
        and then module names to config options.

        The result is a 2-tuple (unresolved modules, resolved modules).
        Modalias identifiers for which no module could be found
        are quietly ignored.

        @param modaliases:  iterable containing kernel module names
        @type  modaliases:  iterable of C{str}

        @return: 2-tuple (
                    list of modules that could not be translated,
                    deduplicated list of config options
                 )
        @rtype:  2-tuple (C{list} of C{str}, C{list} of C{str})
        """
        hwdetector = self.hwdetector
        if hwdetector is None:
            self.logger.warning(
                (
                    'Cannot translate modalias to modules,'
                    ' no mapping has been provided.'
                )
            )
            return None

        else:
            return hwdetector.translate_modalias_to_config_options(modaliases)
    # --- end of translate_modalias_to_config_options (...) ---

    def process_command(self, cmdv, conditional):
        _KernelConfigOp = parser.KernelConfigOp

        def _iter_evaluate_conditional(context_obj, conditional, items):
            # When processing multiple options/include files,
            # try to reuse the conditional part.
            # This is not possible if it contains "placeholder" conditions
            # such as a plain "exists" condition.
            cached_cond = None

            for item in items:
                if cached_cond is None:
                    try:
                        cond_dynamic, cond_eval = self.evaluate_conditional(
                            conditional, context_obj.bind(item)
                        )
                    except KernelConfigLangInterpreterCondOpNotSupported:
                        cond_dynamic = True  # unused
                        cond_eval = None
                    else:
                        if not cond_dynamic:
                            cached_cond = cond_eval
                else:
                    # FIXME: push one cond_eval per directive,
                    #         and not one cond_eval per option
                    self.push_cond_result(cached_cond)
                    cond_eval = cached_cond
                # --

                yield (cond_eval, item)
            # -- end for
        # --- end of _iter_evaluate_conditional (...) ---

        def iter_options_evaluate_conditional(conditional, oper_type, args):
            nonlocal _KernelConfigOp

            if oper_type is _KernelConfigOp.oper_option:
                options = args

            elif (
                oper_type is _KernelConfigOp.oper_driver
                or oper_type is _KernelConfigOp.oper_modalias
            ):
                if oper_type is _KernelConfigOp.oper_driver:
                    modules_missing, options = (
                        self.translate_module_names_to_config_options(args)
                    )
                else:
                    modules_missing, options = (
                        self.translate_modalias_to_config_options(args)
                    )
                    if not options:
                        self.logger.warning(
                            "Could not get module names for config aliases %r",
                            args
                        )
                        if not modules_missing:
                            # otherwise, continue with the next log message
                            # and return "no can do" later
                            return [(None, None)]
                # --

                if modules_missing:
                    for module_name in modules_missing:
                        # "if exist":
                        #   affects config options, not module names
                        #
                        # otherwise,
                        # add dummy entry to options and keep going
                        self.logger.warning(
                            "Could not get config options for module %r",
                            module_name
                        )
                    # --
                    return [(None, None)]
                # -- end if modules missing

            else:
                self.logger.error("Unknown operand type %r", oper_type)
                raise NotImplementedError("unknown operand type", oper_type)

            return _iter_evaluate_conditional(
                self._config_option_cond_context, conditional, options
            )
        # --- end of iter_options_evaluate_conditional (...) ---

        def iter_include_files_evaluate_conditional(
            conditional, include_files
        ):
            return _iter_evaluate_conditional(
                self._include_file_cond_context, conditional, include_files
            )
        # --- end of iter_include_files_evaluate_conditional (...) ---

        cmd_arg = cmdv[0]

        if self.check_command_masked_opcode(cmdv):
            return self.log_command_masked_opcode(cmdv, conditional)

        elif cmd_arg is _KernelConfigOp.op_include:
            include_files_in = self.lookup_include_file(cmdv[1])

            if not include_files_in:
                try:
                    cond_dynamic, cond_eval = self.evaluate_conditional(
                        conditional,
                        self._include_file_cond_context.bind(None)
                    )
                except KernelConfigLangInterpreterCondOpNotSupported:
                    return False

                if not cond_eval:
                    self.logger.debug(
                        "Include directive disabled by unmet conditions: %r",
                        cmdv[1]
                    )
                    return True

                else:
                    self.logger.error(
                        "include file %s does not exist", cmdv[1]
                    )
                    return False
            # -- end if no files found

            include_files_to_load = []
            include_files_filtered = []

            for cond_eval, include_file in (
                iter_include_files_evaluate_conditional(
                    conditional, include_files_in
                )
            ):
                if cond_eval is None:
                    return False
                elif cond_eval:
                    # -- self.add_input_file(include_file) -- below
                    include_files_to_load.append(include_file)
                else:
                    include_files_filtered.append(include_file)
            # --

            if include_files_to_load:
                if self.logger.isEnabledFor(logging.DEBUG):
                    num_include_files = len(include_files_to_load)

                    if include_files_filtered:
                        self.logger.debug(
                            "Include directive partially disabled: %r",
                            include_files_filtered
                        )
                    # --

                    if num_include_files > 1:
                        if num_include_files < 5:
                            self.logger.debug(
                                "Include directive matched %d files: %r",
                                num_include_files, include_files_to_load
                            )
                        else:
                            self.logger.debug(
                                "Include directive matched %d files",
                                num_include_files
                            )
                    # -- end if

                    del num_include_files
                # -- end if debug-log

                for include_file in include_files_to_load:
                    try:
                        self.add_input_file(include_file)
                    except filequeue.DuplicateItemKey:
                        return False

            elif include_files_filtered:
                self.logger.debug(
                    "Include directive disabled by unmet conditions: %r",
                    include_files_filtered
                )

            else:
                raise AssertionError((
                    'non-empty include_files_in implies '
                    'non-empty include_files_to_load|include_files_filtered'
                ))
            # --

            return True

        elif cmd_arg is _KernelConfigOp.op_hwdetect:
            # hwdetect conditionals are context free,
            #  pass an empty context function dict
            cond_dynamic, cond_eval = self.evaluate_conditional(
                conditional, {}
            )

            # don't bother scanning /sys if the conditional evaluated to false
            if not cond_eval:
                self.logger.debug(
                    'hardware-detect directive disabled by unmet conditions'
                )
                return True
            # --

            hwdetector = self.hwdetector
            if hwdetector is None:
                self.logger.warning("Hardware detection is not available")
                return False
            # --

            errors, config_suggestions = hwdetector.get_suggestions()
            if errors:
                # already logged
                return False

            dispatcher = self.config_choices.option_set_to
            for option, value in config_suggestions.items():
                if not dispatcher(option, value):
                    return False

            return True

        elif cmd_arg in self._choice_op_dispatchers:
            # dispatcher X options
            dispatcher = self._choice_op_dispatchers[cmd_arg]

            for cond_eval, option in iter_options_evaluate_conditional(
                conditional, cmdv[1], cmdv[2]
            ):
                if cond_eval is None:
                    return False
                elif not cond_eval:
                    pass
                elif not dispatcher(option):
                    return False
            # -- end for

            return True

        elif cmd_arg in self._choice_str_op_dispatchers:
            # dispatcher X option X value
            dispatcher = self._choice_str_op_dispatchers[cmd_arg]

            for cond_eval, option in iter_options_evaluate_conditional(
                conditional, cmdv[1], cmdv[2]
            ):
                if cond_eval is None:
                    return False
                elif not cond_eval:
                    pass
                elif not dispatcher(option, cmdv[3]):
                    return False
            # -- end for

            return True

        else:
            self.logger.error("Unknown command %r", cmd_arg)
            raise NotImplementedError("unknown cmd_arg", cmd_arg)
    # --- end of process_command (...) ---

# --- end of KernelConfigLangInterpreter ---


if __name__ == "__main__":
    def main():
        import sys

        class MiniInterpreter(AbstractKernelConfigLangInterpreter):

            def lookup_cmp_operand(self, arg):
                return None

            def lookup_load_file(self, load_file):
                fpath = os.path.realpath(load_file) if load_file else None
                if fpath and os.path.exists(fpath):
                    return fpath
                else:
                    return None

            def lookup_include_file(self, include_file):
                fpath = self.lookup_load_file(include_file)
                return [fpath] if fpath else None

            def process_command(self, cmdv, conditional):
                print("COMMAND      ", cmdv)
                print("  CONDITIONAL", conditional)
                if self.check_command_masked_opcode(cmdv):
                    print("  IS MASKED.")
        # ---

        ipret = MiniInterpreter()
        for arg in sys.argv[1:]:
            ipret.process_file(arg)
    # ---

    main()
