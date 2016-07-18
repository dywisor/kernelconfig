# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections


__all__ = ["SetAccumulatorDict", "ListAccumulatorDict"]


class AccumulatorDict(collections.UserDict):
    # dict :: key -> (container of object)
    CONTAINER_TYPE = None

    def add_to_entry(self, entry, item):
        raise NotImplementedError()

    def addv_to_entry(self, entry, items):
        for item in items:
            self.add_to_entry(entry, item)

    def get_or_create_entry(self, key):
        try:
            return self.data[key]
        except KeyError:
            entry = self.CONTAINER_TYPE()
            self.data[key] = entry
            return entry
    # ---

    def add(self, key, item):
        entry = self.get_or_create_entry(key)
        self.add_to_entry(entry, item)
        return entry

    def addv(self, key, items):
        entry = self.get_or_create_entry(key)
        self.addv_to_entry(entry, items)
        return entry

    # __setitem__ = add

    def __init__(self, data=None, **kwargs):
        super().__init__()
        self.update(data, **kwargs)
    # ---

    def update(self, data=None, **kwargs):
        if not data:
            pass
        elif hasattr(data, "keys"):
            for key in data:
                self.add(key, data[key])
        else:
            for key, value in data:
                self.add(key, value)

        for key in kwargs:
            self.add(key, kwargs[key])
    # ---

    def gen_reverse(self):
        # { a => {X, Y}, b => {Y, Z} } ==> { X => {a}, Y => {a, b}, Z => {b} }
        return (
            (value, key)
            for key, values in self.items()
            for value in values
        )

    def reverse_mapping(self):
        return self.__class__(data=self.gen_reverse())
    # ---

# ---


class SetAccumulatorDict(AccumulatorDict):
    # dict :: key -> set
    CONTAINER_TYPE = set

    def add_to_entry(self, entry, item):
        entry.add(item)

    def addv_to_entry(self, entry, items):
        entry.update(items)

# --- end of SetAccumulatorDict ---


class ListAccumulatorDict(AccumulatorDict):
    # dict :: key -> list
    CONTAINER_TYPE = list

    def add_to_entry(self, entry, item):
        entry.append(item)

    def addv_to_entry(self, entry, items):
        entry.extend(items)

    # def gen_reverse():  random order of values
    # { a => {X, Y}, b => {Y, Z} }
    #    (1) ==> { X => [a], Y => [a, b], Z => [b] }
    # or (2) ==> { X => [a], Y => [b, a], Z => [b] }

# --- end of ListAccumulatorDict ---


class DictAccumulatorDict(AccumulatorDict):
    # dict :: key -> (dict :: subkey -> set)
    CONTAINER_TYPE = SetAccumulatorDict

    def add_to_entry(self, entry, item):
        entry.add(item[0], item[1])

    def gen_reverse(self):
        # a -> (b -> c)  ==>  b -> (a -> c)
        return (
            (value, (key, sub_value))
            for key, value_map in self.items()
            for value, sub_values in value_map.items()
            for sub_value in sub_values
        )
# --- end of DictAccumulatorDict ---
