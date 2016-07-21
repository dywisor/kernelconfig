# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import re

__all__ = ["PumpPattern"]


PumpPatternMatchParts = collections.namedtuple(
    "PumpPatternMatchParts",
    "word prefix_word prefix prefix_sep suffix_word suffix suffix_sep"
)


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

    def split_match_parts(self, match):
        start, end = match.span()
        if start < 0:  # then also end < 0,  discard empty matches
            return None

        prefix_word = match.string[:start]
        if prefix_word and prefix_word[-1] in self.fillchars:
            prefix_sep = prefix_word[-1]
            prefix = prefix_word[:-1]
        else:
            prefix = prefix_word
            prefix_sep = None

        suffix_word = match.string[end:]
        if suffix_word and suffix_word[0] in self.fillchars:
            suffix_sep = suffix_word[0]
            suffix = suffix_word[1:]
        else:
            suffix = suffix_word
            suffix_sep = None

        word = match.string[start:end]

        return PumpPatternMatchParts(
            word=word,
            prefix_word=prefix_word, prefix=prefix, prefix_sep=prefix_sep,
            suffix_word=suffix_word, suffix=suffix, suffix_sep=suffix_sep
        )
    # --- end of split_match_parts (...) ---

    def weight_sort_key(self, weight):
        return weight[0]
    # --- end of weight_sort_key (...) ---

    def weight_nomatch(self, string):
        return (-1, None)

    def match_cost(self, match, mparts):
        # rate the match
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
        patlen = self.pattern_length

        return (
            2 * patlen
            + (
                3 * patlen if not mparts.prefix_word
                else (patlen if mparts.prefix_sep else 0)
            )
            + (
                2 * patlen if not mparts.suffix_word
                else (patlen if mparts.suffix_sep else 0)
            )
        )
    # --- end of match_cost (...) ---

    def weight_match(self, match):
        mparts = self.split_match_parts(match)
        if not mparts:
            return None

        return (self.match_cost(match, mparts), mparts.word)
    # --- end of weight_match (...) ---

    def _finditer(self, string):
        weight_match = self.weight_match
        for match in self.expr.finditer(string):
            weight = weight_match(match)
            if weight is not None:
                yield weight
            # --
        # -- end for
    # --- end of _finditer (...) ---

    def search(self, string):
        matches = list(self._finditer(string))
        if matches:
            return max(matches, key=self.weight_sort_key)
        else:
            return self.weight_nomatch(string)
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
