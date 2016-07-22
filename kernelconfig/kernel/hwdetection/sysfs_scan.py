# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import stat

from ...util import accudict

__all__ = ["scan_drivers", "scan_modalias"]


class _SysfsFind(object):

    SYSFS_PATH = "/sys"

    @classmethod
    def find(cls, names, typechecks, *, root=None):
        nameset = frozenset(names)

        for dirpath, dirnames, filenames in os.walk(
            (cls.SYSFS_PATH if root is None else root),
            followlinks=False
        ):
            fnames_matching = (
                nameset.intersection(filenames)
                | nameset.intersection(dirnames)
            )

            for fname in fnames_matching:
                fpath = os.path.join(dirpath, fname)
                stat_info = os.lstat(fpath)

                if any(
                    (typecheck(stat_info.st_mode) for typecheck in typechecks)
                ):
                    yield (fpath, stat_info)
            # -- end for fname
        # -- end for <<walk>>
    # --- end of find (...) ---

    @classmethod
    def find_symlinks(cls, *names, **kwargs):
        return cls.find(names, [stat.S_ISLNK], **kwargs)

    @classmethod
    def find_regular_files(cls, *names, **kwargs):
        return cls.find(names, [stat.S_ISREG], **kwargs)

    @classmethod
    def find_driver_symlinks(cls, *, root=None):
        if root is None:
            root = cls.SYSFS_PATH

        root_prefix_len = len(root) + 1

        for symlink_path, stat_info in cls.find_symlinks("driver", root=root):
            yield (
                symlink_path[root_prefix_len:],
                os.path.basename(os.readlink(symlink_path))
            )
    # --- end of find_driver_symlinks (...) ---

    @classmethod
    def scan_drivers(cls, **kwargs):
        """
        Scans /sys for "driver" symlinks and creates dict that maps
        driver names to a set of sysfs relpaths pointing to this driver.

        @keyword root:  alternative sysfs path. Defaults to None (-> /sys).
        @type    root:  C{None} or C{str}

        @return: dict of driver X relpaths
        @rtype:  dict :: C{str} => C{set} of C{str}
        """
        return accudict.SetAccumulatorDict(
            (
                (driver, symlink_relpath)
                for (symlink_relpath, driver)
                in cls.find_driver_symlinks(**kwargs)
            )
        ).to_dict()
    # --- end of scan_drivers (...) ---

    @classmethod
    def find_modalias_files(cls, *, root=None):
        if root is None:
            root = cls.SYSFS_PATH

        root_prefix_len = len(root) + 1

        for modalias_filepath, stat_info in (
            cls.find_regular_files("modalias", root=root)
        ):
            yield (
                modalias_filepath[root_prefix_len:],
                modalias_filepath
            )
    # --- end of find_modalias_files (...) ---

    @classmethod
    def _iter_scan_modalias(cls, **kwargs):
        for modalias_relpath, modalias_filepath in (
            cls.find_modalias_files(**kwargs)
        ):
            # not using fileio here, these files are really simple
            with open(modalias_filepath, "rt") as fh:
                for line in filter(None, (l.strip() for l in fh)):
                    yield (line, modalias_relpath)
    # --- end of _iter_scan_modalias (...) ---

    @classmethod
    def scan_modalias(cls, **kwargs):
        """
        Scans /sys for "modalias" files and creates a dict that maps
        module alias identifiers to a set of relative paths of sysfs files
        listing this identifier.

        @keyword root:  alternative sysfs path. Defaults to None (-> /sys).
        @type    root:  C{None} or C{str}

        @return: dict of modalias X relpaths
        @rtype:  dict :: C{str} => C{set} of C{str}
        """
        return accudict.SetAccumulatorDict(
            cls._iter_scan_modalias(**kwargs)
        ).to_dict()
    # --- end of scan_modalias (...) ---

# ---


# make select _SysfsFind methods available module-wide
scan_drivers = _SysfsFind.scan_drivers
scan_modalias = _SysfsFind.scan_modalias


if __name__ == "__main__":
    def main():
        import pprint

        print("== DRIVER ==")
        pprint.pprint(scan_drivers())
        print("== END OF DRIVER ==")

        print("\n== MODALIAS ==")
        pprint.pprint(scan_modalias())
        print("== END OF MODALIAS ==")
    # ---

    main()
# -- end if __main__
