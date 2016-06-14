# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import re

import ply.lex

__all__ = ["KernelConfigLangLexer"]


class KernelConfigLangLexError(SyntaxError):

    def __init__(self, lineno, lexpos, message):
        self.lexpos = lexpos
        self.lineno = lineno
        super().__init__(message)
# ---


class KernelConfigLangLexInvalidCharError(KernelConfigLangLexError):
    def __init__(self, lineno, lexpos, invalid_char):
        super().__init__(lineno, lexpos, "invalid char %r" % invalid_char)
# ---


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

        "exist":             "KW_EXISTS",
        "exists":            "KW_EXISTS",
        "hardware-match":    "KW_HWMATCH",
        "hw":                "KW_HWMATCH",

        "true":              "KW_TRUE",
        "false":             "KW_FALSE",

        '!=':                "NE",
        '>=':                "GE",
        '<=':                "LE",
        '>':                 "GT",
        '<':                 "LT",
        '==':                "EQ_CMP",
        '=':                 "EQ",
        ':=':                "COL_EQ",
        '+=':                "PLUS_EQ",
        '|=':                "BITOR_EQ",

        '&&':                "AND",
        "and":               "AND",
        '||':                "OR",
        "or":                "OR",
        '!':                 "NOT",
        "not":               "NOT",

        "_":                 "KW_PLACEHOLDER"
    }

    tokens = (
        [
            "STR",
            "CMD_END",
            "LPAREN",
            "RPAREN",
        ]
        + list(set(reserved.values()))
    )

    t_ignore = ' \t'

    regexp_escape_seq = re.compile(r'[\\]([.])')

    @classmethod
    def unescape_quoted_str(cls, s):
        """This method replaces escape sequences in a str with their
        unescaped value.

        @param s:  input str
        @type  s:  C{str}

        @return:   output str
        @rtype:    C{str}
        """
        return cls.regexp_escape_seq.sub(r'\1', s[1:-1])

    @classmethod
    def unquote_tok(cls, t):
        """
        This method unquotes the value of a token and sets its type to "STR".

        @param t:  token
        @type  t:  LexToken

        @return:   input token, modified
        @rtype:    LexToken
        """
        t.value = cls.unescape_quoted_str(t.value)
        t.type = "STR"
        return t

    def emit_cmd_end(self, t):
        """Changes the input token to a CMD_END token,
        and suppresses repeated tokens of this type.

        Token methods ("t_") that produce such a token should wrap their
        return value with a call to this method.

        @param t:  token
        @type  t:  LexToken

        @return:   input token, modified
        @rtype:    LexToken or C{None}
        """
        if self.last_tok_was_cmd_sep:
            return None
        else:
            t.value = True
            t.type = "CMD_END"
            self.last_tok_was_cmd_sep = True
            return t
    # ---

    def emit_reset_cmd_end(self, t):
        """
        Resets the "suppress repeated CMD_END" state var
        and returns the input token.

        Token methods ("t_") that produce a not-None, not-CMD_END token
        should wrap their return value with a call to this method.

        @param t:  token
        @type  t:  LexToken

        @return:   input token, unmodified
        @rtype:    LexToken
        """
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

    def t_LPAREN(self, t):
        r'\('
        return self.emit_reset_cmd_end(t)

    def t_RPAREN(self, t):
        r'\)'
        return self.emit_reset_cmd_end(t)

    def t_op(self, t):
        r'[\<\>\=\!\|\+\:][\=]?'
        t.type = self.reserved[t.value]
        return self.emit_reset_cmd_end(t)

    def t_op_and(self, t):
        r'\&\&'
        t.type = self.reserved[t.value]
        return self.emit_reset_cmd_end(t)

    def t_op_or(self, t):
        r'\|\|'
        t.type = self.reserved[t.value]
        return self.emit_reset_cmd_end(t)

    def t_STR(self, t):
        r'[a-zA-Z0-9\_\-\+\.\/]+'
        slow = t.value.lower()
        try:
            stype = self.reserved[slow]
        except KeyError:
            pass
        else:
            t.value = slow
            t.type = stype
        # --
        return self.emit_reset_cmd_end(t)

    def t_error(self, t):
        raise KernelConfigLangLexInvalidCharError(
            t.lineno, t.lexpos, t.value[0]
        )

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
