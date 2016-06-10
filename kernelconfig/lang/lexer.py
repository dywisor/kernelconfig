# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import re

import ply.lex

__all__ = ["KernelConfigLangLexer"]


class KernelConfigLangLexer(object):
    """

    @ivar last_tok_was_cmd_sep:  lookbehind var for suppressing repeated
                                 CMD_END tokens
    @type last_tok_was_cmd_sep:  C{bool}
    """

    reserved = {
        "disable":           "OP_DISABLE",
        "n":                 "OP_DISABLE",

        "module":            "OP_MODULE",
        "m":                 "OP_MODULE",

        "builtin":           "OP_BUILTIN",
        "y":                 "OP_BUILTIN",

        "builtin-or-module": "OP_BUILTIN_OR_MODULE",
        "ym":                "OP_BUILTIN_OR_MODULE",

        "set":               "OP_SET_TO",
        "append":            "OP_APPEND",
        "add":               "OP_ADD",

        "include":           "OP_INCLUDE",

        "if":                "KW_IF",
        "unless":            "KW_UNLESS",
    }

    tokens = [
        "STR",
        "CMD_END",
    ] + list(set(reserved.values()))

    t_ignore = ' \t'

    regexp_escape_seq = re.compile(r'[\\]([.])')

    @classmethod
    def unescape_quoted_str(cls, s):
        return cls.regexp_escape_seq.sub(r'\1', s[1:-1])

    @classmethod
    def unquote_tok(cls, t):
        t.value = cls.unescape_quoted_str(t.value)
        t.type = "STR"
        return t

    def emit_cmd_end(self, t):
        if self.last_tok_was_cmd_sep:
            return None
        else:
            t.value = True
            t.type = "CMD_END"
            self.last_tok_was_cmd_sep = True
            return t
    # ---

    def emit_reset_cmd_end(self, t):
        self.last_tok_was_cmd_sep = False
        return t

    def t_comment(self, t):
        r'[ \t]*[#][^\n]*'
        # no-modify self.last_tok_was_cmd_sep
        return None

    def t_CMD_END(self, t):
        r'\;'
        return self.emit_cmd_end(t)

    def t_newline(self, t):
        r'[\n]+'
        t.lexer.lineno += len(t.value)
        return self.emit_cmd_end(t)

    def t_DQSTR(self, t):
        r'"([\\].|[^"\\])*"'
        return self.emit_reset_cmd_end(self.unquote_tok(t))

    def t_SQSTR(self, t):
        r"'([\\].|[^'\\])*'"
        return self.emit_reset_cmd_end(self.unquote_tok(t))

    def t_STR(self, t):
        r'[a-zA-Z0-9\_\-]+'
        slow = t.value.lower()
        try:
            stype = self.reserved[slow]
            t.value = slow
            t.type = stype
        except KeyError:
            pass

        return self.emit_reset_cmd_end(t)

    def t_error(self, t):
        raise SyntaxError((t.lexer.lineno, t.value[0]))

    def __init__(self):
        super().__init__()
        self.lexer = None
        self.last_tok_was_cmd_sep = True

    def reset(self):
        self.last_tok_was_cmd_sep = True

    def build(self, **kwargs):
        kwargs.setdefault("debug", False)
        self.lexer = ply.lex.lex(module=self, **kwargs)

    def input(self, *args, **kwargs):
        self.reset()
        self.lexer.input(*args, **kwargs)

    def token(self):
        return self.lexer.token()

# --- end of KernelConfigLangLexer ---


if __name__ == "__main__":
    def main():
        import sys

        l = KernelConfigLangLexer()
        l.build()

        for arg in sys.argv[1:]:
            l.input(arg)
            while True:
                tok = l.token()
                if not tok:
                    break
                print(tok)
        # --
    # ---

    main()
# --
