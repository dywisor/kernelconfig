# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import stat

from ...util import accudict

__all__ = ["scan_drivers"]


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
        Scans /sys for drivers symlinks and creates dict that maps
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

# ---


# make select _SysfsFind methods available module-wide
scan_drivers = _SysfsFind.scan_drivers


if __name__ == "__main__":
    def main():
        import pprint
        pprint.pprint(scan_drivers())
    # ---

    main()
# -- end if __main__
