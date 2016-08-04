# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import shutil

from ...abc import informed
from ...util import fs
from ...util import osmisc

from . import _globals


__all__ = ["EclassImporter"]


class EclassImporter(informed.AbstractSourceInformed):
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

    @cvar LINUX_INFO_HACKS:     whether to allow non-essential modifications
                                to linux-info.eclass.
                                Some provide better CONFIG_CHECK results,
                                while others increase performance.

                                Defaults to True, and can be disabled
                                by setting the environment variable
                                KERNELCONFIG_PORTAGE_LINUX_INFO_HACKS
                                to the empty string.
    @type LINUX_INFO_HACKS:     C{bool}

    @cvar LINUX_INFO_HACKS_KV:  whether to override get_version() from
                                linux-info.eclass with a variant that
                                sets the KV_* vars from self.source_info
                                (determined at eclass modification time)

                                The instance behavior is controlled
                                by the linux_info_hacks_kv variable,
                                LINUX_INFO_HACKS_KV simply controls whether
                                it is allowed to enable it automatically.

                                Disabled if LINUX_INFO_HACKS is disabled.
                                Otherwise, defaults True and can be disabled
                                by setting the environment variable
                                KERNELCONFIG_PORTAGE_LINUX_INFO_HACKS_KV
                                to the empty string.
    @type LINUX_INFO_HACKS_KV:  C{bool}

    @ivar linux_info_hacks_kv:  see LINUX_INFO_HACKS_KV
                                Defaults to None, which enables the "kv hack"
                                IFF LINUX_INFO_HACKS_KV is set to True
                                and a source info object is present.
    @type linux_info_hacks_kv:  C{bool}

    @ivar _imported:  imported eclass files, src => first dst
    @type _imported:  C{dict} :: C{str} => C{str}
    """

    LINUX_INFO_HACKS = osmisc.envbool_nonempty(
        "KERNELCONFIG_PORTAGE_LINUX_INFO_HACKS", True
    )

    LINUX_INFO_HACKS_KV = (
        LINUX_INFO_HACKS
        and osmisc.envbool_nonempty(
            "KERNELCONFIG_PORTAGE_LINUX_INFO_HACKS_KV", True
        )
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._imported = {}
        self._linux_info_hacks_kv = None

    @property
    def linux_info_hacks_kv(self):
        linux_info_hacks_kv = self._linux_info_hacks_kv
        if linux_info_hacks_kv is None:
            if self.LINUX_INFO_HACKS_KV:
                linux_info_hacks_kv = bool(self.source_info is not None)
            else:
                linux_info_hacks_kv = False
            # --

            self._linux_info_hacks_kv = linux_info_hacks_kv
        # --
        return linux_info_hacks_kv
    # --- end of property linux_info_hacks_kv (...) ---

    @linux_info_hacks_kv.setter
    def _set_linux_info_hacks_kv(self, value):
        if not value:
            self._linux_info_hacks_kv = False

        elif self.source_info is not None:
            self._linux_info_hacks_kv = True

        else:
            raise ValueError(value)
    # --- end of _set_linux_info_hacks_kv (...) ---

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
        self.logger.debug(
            "Overriding check_extra_config() in linux-info.eclass"
        )
        config_check_tmpfile = (
            _globals.get_vars().get_config_check_tmpfile_path("${T}")
        )
        yield "unset -f check_extra_config"
        yield "check_extra_config() {"
        yield "\tprintf '%s\\n' \"${{CONFIG_CHECK}}\" >> \"{}\"".format(
            config_check_tmpfile
        )
        yield "}"

        # To improve the performance further,
        # skip repeated makefile kernelversion parsing
        # by overriding get_version().
        #
        # This is, of course, quite hacky,
        # but reduces ebuild processing time considerably.
        #
        # The override versions sets all global variables that
        # the original function would.
        #
        # KV_LOCAL remains empty.
        #
        # Note:
        #  KV_MAJOR is VERSION
        #  KV_MINOR is PATCHLEVEL    !
        #  KV_PATCH is SUBLEVEL      !
        #  KV_EXTRA is EXTRAVERSION
        #
        if self.linux_info_hacks_kv:
            self.logger.debug("Overriding get_version() in linux-info.eclass")

            source_info = self.source_info
            # assert source_info is not None
            kver = source_info.kernelversion

            yield ""
            yield "unset -f get_version"
            yield "get_version() {"
            for varname, value in [
                ("KV_DIR", "${KERNEL_DIR:?kernelconfig bug}"),
                ("KV_DIR_OUT", "${KBUILD_OUTPUT:?kernelconfig bug}"),
                (
                    "KERNEL_MAKEFILE",
                    "${KERNEL_DIR:?kernelconfig bug}/Makefile"
                ),
                ("KV_FULL", kver),
                ("KV_MAJOR", kver.version or 0),
                ("KV_MINOR", kver.patchlevel or 0),
                ("KV_PATCH", kver.sublevel or 0),
                ("KV_EXTRA", kver.extraversion or ""),
                ("KV_LOCAL", ""),
            ]:
                yield "\t{0!s}=\"{1!s}\"".format(varname, value)
            # implicit return
            yield "}"
        # -- end if kv_hack
    # --- end of gen_linux_info_modification_lines (...) ---

# --- end of EclassImporter ---
