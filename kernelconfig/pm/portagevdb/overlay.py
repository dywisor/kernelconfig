# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import errno
import os
import shutil

from ...abc import loggable
from ...util import fs
from ...util import fspath


__all__ = ["TemporaryOverlay"]


class AbstractTemporaryOverlayBase(loggable.AbstractLoggable):
    """
    @ivar root:
    @type root:  C{str}
    """

    # copy-paste inherit FsView

    @abc.abstractmethod
    def is_empty(self):
        """
        @return:  True if the overlay is empty, else False
        @rtype:   C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def add_package(self, package_info):
        """
        @param package_info:  package info object
        @type  package_info:  L{PackageInfo}

        @return:  True if package has been added, else False
        @rtype:   C{bool}
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def fs_init(self):
        """
        Creates the overlay (at its filesystem location).

        @return:  None (implicit)
        """
        raise NotImplementedError()

    def __init__(self, root, **kwargs):
        super().__init__(**kwargs)
        self.root = root

    def get_path(self):
        return self.root

    def get_filepath(self, *relpath_elements):
        return fspath.join_relpaths_v(self.root, relpath_elements)

# --- end of AbstractTemporaryOverlayBase (...) ---


class AbstractTemporaryOverlay(AbstractTemporaryOverlayBase):

    """
    @ivar name:         the temporary repo name, e.g. "kernelconfig_tmp_gentoo"
    @type name:         C{str}
    @ivar orig_name:    the original repo name, e.g. "gentoo"
    @type orig_name:    C{str}
    @ivar packages:     dict of all packages in this overlay
    @type packages:     C{dict} :: C{str} => L{PackageInfo}
    @ivar categories:   set of all categories
    @type categories:   C{set} of C{str}
    """

    def __init__(self, overlay_dir, orig_name, **kwargs):
        self.orig_name = orig_name
        self.name = "kernelconfig_tmp_{!s}".format(self.orig_name)
        self.packages = {}
        self.categories = set()

        kwargs.setdefault("logger_name", self.orig_name)
        super().__init__(overlay_dir, **kwargs)
    # --- end of __init__ (...) ---

    def is_empty(self):
        return bool(self.packages)

    def add_package(self, package_info):
        cpv = package_info.cpv
        if cpv in self.packages:
            raise KeyError("duplicate entry for package {}".format(cpv))

        self.categories.add(package_info.category)
        self.packages[cpv] = package_info
        self.logger.debug("packaged added: %s", package_info.cpv)
        return True
    # --- end of add_package (...) ---

    def iter_packages(self):
        return self.packages.values()
    # --- end of iter_packages (...) ---

# --- end of AbstractTemporaryOverlay ---


class TemporaryOverlay(AbstractTemporaryOverlay):

    def populate(self):
        # initially, try to symlink ebuilds,
        # and fall back to copying if symlinks are not supported
        copy_or_symlink = os.symlink
        copy_method_name = "symlink"

        for pkg_info in self.iter_packages():
            pkg_dir = self.get_filepath(
                fspath.join_relpath(pkg_info.category, pkg_info.name)
            )
            ebuild_dst = fspath.join_relpath(pkg_dir, pkg_info.ebuild_name)

            self.logger.debug(
                "Importing ebuild for %s as %s",
                pkg_info.cpv, copy_method_name
            )
            self.logger.debug("ebuild file: %s", pkg_info.ebuild_file)

            fs.dodir(pkg_dir)
            # unnecessary rmfile,
            #  except for running mkoverlays on the same dir again
            fs.rmfile(ebuild_dst)
            try:
                copy_or_symlink(pkg_info.ebuild_file, ebuild_dst)
            except OSError as oserr:
                if (
                    copy_or_symlink is os.symlink
                    and oserr.errno == errno.EPERM
                ):
                    self.logger.debug(
                        (
                            'symlinks seem to be unsupported by the fs,'
                            ' falling back to copying'
                        )
                    )
                    copy_or_symlink = shutil.copyfile
                    copy_method_name = "file"

                    self.logger.debug(
                        "Trying to import ebuild for %s as %s",
                        pkg_info.cpv, copy_method_name
                    )
                    copy_or_symlink(pkg_info.ebuild_file, ebuild_dst)  # raises
                else:
                    raise
        # -- end for
    # --- end of populate (...) ---

    def fs_init(self):
        self.logger.debug("Initializing overlay directory")
        try:
            self.fs_init_base()
            self.fs_init_profiles()
            self.fs_init_metadata()
            self.fs_init_eclass()

        except (OSError, IOError):
            self.logger.error("Failed to initialize overlay!")
            raise
    # --- end of fs_init (...) ---

    def fs_init_base(self):
        # reinit() or init(), i.e. mkdir with exists_ok=True or plain mkdir?
        fs.dodir(self.root)
    # ---

    def fs_init_profiles(self):
        profiles_dir = self.get_filepath("profiles")

        fs.dodir(profiles_dir)

        # "/repo_name"
        self.logger.debug("Creating profiles/repo_name")  # overly verbose
        with open(fspath.join_relpath(profiles_dir, "repo_name"), "wt") as fh:
            fh.write("{!s}\n".format(self.name))
        # --

        # "/categories"
        # dedup and sort categories
        self.logger.debug("Creating profiles/categories")  # overly verbose
        categories = sorted(self.categories)
        with open(fspath.join_relpath(profiles_dir, "categories"), "wt") as fh:
            if categories:
                fh.write("\n".join(categories))
            fh.write("\n")
        # --
    # --- end of fs_init_profiles (...) ---

    def fs_init_metadata(self):
        metadata_dir = self.get_filepath("metadata")

        fs.dodir(metadata_dir)

        # "/layout.conf"
        self.logger.debug("Creating metadata/layout.conf")  # overly verbose
        with open(
            fspath.join_relpath(metadata_dir, "layout.conf"), "wt"
        ) as fh:
            fh.write("repo_name = {!s}".format(self.name))
            fh.write("masters = {!s}\n".format(self.orig_name))
        # --
    # --- end of fs_init_metadata (...) ---

    def fs_init_eclass(self):
        self.logger.error("TODO: fs-init eclass")
    # --- end of fs_init_eclass (...) ---

# --- end of TemporaryOverlay ---


class TemporaryOverlayUnion(AbstractTemporaryOverlayBase):
    """
    @ivar overlays:
    @type overlays:  C{dict} :: C{str} => L{TemporaryOverlay}
    """

    def __init__(self, root, **kwargs):
        super().__init__(root, **kwargs)
        self.overlays = {}

    def iter_overlays(self):
        return self.overlays.values()

    def get_or_create_overlay(self, repo_name):
        try:
            ov = self.overlays[repo_name]
        except KeyError:
            ov = self.create_loggable(
                TemporaryOverlay,
                overlay_dir=self.get_filepath(repo_name), orig_name=repo_name
            )
            self.overlays[repo_name] = ov
        # --
        return ov
    # --- end of get_or_create_overlay (...) ---

    def is_empty(self):
        return self.overlays and any(
            (not ov.empty() for ov in self.iter_overlays())
        )

    def add_package(self, package_info):
        ov = self.get_or_create_overlay(package_info.repo_name)
        return ov.add_package(package_info)

    def populate(self):
        self.logger.debug("Populating overlays")
        for ov in self.iter_overlays():
            self.logger.debug("Populating overlay: %s", ov.orig_name)
            ov.populate()

    def fs_init(self):
        fs.dodir(self.root)
        for ov in self.iter_overlays():
            ov.fs_init()

# --- end of TemporaryOverlayUnion ---
