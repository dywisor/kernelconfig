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


class EclassImporter(loggable.AbstractLoggable):
    """
    Each temporary has its own dir with copied and modified eclass files,
    but in case of "linux-info.eclass" this likely results in modifying
    the same file more than once.

    To avoid redundant eclass file editing, this class provides caching.

    Based on the assumption that the eclass files do not get modified after
    importing, the importer returns the path of the already imported eclass
    when requested to import the same file again.

    To substantiate the assumption, this class takes also care of the
    modifying the eclass files (i.e. "linux-info").

    @ivar _imported:  imported eclass files, src => first dst
    @type _imported:  C{dict} :: C{str} => C{str}
    """

    def __init__(self, *undef_args, **kwargs):
        super().__init__(**kwargs)
        self._imported = {}

    def _reimport_eclass_file(self, src, dst):
        """
        @return:  True if imported from cache, else False
        @rtype:   C{bool}
        """
        try:
            imported_dst = self._imported[src]
        except KeyError:
            self.logger.debug("eclass has not been imported yet: %s", src)
            return False
        # --

        self.logger.debug("eclass has already been imported: %s", src)
        # hardlink, copy, symlink?
        shutil.copyfile(imported_dst, dst)
        return True
    # --- end of _reimport_eclass_file (...) ---

    def _register_new_import(self, src, dst):
        self._imported[src] = dst
    # --- end of _register_import (...) ---

    def import_linux_info(self, src, dst):
        if self._reimport_eclass_file(src, dst):
            return

        # there may be leftover files if a previous import did not succeed
        fs.rmfile(dst)

        # copy and modify the eclass
        with open(dst, "wt") as out_fh:
            # copy first
            with open(src, "rt") as in_fh:
                out_fh.write(in_fh.read())
            # --

            # then, the modifications
            out_fh.write("\n\n# KERNELCONFIG MODIFICATIONS START HERE\n\n")
            out_fh.write("\n".join(self.gen_linux_info_modification_lines()))
            out_fh.write("\n")
        # --

        # done
        self._register_new_import(src, dst)
    # --- end of import_linux_info (...) ---

    def gen_linux_info_modification_lines(self):
        """
        @return: text line(s)
        @rtype:  C{str}  (genexpr)
        """
        # COULDFIX: get from install_info --> data file,

        # override check_extra_config()
        #
        #  This function receives the value of CONFIG_CHECK as var,
        #  and checks it against the kernel config.
        #
        #  The modified version simply appends the value of CONFIG_CHECK
        #  to a temporary file and returns 0.
        #
        #  This is the most reliable code point at which CONFIG_CHECK
        #  can be diverted from its intended use:
        #
        #  * the original check_extra_config() would die
        #    if a config option is not prefixed with "~" ('optional')
        #    Such cases are unlikely, but there is really no point in
        #    dying because of missing config options when creating a config.
        #
        #    (Logically, only packages that have been successfully built
        #    in the past are processed by this module, and therefore it's
        #    quite likely that the "mandatory config option" checks would
        #    succeed, but it still doesn't make much sense to allow die()
        #    because of missing config options.)
        #
        #  * the value of CONFIG_CHECK does not have to be retrieved
        #    from log files or wheresoever,
        #    it is written to a temporary file,
        #    and subsequent check_extra_config() calls append to that file
        #
        #  * instead of having to edit every ebuild,
        #    only the eclass is modified
        #
        #  Efficiency-wise, the result of the CONFIG_CHECK comparison is
        #  not of interest to kernelconfig, since kernelconfig simply
        #  {,tries to} enable(s) the options instead,
        #  and overriding check_extra_config() skips the reading of .config
        #  (which would be read multiple times per ebuild!).
        #
        yield "unset -f check_extra_config"
        yield "check_extra_config() {"
        yield (
            "\tprintf '%s\\n' \"${CONFIG_CHECK}\""
            " >> \"${T}/kernelconfig_config_check\""
        )
        yield "}"

        # TODO: To improve the performance further,
        # it would be possible to skip repeated makefile kernelversion parsing
        # by overriding linux-info_get_any_version().
        #
        # It is being considered, but not essential for initial testing.
        #
    # --- end of gen_linux_info_modification_lines (...) ---

# --- end of EclassImporter ---


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
    def fs_init(self, **kwargs):
        """
        Creates the overlay (at its filesystem location).

        @param kwargs:  undefined

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

    @abc.abstractmethod
    def assign_repo_config(self, port_iface, fallback_repo_config=True):
        raise NotImplementedError()

    def get_fallback_repo_config(self, port_iface):
        # If the original repo of one of the overlay repos can not be found,
        # the main repo is used as fallback.
        #
        # Usually, this is "gentoo", but it can be overridden via os.environ.
        # Setting the env var to an empty str disables the fallback behavior.
        #
        # FIXME: DOC: special env var KERNELCONFIG_PORTAGE_MAIN_REPO
        #
        main_repo_name = os.environ.get(
            "KERNELCONFIG_PORTAGE_MAIN_REPO", "gentoo"
        )

        if not main_repo_name:
            self.logger.debug("main repo fallback has been disabled via env")
            return None
        else:
            try:
                main_repo_config = port_iface.get_repo_config(main_repo_name)
            except KeyError:
                self.logger.warning(
                    "Main repo fallback is unavailable, repo %s not found.",
                    main_repo_name
                )
                return None
            else:
                self.logger.debug(
                    "Using main repo '%s' as fallback", main_repo_config.name
                )
                return main_repo_config
        # --
    # --- end of get_fallback_repo_config (...) ---

# --- end of AbstractTemporaryOverlayBase (...) ---


class AbstractTemporaryOverlay(AbstractTemporaryOverlayBase):

    """
    @ivar tmp_name:     the temporary repo name, e.g. "kernelconfig_tmp_gentoo"
    @type tmp_name:     C{str}
    @ivar name:         the original repo name, e.g. "gentoo"
    @type name:         C{str}
    @ivar masters:      either None or a list of "master" repo names
    @ŧype masters:      C{None} or C{list} of C{str}
    @ivar packages:     dict of all packages in this overlay
    @type packages:     C{dict} :: C{str} => L{PackageInfo}
    @ivar categories:   set of all categories
    @type categories:   C{set} of C{str}
    """

    def __init__(self, overlay_dir, name, **kwargs):
        self.name = name
        self.tmp_name = "kernelconfig_tmp_{!s}".format(self.name)
        self.masters = None
        self.packages = {}
        self.categories = set()

        kwargs.setdefault("logger_name", self.name)
        super().__init__(overlay_dir, **kwargs)
    # --- end of __init__ (...) ---

    def get_masters_str(self):
        return (
            " ".join(self.masters) if self.masters is not None
            else self.name
        )
    # --- end of get_masters_str (...) ---

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


class _TemporaryOverlay(AbstractTemporaryOverlay):

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

    def fs_init(self, eclass_importer=None):
        self.logger.debug("Initializing overlay directory")
        try:
            self.fs_init_base()
            self.fs_init_profiles()
            self.fs_init_metadata()
            self.fs_init_eclass(eclass_importer=eclass_importer)

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
            fh.write("{!s}\n".format(self.tmp_name))
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
            fh.write("repo_name = {!s}".format(self.tmp_name))
            # trailing whitespace in absence of "masters": don't care
            fh.write("masters = {!s}\n".format(self.get_masters_str()))
        # --
    # --- end of fs_init_metadata (...) ---

    @abc.abstractmethod
    def fs_init_eclass(self, eclass_importer):
        raise NotImplementedError()
    # --- end of fs_init_eclass (...) ---

# --- end of _TemporaryOverlay ---


class TemporaryOverlay(_TemporaryOverlay):
    """
    @ivar linux_info_eclass_src:  path to the linux-info eclass file
                                  in the original repo
                                  (or in one of its master repos)
    @type linux_info_eclass_src:  C{str}  (initially C{None}
    """

    def __init__(self, overlay_dir, name, **kwargs):
        super().__init__(overlay_dir, name, **kwargs)
        self.linux_info_eclass_src = None
    # --- end of __init__ (...) ---

    def assign_repo_config(self, port_iface, fallback_repo_config=True):
        if fallback_repo_config is True:
            fallback_repo_config = self.get_fallback_repo_config(port_iface)

        try:
            repo_config = port_iface.get_repo_config(self.name)
        except KeyError:
            self.logger.warning("Repo config for '%s' not found", self.name)

            if not fallback_repo_config:  # None, False
                raise

            # use the fallback repo config,
            # rewrite masters to reflect this change
            self.logger.warning(
                "Using main repo '%s' as fallback", fallback_repo_config.name
            )
            repo_config = fallback_repo_config
            self.masters = [repo_config.name]
        else:
            self.logger.debug("Found repo config for '%s'", repo_config.name)
        # --

        eclasses = repo_config.eclass_db.eclasses
        try:
            linux_info_eclass_src_info = eclasses["linux-info"]

        except KeyError:
            # eclass not found
            #  That means, eclass not found in the original overlay
            #  nor in one of its master repos ([possibly] including "gentoo").
            #
            #  This strongly contradicts the fact that only packages
            #  that have been successfully built in the past
            #  and whose ebuild inherits linux-info.eclass
            #  are added to *this* overlay.
            #
            #  So, basically linux-info was present at pkg build time,
            #  but cannot be found now.
            #
            self.logger.error(
                "linux-info.eclass not found - pm-integration cannot operate!"
            )
            raise  # FIXME: raise a more specific exception

        else:
            self.linux_info_eclass_src = linux_info_eclass_src_info.location
    # --- end of assign_repo_config (...) ---

    def fs_init_eclass(self, eclass_importer):
        eclass_dir = self.get_filepath("eclass")

        fs.dodir(eclass_dir)

        if not self.linux_info_eclass_src:
            raise AssertionError("linux-info.eclass src is not set.")

        linux_info_eclass_dst = fspath.join_relpath(
            eclass_dir,
            os.path.basename(self.linux_info_eclass_src)  # "linux-info.eclass"
        )

        eclass_importer.import_linux_info(
            self.linux_info_eclass_src, linux_info_eclass_dst
        )
    # --- end of fs_init_eclass (...) ---

# --- end of TemporaryOverlay ---


class TemporaryOverlayUnion(AbstractTemporaryOverlayBase):
    """
    @ivar overlays:
    @type overlays:  C{dict} :: C{str} => L{TemporaryOverlay}
    """

    def setup(self, port_iface, fallback_repo_config=True):
        self.assign_repo_config(port_iface, fallback_repo_config)
        self.fs_init()
        self.populate()
    # --- end of setup (...) ---

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
                overlay_dir=self.get_filepath(repo_name), name=repo_name
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
            self.logger.debug("Populating overlay: %s", ov.name)
            ov.populate()

    def assign_repo_config(self, port_iface, fallback_repo_config=True):
        if fallback_repo_config is True:
            fallback_repo_config = self.get_fallback_repo_config(port_iface)

        for ov in self.iter_overlays():
            ov.assign_repo_config(port_iface, fallback_repo_config)
    # --- end of assign_repo_config (...) ---

    def fs_init(self):
        eclass_importer = self.create_loggable(EclassImporter)

        fs.dodir(self.root)
        for ov in self.iter_overlays():
            ov.fs_init(eclass_importer=eclass_importer)

# --- end of TemporaryOverlayUnion ---
