# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import collections
import fnmatch
import glob
import os
import stat

from . import fspath

__all__ = ["MultiDirEntry", "MultiDirDequeEntry"]


class MultiDirEntryBase(object, metaclass=abc.ABCMeta):
    """
    Object that provides access to files that may appear
    in multiple directories.

    It support the following operations:

    * get_entry():         get multi dir entry for a file
                           (containing all possible paths)
    * get_file_paths():    get all possible paths to a file,
                           in the same order as the path list
    * get_file_path():     get path to file,
                           in the first directory it appears in
    * glob():              get all pattern matches, as entries
    * iglob():             get pattern matches as filepaths,
                           one filepath per matched name
    * iglob_check_type():  get "pattern and filetype" matches as filepaths,
                           one filepath per matched name
    * scandir():           combined dir contents, as name => entry dict
    * listdir():           combined dir contents, as name list

    A typical use case is looking up files
    in $HOME/.config/<name> and /etc/<name>,
    and either using both or preferring the file in $HOME.

    This is the base class for multi dir entries.
    It implements most the functionality,
    but leaves the type of the path list open (as long as it's list-like).

    @cvar PATH_LIST_TYPE: list type for the filesystem paths.
                          Sensible choices include C{list} and
                          C{collections.deque}, depending on how frequent
                          append-to-head operations occur.
                          Derived need to set this attribute
                          and implement _add_path_to_{head,tail}().

    @ivar paths:                    filesystem paths of this entry
    @ivar paths:                    C{list} of C{str}, or list-like
    @ivar _stat_cache:              stat_result cache for paths
    @ivar _stat_cache:              C{dict} :: C{str} => C{os.stat_result}
    @ivar _scandir_cache:           cache for subordinate entries
    @ivar _scandir_cache:           C{dict} :: C{str} => L{MultiDirEntry}
    @ivar _scandir_cache_complete:  bool that indicates whether _scandir_cache
                                    contains entries for the contents of
                                    all paths
    @ivar _scandir_cache_complete:  C{bool}
    """

    @abc.abstractproperty
    def PATH_LIST_TYPE(cls):
        raise NotImplementedError()

    @abc.abstractmethod
    def _add_path_to_head(self, path):
        """Adds 'path' to the head of the paths list."""
        raise NotImplementedError()

    @abc.abstractmethod
    def _add_path_to_tail(self, path):
        """Adds 'path' to the end of the paths list."""
        raise NotImplementedError()

    def __init__(self, pathv=None):
        super().__init__()
        self.paths = self.PATH_LIST_TYPE()
        self._stat_cache = {}
        self._scandir_cache = {}
        self._scandir_cache_complete = False

        if pathv:
            self.add_pathv(pathv)
    # --- end of __init__ (...) ---

    def copy(self):
        """Creates and returns a copy of this multi dir entry.

        The paths (but not the path list) will be shared between
        the original and the copy.
        """
        return self.__class__(pathv=self.paths)
    # --- end of copy (...) ---

    def __bool__(self):
        return bool(self.paths)
    # --- end of __bool__ (...) ---

    def __str__(self):
        # MultiDirEntry("a", "b", ...)
        return "{c.__name__}({pathlist})".format(
            c=self.__class__,
            pathlist=", ".join(("\"%s\"" % p for p in self.paths))
        )
    # --- end of __str__ (...) ---

    def __repr__(self):
        # MultiDirEntry(['a', 'b', ...])
        return "{c.__name__}({s.paths!r})".format(c=self.__class__, s=self)
    # --- end of __repr__ (...) ---

    def create_new_sub_entry(self):
        return self.__class__()

    def get_path(self):
        """Returns the 'most relevant' filesystem path of this entry.

        @raises StopIteration:  if this entry has no paths

        @return:  filesystem path
        @rtype:   C{str}
        """
        return next(iter(self.paths))
    # --- end of get_path (...) ---

    def normalize_filename(self, filename):
        """Normalizes a file name,
        which could also be a relative path containing "/".

        @param filename:  file name
        @type  filename:  C{str}

        @return:  normalized file name
        @rtype:   C{str}
        """
        return fspath.normalize_relpath(filename)
    # --- end of normalize_filename (...) ---

    def clear_cache(self):
        """Clears all caches."""
        self._stat_cache.clear()
        self._scandir_cache.clear()
        self._scandir_cache_complete = False
    # --- end of clear_cache (...) ---

    def _cache_invalidate_path(self, path_abs):
        """Invalidates cache entries for the given filesystem path.

        This method is meant to be used for paths that are in self.paths
        (or are about to be added to self.paths).

        @param path_abs:  filesystem path (absolute / normalized)
        @type  path_abs:  C{str}
        """
        self._stat_cache.pop(path_abs, None)
        self._scandir_cache.clear()
        self._scandir_cache_complete = False
    # --- end of _cache_invalidate_path (...) ---

    def do_stat(self, filepath):
        """A 'fault-tolerant' os.stat variant.

        @return: stat_result if successful, None on OSError
        """
        try:
            return os.stat(filepath)
        except OSError:
            return None
    # --- end of do_stat (...) ---

    def _add_path(
        self, path_abs, stat_info=None, check_new=False, to_end=True
    ):
        """Adds a filesystem path to self.paths,
        invalidates relevant cache entries.

        @param   path_abs:   filesystem path (absolute / normalized)
        @type    path_abs:   C{str}
        @keyword stat_info:  None or stat info for the path. Defaults to None.
        @type    stat_info:  C{None} or C{os.stat_result}
        @keyword check_new:  whether to check for duplicate filesystem paths
                             and not add the path in that case.
                             Defaults to False.
        @type    check_new:  C{bool}
        @keyword to_end:     whether to add the path to end of the path list
                             (True, giving it the lowest priority for
                             file lookups), or the start
                             (False, giving it the highest priority)
                             Defaults to True.
        @type    to_end:     C{bool}

        @return:  None (implicit)
        """
        if check_new and path_abs in self.paths:
            return

        self._cache_invalidate_path(path_abs)

        if to_end:
            self._add_path_to_tail(path_abs)
        else:
            self._add_path_to_head(path_abs)

        if stat_info is not None:
            self._stat_cache[path_abs] = stat_info
    # --- end of _add_path (...) ---

    def add_path(self, path, stat_info=None, check_new=False, to_end=True):
        """Similar to add_path(), but normalizes the path before adding it."""
        path_abs = os.path.abspath(path)
        self._add_path(
            path_abs, stat_info=stat_info, check_new=check_new, to_end=to_end
        )
    # --- end of add_path (...) ---

    def add_pathv(self, pathv, **kwargs):
        """add_path() variant that accepts a list of paths."""
        for path in pathv:
            self.add_path(path, **kwargs)
    # --- end of add_pathv (...) ---

    def add_paths(self, *pathv, **kwargs):
        """add_path() variant that accepts a var-args list of paths."""
        self.add_pathv(pathv, **kwargs)
    # --- end of add_paths (...) ---

    def iter_paths(self):
        """
        Generator that yields 2-tuples (path, path_stat_info)
        for all paths of this entry.

        path_stat_info may be None if os.stat() failed.
        """
        stat_cache = self._stat_cache

        for path in self.paths:
            try:
                stat_info = stat_cache[path]
            except KeyError:
                stat_info = self.do_stat(path)
                if stat_info is not None:
                    # not caching 'negative' results
                    stat_cache[path] = stat_info
            # -- end try

            yield (path, stat_info)
        # -- end for
    # --- end of iter_paths (...) ---

    def iter_paths_filter_stat_mode(self, filter_func):
        """Generator that yields 2-tuple (path, path_stat_info)
        for all paths of this entry whose stat mode is matched successfully
        by the given filter_func.

        Unlike iter_paths(), returns only paths with a not-None path_stat_info.
        """
        for path, stat_info in self.iter_paths():
            if stat_info is not None and filter_func(stat_info.st_mode):
                yield (path, stat_info)
    # --- end of iter_paths_filter_stat_mode (...) ---

    def iter_dir_paths(self):
        return self.iter_paths_filter_stat_mode(stat.S_ISDIR)
    # --- end of iter_dir_paths (...) ---

    def scandir_ref(self, refresh=False):
        """Returns the union of the dir contents of all paths.

        Vaguely similar to os.scandir() in Python >= 3.5,
        but returned entries are MultiDirEntry objects.

        @keyword refresh:  whether to force recreation of entries (True)
                           or try to reuse cached entries (False)
                           Defaults to False.
        @type    refresh:  C{bool}

        @return: shared dict that maps filenames to entries
                 Make sure to copy it before doing any modifications,
                 otherwise the scandir cache might get corrupted.
        @rtype:  C{dict} :: C{str} => L{MultiDirEntry}
        """

        if not refresh and self._scandir_cache_complete:
            return self._scandir_cache
        # --

        _osp_join = os.path.join

        entries = {}

        for path, _ in self.iter_dir_paths():
            try:
                fnames = os.listdir(path)
            except OSError:
                pass
            else:
                for fname in fnames:
                    try:
                        entry = entries[fname]
                    except KeyError:
                        entries[fname] = entry = self.create_new_sub_entry()

                    entry.add_path(_osp_join(path, fname))
        # -- end for path

        self._scandir_cache = entries
        self._scandir_cache_complete = True

        return entries
    # --- end of scandir_ref (...) ---

    def listdir(self, refresh=False):
        """Returns a list of all file names under any dir path of this entry,
        similar to os.listdir().

        @keyword refresh:  see scandir_ref()

        @return:  list of file names
        @rtype:   C{list} of C{str}
        """
        return sorted(self.scandir_ref(refresh=refresh))
    # --- end of listdir (...) ---

    def scandir(self, refresh=False):
        """
        Like scandir_ref(),
        but returns a copied dict that can be modified freely.
        Note that the MultiDirEntry objects are still ref-shared
        and should not be modified.
        """
        return self.scandir_ref(refresh=refresh).copy()
    # --- end of scandir (...) ---

    def scandir_flatten(self, refresh=False):
        """
        Like scandir_ref(), but the values of the returned dict
        are 2-tuples (path, stat info) of the 'most relevant' path.

        The returned dict is not shared with other instances
        and can be modified freely.
        """
        entries = self.scandir_ref(refresh=refresh)
        return {
            name: next(entry.iter_paths())
            for name, entry in entries.items()
            if entry
        }
    # --- end of scandir_flatten (...) ---

    def _glob_from_scandir_cache(self, norm_filename, glob_kw):
        """Tries to glob-expand norm_filename using the scandir cache.

        A cache hit can only be used if
        * the scandir cache is "complete"
        * the normalized filename is just a name
          and not a relative path containing "/"
        * the requested glob-expand mode is non-recursive,
          which means that either the "recursive" keyword
          is False or not present in glob_kw,
          or the requested filenamed does not contain "**"
          (Python >= 3.5 feature)

        Returns a dict of matching entries on success, and None otherwise.

        @param norm_filename:  normalized file name
        @type  norm_filename:  C{str}
        @param glob_kw:        keyword arguments that will be passed
                               to glob.glob()/glob.iglob()

        @return:  None or dict
        @rtype:   C{None} or C{dict} :: C{str} => L{MultiDirEntry}
        """
        if (
            self._scandir_cache_complete
            and fspath.is_name(norm_filename)
            and (
                not glob_kw.get("recursive") or "**" not in norm_filename
            )
        ):
            return {
                fname: entry
                for fname, entry in self.scandir_ref().items()
                if fnmatch.fnmatch(fname, norm_filename)
            }

        else:
            return None
    # --- end of _glob_from_scandir_cache (...) ---

    def _iglob_all_paths(self, norm_filename, glob_kw):
        """
        Generator that performs glob-expansion of the normalized file name
        for all paths, and yields 2-tuples
        (filepath relative to this entry, absolute filepath).

        The relative path is not unique,
        the same relpath may appear multile times.
        """
        _osp_join = os.path.join
        _osp_relpath = os.path.relpath

        for path, _ in self.iter_dir_paths():
            for filepath in glob.iglob(
                _osp_join(path, norm_filename), **glob_kw
            ):
                yield (_osp_relpath(filepath, path), filepath)
    # --- end of _iglob_all_paths (...) ---

    def glob(self, filename, **glob_kw):
        """Glob-expands the given filename pattern
        and returns a dict of matching entries.

        @param filename:  glob pattern
        @type  filename:  C{str}
        @param glob_kw:   additional keyword arguments for glob.iglob()

        @return:  dict that maps relpaths to entries
        @rtype:   dict :: C{str} => L{MultiDirEntry}
        """
        norm_filename = self.normalize_filename(filename)

        cached_entries = self._glob_from_scandir_cache(norm_filename, glob_kw)
        if cached_entries is not None:
            return cached_entries
        # --

        entries = {}
        for fname, filepath in self._iglob_all_paths(norm_filename, glob_kw):
            try:
                entry = entries[fname]
            except KeyError:
                entries[fname] = entry = self.create_new_sub_entry()

            entry.add_path(filepath)
        # -- end for

        return entries
    # --- end of glob (...) ---

    def iglob(self, filename, **glob_kw):
        """Generator glob() variant that returns the 'most-relevant'
        matching path only.

        @param   filename:         glob pattern
        @type    filename:         C{str}
        @param   glob_kw:          additional kw-args for glob.iglob()

        @return:  2-tuple (filepath relative to this entry, abs. filepath)
        @rtype:   2-tuple (C{str}, C{str})
        """
        norm_filename = self.normalize_filename(filename)

        cached_entries = self._glob_from_scandir_cache(norm_filename, glob_kw)
        if cached_entries is not None:
            for fname, entry in cached_entries.items():
                yield (fname, entry.get_path())
            # --
            return
        # -- end if cached

        relpaths_seen = set()
        for fname, filepath in self._iglob_all_paths(norm_filename, glob_kw):
            if fname not in relpaths_seen:
                yield (fname, filepath)
                relpaths_seen.add(fname)
        # -- end for
    # --- end of iglob (...) ---

    def _iglob_stat(self, filename, **glob_kw):
        norm_filename = self.normalize_filename(filename)

        relpaths_seen = set()

        cached_entries = self._glob_from_scandir_cache(norm_filename, glob_kw)
        if cached_entries is not None:
            for fname, entry in cached_entries.items():
                for filepath, stat_info in entry.iter_paths():
                    yield (relpaths_seen, fname, filepath, stat_info)
                    if fname in relpaths_seen:
                        break
                # --
            # --
            return
        # -- end if cached

        for fname, filepath in self._iglob_all_paths(norm_filename, glob_kw):
            if fname not in relpaths_seen:
                stat_info = self.do_stat(filepath)
                yield (relpaths_seen, fname, filepath, stat_info)
            # -- end if duplicate
        # -- end for
    # --- end of _iglob_stat (...) ---

    def iglob_stat(self, filename, **glob_kw):
        """
        @return:  3-tuple (
                     filepath relative to this entry, abs. filepath, stat info
                  )
        @rtype:   3-tuple (C{str}, C{str}, <<posix.stat_result>>)
        """
        for relpaths_seen, fname, filepath, stat_info in (
            self._iglob_stat(filename, **glob_kw)
        ):
            if stat_info is not None:
                yield (fname, filepath, stat_info)
                relpaths_seen.add(fname)
    # --- end of iglob_stat (...) ---

    def iglob_check_type(
        self, filename, check_file_type=stat.S_ISREG, **glob_kw
    ):
        """iglob() variant that filters results by file type.

        @param   filename:         glob pattern
        @type    filename:         C{str}
        @keyword check_file_type:  function for filtering matches,
                                   Defaults to "is file".
        @type    check_file_type:  callable c :: C{os.stat_result} => C{bool}
        @param   glob_kw:          additional kw-args for glob.iglob()

        @return:  2-tuple (filepath relative to this entry, abs. filepath)
        @rtype:   2-tuple (C{str}, C{str})
        """
        for relpaths_seen, fname, filepath, stat_info in (
            self._iglob_stat(filename, **glob_kw)
        ):
            if stat_info is not None and check_file_type(stat_info.st_mode):
                yield (fname, filepath)
                relpaths_seen.add(fname)
        # --
    # --- end of iglob_check_type (...) ---

    def _iget_all_paths(self, norm_filename):
        """Generator that yields 2-tuples (absolute filepath, stat info)
        for all files with the given name.

        Side-Note: the number of returned file paths is <= len(self.paths).

        @param norm_filename:  normalized filename
        @type  norm_filename:  C{str}

        @return:  2-tuple (absolute filepath, stat info)
        @rtype:   2-tuple (C{str}, C{os.stat_result})
        """
        _osp_join = os.path.join

        for path, _ in self.iter_dir_paths():
            filepath = _osp_join(path, norm_filename)
            stat_info = self.do_stat(filepath)
            if stat_info is not None:
                yield (filepath, stat_info)
    # --- end of _iget_all_paths (...) ---

    def get_entry(self, filename):
        """Returns a MultiDirEntry for the given file,
        containing all possible paths.

        Returns None if the file does not exist.

        @param filename:  file name
                          (interpreted relative to paths from self.paths)
        @type  filename:  C{str}

        @return:  multi dir entry or None
        @rtype:   L{MultiDirEntry} or C{None}
        """
        norm_filename = self.normalize_filename(filename)

        try:
            return self._scandir_cache[norm_filename]
        except KeyError:
            pass

        if not fspath.is_name(norm_filename):
            cacheable = False
        elif self._scandir_cache_complete:
            return None
        else:
            cacheable = True

        entry = self.create_new_sub_entry()
        for filepath, stat_info in self._iget_all_paths(norm_filename):
            entry.add_path(filepath, stat_info=stat_info)

        if cacheable:
            self._scandir_cache[norm_filename] = entry

        return entry if entry.paths else None
    # --- end of get_entry (...) ---

    def get_file_paths(self, filename, check_file_type=stat.S_ISREG):
        """Returns a list of all possible paths for the given file,
        and filters out paths that do not have the request file type.

        The list is empty if no path candidates exist.

        @param filename:           file name (interpreted relative to paths
                                   from self.paths)
        @type    filename:         C{str}
        @keyword check_file_type:  function for filtering matches,
                                   Defaults to "is file".
        @type    check_file_type:  callable c :: C{os.stat_result} => C{bool}

        @return:  list of filesystem paths, possibly empty
        @rtype:   C{list} of C{str}
        """
        entry = self.get_entry(filename)
        if entry is None:
            return []
        else:
            return [
                path for path, stat_info
                in entry.iter_paths_filter_stat_mode(check_file_type)
            ]
    # --- end of get_file_paths (...) ---

    def get_file_path(self, filename, check_file_type=stat.S_ISREG):
        """
        Returns the first-matching path for the given file
        or None if no path candidate exists.

        Otherwise, identical to get_file_paths(),
        but a bit more optimized for the "return first-match" case.

        @return:  filesystem path or None
        @rtype:   C{str} or C{None}
        """
        norm_filename = self.normalize_filename(filename)

        try:
            entry = self._scandir_cache[norm_filename]
        except KeyError:
            pass
        else:
            for path, _ in entry.iter_paths_filter_stat_mode(check_file_type):
                return path
            return None
        # --

        if self._scandir_cache_complete and fspath.is_name(norm_filename):
            return None

        for filepath, stat_info in self._iget_all_paths(norm_filename):
            if check_file_type(stat_info.st_mode):
                return filepath
        # --

        return None
    # --- end of get_file_path (...) ---

    def get_child(self, filename, check_exist=False):
        if check_exist:
            entry = self.get_entry(filename)
            return entry.copy() if entry else None

        else:
            entry = self.create_new_sub_entry()
            norm_filename = self.normalize_filename(filename)
            entry.add_pathv(
                (os.path.join(path, norm_filename) for path in self.paths)
            )
            return entry
    # --- end of get_child (...) ---

# --- end of MultiDirEntryBase ---


class MultiDirEntry(MultiDirEntryBase):
    """Multi dir entry that uses a list for storing its paths."""
    PATH_LIST_TYPE = list

    def _add_path_to_head(self, path):
        self.paths[:0] = [path]
    # --- end of _add_path_to_head (...) ---

    def _add_path_to_tail(self, path):
        self.paths.append(path)
    # --- end of _add_path_to_tail (...) ---

# --- end of MultiDirEntry ---


class MultiDirDequeEntry(MultiDirEntryBase):
    """Multi dir entry that uses a deque for storing its paths.

    Sub entries use a normal list.
    """
    PATH_LIST_TYPE = collections.deque

    def create_new_sub_entry(self):
        return MultiDirEntry()

    def _add_path_to_head(self, path):
        self.paths.appendleft(path)

    def _add_path_to_tail(self, path):
        self.paths.append(path)

# --- end of MultiDirDequeEntry ---
