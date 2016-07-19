# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import enum
import operator

import ply.yacc

from ..abc import loggable
from . import lexer


__all__ = ["KernelConfigLangParser", "KernelConfigOp"]


@enum.unique
class KernelConfigOp(enum.IntEnum):
    (
        op_include,
        op_disable,
        op_module,
        op_builtin,
        op_builtin_or_module,
        op_set_to,
        op_append,
        op_add,
        cond_if,
        cond_unless,
        # FIXME: simplify, introduce cond_type with bitmask
        condop_const,
        condop_operator_func,
        condop_operator_star_func,
        condop_operator_cmp_func,
        condop_exists,
        condop_hwmatch,
    ) = range(16)

    @classmethod
    def is_op(cls, value):
        try:
            cls(value)
        except (ValueError, TypeError):
            return False
        else:
            return True

# --- end of KernelConfigOp ---


def dict_composition(da, db):
    # d :: k -> u, d = da o db | da :: k -> v, db :: v -> u
    return {k: db[v] for k, v in da.items()}


def dict_composition_partial(da, db):
    # d :: k -> u, d = da o db | da :: k -> v, db :: v' -> u
    return {k: db[v] for k, v in da.items() if v in db}


class KernelConfigLangParser(loggable.AbstractLoggable):

    tokens = tuple(lexer.KernelConfigLangLexer.tokens)

    precedence = (
        (
            "nonassoc",
            "NE", "GE", "LE", "GT", "LT", "EQ_CMP",
            "EQ", "COL_EQ", "PLUS_EQ", "BITOR_EQ"
        ),
        ("right", "NOT"),
        ("left", "AND"),
        ("left", "OR"),
    )

    op_map = dict_composition_partial(
        lexer.KernelConfigLangLexer.reserved,
        {
            "AND":    all,
            "OR":     any,
            "NOT":    operator.__not__,
            "NE":     operator.__ne__,
            "GE":     operator.__ge__,
            "LE":     operator.__le__,
            "GT":     operator.__gt__,
            "LT":     operator.__lt__,
            "EQ":     operator.__eq__,
            "EQ_CMP": operator.__eq__
        }
    )

    @classmethod
    def build_cond_expr(cls, cond_type, cond_func, cond_args):
        if __debug__:
            assert KernelConfigOp.is_op(cond_type)
            assert cond_func is None or hasattr(cond_func, "__call__")
        # --
        return [cond_type, cond_func, cond_args]

    def p_lang(self, p):
        '''lang : command_list'''
        p[0] = p[1]

    def p_command_list_empty(self, p):
        '''command_list : '''
        p[0] = []

    def p_command_list_nop(self, p):
        '''command_list : CMD_END'''
        p[0] = []

    def p_command_list_one(self, p):
        '''command_list : conditional_command'''
        p[0] = [p[1]]

    def p_command_list_many(self, p):
        '''command_list : conditional_command CMD_END command_list'''
        p[0] = [p[1]] + p[3]

    def p_command_list_bad_missing_sep(self, p):
        '''command_list : conditional_command error'''
        self.handle_parse_error(p, 2, "expected newline or ';' after command")

    def p_conditional_command_nocond(self, p):
        '''conditional_command : command'''
        p[0] = p[1]

    # ---
    # conditional statement
    #

    def p_conditional_command_if(self, p):
        '''conditional_command : command KW_IF cond_expr'''
        p[0] = [KernelConfigOp.cond_if, p[3], p[1]]

    def p_conditional_command_unless(self, p):
        '''conditional_command : command KW_UNLESS cond_expr'''
        p[0] = [KernelConfigOp.cond_unless, p[3], p[1]]

    def p_conditional_command_bad_missing_cond_expr(self, p):
        '''conditional_command : command KW_IF error
                               | command KW_UNLESS error'''
        self.handle_parse_error(p, 3, "expected conditional expression")
    # ---

    # ---
    # include file
    #

    def p_command_include_file(self, p):
        '''command : OP_INCLUDE STR'''
        p[0] = [KernelConfigOp.op_include, p[2]]

    def p_command_include_file_bad(self, p):
        '''command : OP_INCLUDE error'''
        self.handle_parse_error(
            p, 2, "expected file or name after %s directive" % p[1]
        )

    # ---
    # "d-m-b option"
    #   disable|module|builtin|builtin-or-module OPTION [OPTION...]
    #

    def p_command_disable(self, p):
        '''command : OP_DISABLE str_list'''
        p[0] = [KernelConfigOp.op_disable, p[2]]

    def p_command_module(self, p):
        '''command : OP_MODULE str_list'''
        p[0] = [KernelConfigOp.op_module, p[2]]

    def p_command_builtin(self, p):
        '''command : OP_BUILTIN str_list'''
        p[0] = [KernelConfigOp.op_builtin, p[2]]

    def p_command_builtin_or_module(self, p):
        '''command : OP_BUILTIN_OR_MODULE str_list'''
        p[0] = [KernelConfigOp.op_builtin_or_module, p[2]]

    def p_command_dmb_bad_no_options(self, p):
        '''command : OP_DISABLE error
                   | OP_MODULE  error
                   | OP_BUILTIN error
                   | OP_BUILTIN_OR_MODULE error
        '''
        self.handle_parse_error(
            p, 2,
            "expected one or more config options after %s directive" % p[1]
        )

    # ---
    # "se-ap-ad option"
    #   set|append|add OPTION VALUE
    #

    def p_command_set_to(self, p):
        '''command : OP_SET_TO STR STR'''
        p[0] = [KernelConfigOp.op_set_to, p[2], p[3]]

    def p_command_append(self, p):
        '''command : OP_APPEND STR STR'''
        p[0] = [KernelConfigOp.op_append, p[2], p[3]]

    def p_command_add(self, p):
        '''command : OP_ADD STR STR'''
        p[0] = [KernelConfigOp.op_add, p[2], p[3]]

    def p_command_seapad_bad_missing_option(self, p):
        '''command : OP_SET_TO error
                   | OP_APPEND error
                   | OP_ADD    error
        '''
        self.handle_parse_error(
            p, 2, "expected a config option after %s directive" % p[1]
        )

    def p_command_seapad_bad_missing_value(self, p):
        '''command : OP_SET_TO STR error
                   | OP_APPEND STR error
                   | OP_ADD    STR error
        '''
        self.handle_parse_error(
            p, 2, "expected a value after %s directive" % p[1]
        )

    # ---
    # OPTION=n
    # OPTION=m
    # OPTION=y
    # OPTION=ym
    # OPTION="..str.."
    #

    def p_command_disable_assignop(self, p):
        '''command : STR EQ     OP_DISABLE
                   | STR COL_EQ OP_DISABLE
        '''
        p[0] = [KernelConfigOp.op_disable, [p[1]]]

    def p_command_module_assignop(self, p):
        '''command : STR EQ     OP_MODULE
                   | STR COL_EQ OP_MODULE
        '''
        p[0] = [KernelConfigOp.op_module, [p[1]]]

    def p_command_builtin_assignop(self, p):
        '''command : STR EQ     OP_BUILTIN
                   | STR COL_EQ OP_BUILTIN
        '''
        p[0] = [KernelConfigOp.op_builtin, [p[1]]]

    def p_command_builtin_or_module_assignop(self, p):
        '''command : STR EQ     OP_BUILTIN_OR_MODULE
                   | STR COL_EQ OP_BUILTIN_OR_MODULE
        '''
        p[0] = [KernelConfigOp.op_builtin_or_module, [p[1]]]

    def p_command_set_to_assignop(self, p):
        '''command : STR EQ     STR
                   | STR COL_EQ STR
        '''
        p[0] = [KernelConfigOp.op_set_to, p[1], p[3]]

    def p_command_append_assignop(self, p):
        '''command : STR PLUS_EQ STR'''
        p[0] = [KernelConfigOp.op_append, p[1], p[3]]

    def p_command_add_assignop(self, p):
        '''command : STR BITOR_EQ STR'''
        p[0] = [KernelConfigOp.op_add, p[1], p[3]]

    def p_command_assignop_bad(self, p):
        '''command : STR EQ       error
                   | STR COL_EQ   error
                   | STR PLUS_EQ  error
                   | STR BITOR_EQ error'''
        self.handle_parse_error(
            p, 3, "expected value after %s%s" % (p[1], p[2])
        )

    # ---
    # str list
    #

    def p_str_list_one(self, p):
        '''str_list : STR'''
        p[0] = [p[1]]

    def p_str_list_many(self, p):
        '''str_list : STR str_list'''
        p[0] = [p[1]] + p[2]

    # ---
    # conditional expressions
    #

    def p_conditional_expr_prev_value(self, p):
        '''cond_expr : KW_PLACEHOLDER'''
        p[0] = self.build_cond_expr(KernelConfigOp.condop_const, None, None)

    def p_conditional_expr_true(self, p):
        '''cond_expr : KW_TRUE'''
        p[0] = self.build_cond_expr(KernelConfigOp.condop_const, None, True)

    def p_conditional_expr_false(self, p):
        '''cond_expr : KW_FALSE'''
        p[0] = self.build_cond_expr(KernelConfigOp.condop_const, None, False)

    def p_conditional_expr_exists_explicit_arg(self, p):
        '''cond_expr : KW_EXISTS STR'''
        p[0] = self.build_cond_expr(KernelConfigOp.condop_exists, None, p[2])

    def p_conditional_expr_exists_implicit_arg(self, p):
        '''cond_expr : KW_EXISTS
                     | KW_EXISTS KW_PLACEHOLDER'''
        p[0] = self.build_cond_expr(KernelConfigOp.condop_exists, None, None)

    def p_conditional_expr_hwmatch(self, p):
        '''cond_expr : KW_HWMATCH str_list'''
        p[0] = self.build_cond_expr(KernelConfigOp.condop_hwmatch, None, p[2])

    def p_conditional_expr_in_parens(self, p):
        '''cond_expr : LPAREN cond_expr RPAREN'''
        p[0] = p[2]

    def p_conditional_expr_not(self, p):
        '''cond_expr : NOT cond_expr'''
        p[0] = self.build_cond_expr(
            KernelConfigOp.condop_operator_star_func,
            self.op_map[p[1]],
            [p[2]]
        )

    def p_conditional_expr_andor(self, p):
        '''cond_expr : cond_expr AND cond_expr
                     | cond_expr OR  cond_expr
        '''
        p[0] = self.build_cond_expr(
            KernelConfigOp.condop_operator_func,
            self.op_map[p[2]],
            [p[1], p[3]]
        )

    def p_conditional_expr_cmp(self, p):
        '''cond_expr : STR NE     STR
                     | STR GE     STR
                     | STR LE     STR
                     | STR GT     STR
                     | STR LT     STR
                     | STR EQ_CMP STR
                     | STR EQ     STR
        '''
        p[0] = self.build_cond_expr(
            KernelConfigOp.condop_operator_cmp_func,
            self.op_map[p[2]],
            [p[1], p[3]]
        )

    def p_error(self, p):
        self.parse_error = 1
        if not p:
            self.logger.error("Unexpected end of input file")
    # ---

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lexobj = lexer.KernelConfigLangLexer()
        self.parser = None
        self.lexer = None
        self.infile = None
        self.filename = None

    def reset(self):
        assert self._lexobj is not None
        assert self.parser is not None
        self._lexobj.reset()
        self.parse_error = 0
        self.infile = None
        self.filename = None

    def build(self, **kwargs):
        kwargs.setdefault("debug", False)
        self._lexobj.build()
        self.lexer = self._lexobj.lexer
        self.parser = ply.yacc.yacc(module=self, **kwargs)

    def build_if_needed(self, **kwargs):
        if self.parser is None:
            self.build(**kwargs)

    def _parse(self, data, **kwargs):
        try:
            parse_ret = self.parser.parse(data, lexer=self.lexer, **kwargs)
        except lexer.KernelConfigLangLexError as lex_err:
            self.logger.error(
                "{infile}: line {lineno:d}: {msg}".format(
                    infile=(self.filename or self.infile or "<input>"),
                    lineno=lex_err.lineno, msg=lex_err.args[0]
                )
            )
            return None
        # --

        if self.parse_error:
            return None
        else:
            return parse_ret

    def parse(self, data, **kwargs):
        self.reset()
        return self._parse(data, **kwargs)

    def parse_file(self, infile, filename=None, **kwargs):
        self.reset()
        self.infile = infile
        self.filename = filename or infile

        # COULDFIX: MAYBE: fileio compress open
        with open(infile, "rt") as fh:
            ret = self._parse(fh.read(), **kwargs)
        return ret

    def handle_parse_error(self, p, tok_idx, message):
        self.logger.error(
            "{infile}: line {lineno:d}: col {col:d}: {msg}".format(
                infile=(self.filename or self.infile or "<input>"),
                lineno=p.lineno(tok_idx), col=p.lexpos(tok_idx), msg=message
            )
        )
        self.parse_error = 1  # redundant
        p[0] = None

# --- end of KernelConfigLangParser ---


def build_parser():
    p = KernelConfigLangParser()
    p.build()
    return p
# --- end of build_parser (...) ---


if __name__ == "__main__":
    def main():
        import os.path
        import sys

        p = build_parser()

        for arg in sys.argv[1:]:
            if arg:
                if os.path.isabs(arg):
                    result = p.parse_file(arg)
                else:
                    result = p.parse(arg if arg[0] != "@" else arg[1:])

                print(arg, "==>", result)
        # --
    # ---

    main()
# --
