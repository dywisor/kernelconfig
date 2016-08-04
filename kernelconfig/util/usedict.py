# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections


__all__ = ["BoolFlagDict"]


class BoolFlagDict(collections.OrderedDict):
    """A dict for dealing with USE and FEATURES variables."""

    @classmethod
    def new_from_str(cls, string):
        obj = cls()
        obj.read_str(string)
        return obj
    # ---

    def gen_words(self):
        for flag_name, flag_value in self.items():
            if flag_value:
                yield str(flag_name)
            else:
                yield "-{!s}".format(flag_name)
        # --
    # ---

    def get_str(self):
        return " ".join(self.gen_words())
    # ---

    __str__ = get_str

    def _enable_or_disable(self, words, val_true):
        for word in filter(None, words):
            if word[0] == "-":
                assert len(word) > 1
                self[word[1:]] = not val_true
            else:
                self[word] = val_true
        # --

    def enable(self, *flag_names):
        self._enable_or_disable(flag_names, True)

    def disable(self, *flag_names):
        self._enable_or_disable(flag_names, False)

    def read_str(self, string):
        if string:
            self._enable_or_disable(string.split(), True)

# --- end of BoolFlagDict ---
