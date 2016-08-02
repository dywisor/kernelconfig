# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import portage


__all__ = ["PackageInfo"]


class PackageInfo(object):
    """
    Data object that holds enough information about a single package
    to add it to a temporary overlay and run its pkg_pretend()/pkg_setup()
    from there.

    No functionality is provided by this class, only the necessary variables.

    Instances of this class should be considered readonly,
    although that is not enforced in any way.

    @ivar cpv:          package cat-pkg-version
    @ivar category:     the package's category (from cpv)
    @ivar name:         the package's name (from cpv)
    @ivar repo_name:    the package's origin
    @ivar ebuild_file:  path to the package's ebuild (in vdb)
    """
    __slots__ = ["cpv", "category", "name", "repo_name", "ebuild_file"]

    __hash__ = None

    def __init__(self, cpv, repo_name, ebuild_file):
        super().__init__()
        self.cpv = None
        self.category = None
        self.name = None

        self.repo_name = repo_name
        self.ebuild_file = ebuild_file

        self._set_cpv(cpv)
    # --- end of __init__ (...) ---

    def __repr__(self):
        return "{cls.__name__}<{cpv}>".format(
            cls=self.__class__, cpv=self.cpv
        )

    def _set_cpv(self, cpv):
        splitv = portage.catpkgsplit(cpv)

        if splitv is None:
            # this is super unlikely since all cpvs processed by
            # kernelconfig originate from portage
            raise ValueError(cpv)
        # --

        self.cpv = cpv
        self.category = splitv[0]
        self.name = splitv[1]
    # --- end of _set_cpv (...) ---

# --- end of PackageInfo ---
