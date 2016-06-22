# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections

__all__ = ["FileInputQueue"]


class Empty(Exception):
    pass


class DuplicateItemKey(KeyError):
    pass


def _identity(item):
    return item


class FileInputQueue(object):
    """A data structure for organizing a number of input files in
    a queue with deduplication based on file path.

    @ivar _keyfunc:  key function
                      for input files, this should return filepaths
    @ivar _items:    dict :: key => item
                      for input files, keys should be filepaths as returned
                      by _keyfunc, and items can be arbitrary objects
                      (e.g. tuples containing filepath and additional metadata)

                      This dict contains both 'active' input files that have
                      yet to be processed and already processed files.
                      (IOW, everything that has ever been added via put().)

    @ivar _item_order:  a queue of 'active' input files
    """

    def __init__(self, *, key=None, **kwargs):
        """Constructor.

        Initializes an empty file input queue with the given key function.

        @keyword key:  key function :: item => key
                       Defaults to None, in which case items are used
                       as key (identity :: item => item)
        @type key:     C{None} or callable f :: comparable a => hashable b
        """
        super().__init__(**kwargs)
        self._keyfunc = (_identity if key is None else key)
        self._items = {}
        self._item_order = collections.deque()
    # --- end of __init__ (...) ---

    __hash__ = None

    def reset(self):
        """Empties the queue and removes all items."""
        self.clear()
        self._items.clear()

    def clear(self):
        """Empties the queue, but keeps all items."""
        self._item_order.clear()

    def empty(self):
        return not bool(self._item_order)

    def put(self, item):
        """Adds a file item to the queue if it has not been enqueued before.

        Otherwise, the file item must match exactly the existing one,
        and a DuplicateItemKey exception is raised if not.

        @param item:
        @return: True if item has been added, else False
        """
        item_key = self._keyfunc(item)

        if item_key not in self._items:
            self._items[item_key] = item
            self._item_order.append(item_key)
            return True

        elif item == self._items[item_key]:
            return False

        else:
            raise DuplicateItemKey(item_key, self._items[item_key], item)
    # --- end of put (...) ---

    def get(self):
        """Removes an item from the queue and returns it.

        @raises Empty:  if the queue is empty

        @return: file item
        """
        try:
            item_key = self._item_order.popleft()
        except IndexError:
            raise Empty from None

        # items do not get removed from the items dict
        return self._items[item_key]  # KeyError if broken data structure
    # --- end of get (...) ---

# --- end of FileInputQueue ---
