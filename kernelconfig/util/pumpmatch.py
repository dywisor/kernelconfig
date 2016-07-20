# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import re

__all__ = ["PumpPattern"]


class PumpPattern(object):
    """
    Given a pattern p and some fillchars f,
    modify p so that each char c in p may optionally be followed by a fillchar
    unless it is a fillchar itself (in which case it is made optional),
    or it is the last char in the modified pattern p'.

    For that pattern, provide weighted match methods/functions.
    """

    __slots__ = ["pattern", "pattern_length", "fillchars", "expr"]

    def _gen_pump_pattern(self):
        resc = re.escape

        fillchar_set = self.fillchars
        fillchar_pat = "[{}]?".format(
            "".join(map(resc, sorted(fillchar_set)))
        )

        emit_fillchar = False
        for c in self.pattern:
            if c not in fillchar_set:
                if emit_fillchar:
                    yield fillchar_pat
                    emit_fillchar = False
                # --

                yield resc(c)
                emit_fillchar = True
            # --
        # --
    # --- end of _gen_pump_pattern (...) ---

    def _get_pump_pattern(self):
        return "".join(self._gen_pump_pattern())

    @property
    def pump_pattern(self):
        return self.expr.pattern

    def __init__(self, pattern, fillchars, flags=re.I):
        super().__init__()
        self.fillchars = set(fillchars)
        self.pattern = pattern
        self.pattern_length = len(pattern)
        self.expr = re.compile(self._get_pump_pattern(), flags=flags)

    def _finditer(self, string):
        patlen = self.pattern_length
        fillchar_set = self.fillchars

        for match in self.expr.finditer(string):
            start, end = match.span()
            if start >= 0:  # then also end >= 0,  discard empty matches
                # rate the match
                #   TODO: do this in a cost function
                #
                # matched substring:
                #  * 2*n points for having a match
                # [* deviation? up to n+k*(n-1) | k>0 points for not _?]
                #
                # prefix:
                #  * 3*n points for not having a prefix
                #  * n   points for having a prefix that ends with a fillchar
                #  * 0   points for any other prefix
                #        (or -len(prefix)?)
                #
                # suffix:
                #  * 2*n points for not having a suffix
                #  * n   points for having a suffix that starts with a fillchar
                #  * 0   points for any other suffix
                #

                prefix = string[:start]
                word = string[start:end]
                suffix = string[end:]

                weight = (
                    2 * patlen
                    + (
                        3 * patlen if not prefix
                        else (patlen if prefix[-1] in fillchar_set else 0)
                    )
                    + (
                        2 * patlen if not suffix
                        else (patlen if suffix[0] in fillchar_set else 0)
                    )
                )

                yield (weight, word)
            # --
        # -- end for
    # --- end of _finditer (...) ---

    def search(self, string):
        matches = list(self._finditer(string))
        return max(matches, key=lambda xv: xv[0]) if matches else (-1, None)
    # --- end of search (...) ---

    def search_all(self, strings):
        def gen_search_all(strings):
            for string in strings:
                weight, word = self.search(string)
                yield (weight, string, word)
        # ---

        return sorted(
            gen_search_all(strings), key=lambda xv: xv[0], reverse=True
        )
    # --- end of search_all (...) ---

    def __and__(self, other):
        return self.search_all(other)

# --- end of PumpPattern ---
