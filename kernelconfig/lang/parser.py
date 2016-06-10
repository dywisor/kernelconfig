# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import ply.yacc

if __name__ == "__main__":
    import lexer
else:
    from . import lexer


__all__ = ["KernelConfigLangParser"]


class KernelConfigLangParser(object):

    tokens = tuple(lexer.KernelConfigLangLexer.tokens)

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

    def p_conditional_command_nocond(self, p):
        '''conditional_command : command'''
        p[0] = p[1]

    def p_conditional_command_if(self, p):
        '''conditional_command : command KW_IF str_list'''
        p[0] = [p[2], p[3], p[1]]

    def p_conditional_command_unless(self, p):
        '''conditional_command : command KW_UNLESS str_list'''
        p[0] = [p[2], p[3], p[1]]

    def p_command_include_file(self, p):
        '''command : OP_INCLUDE STR'''
        p[0] = [p[1], None, p[2]]

    def p_command_disable(self, p):
        '''command : OP_DISABLE str_list'''
        p[0] = [p[1], p[2], None]

    def p_command_module(self, p):
        '''command : OP_MODULE str_list'''
        p[0] = [p[1], p[2], None]

    def p_command_builtin(self, p):
        '''command : OP_BUILTIN str_list'''
        p[0] = [p[1], p[2], None]

    def p_command_builtin_or_module(self, p):
        '''command : OP_BUILTIN_OR_MODULE str_list'''
        p[0] = [p[1], p[2], None]

    def p_command_set_to(self, p):
        '''command : OP_SET_TO STR STR'''
        p[0] = [p[1], [p[2]], p[3]]

    def p_command_append(self, p):
        '''command : OP_APPEND STR STR'''
        p[0] = [p[1], [p[2]], p[3]]

    def p_command_add(self, p):
        '''command : OP_ADD STR STR'''
        p[0] = [p[1], [p[2]], p[3]]

    def p_str_list_one(self, p):
        '''str_list : STR'''
        p[0] = [p[1]]

    def p_str_list_many(self, p):
        '''str_list : STR str_list'''
        p[0] = [p[1]] + p[2]

    def p_error(self, p):
        raise SyntaxError(p)

    def __init__(self):
        super().__init__()
        self._lexobj = lexer.KernelConfigLangLexer()
        self.parser = None
        self.lexer = None

    def reset(self):
        assert self._lexobj is not None
        assert self.parser is not None
        self._lexobj.reset()
        self.parser.error = 0

    def build(self, **kwargs):
        kwargs.setdefault("debug", False)
        self._lexobj.build()
        self.lexer = self._lexobj.lexer
        self.parser = ply.yacc.yacc(module=self, **kwargs)

    def parse(self, data, **kwargs):
        self.reset()
        parse_ret = self.parser.parse(data, lexer=self.lexer, **kwargs)
        if self.parser.error:
            return None
        else:
            return parse_ret

# --- end of KernelConfigLangParser ---


if __name__ == "__main__":
    def main():
        import sys

        p = KernelConfigLangParser()
        p.build()

        for arg in sys.argv[1:]:
            result = p.parse(arg)
            print(arg, "==>", result)
        # --
    # ---

    main()
# --
