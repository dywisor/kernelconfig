# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import shutil

from ...abc import informed
from ...util import fs


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

    @cvar LINUX_INFO_KV_HACK:  whether to override get_version() from
                               linux-info.eclass with a variant that
                               sets the KV_* vars from self.source_info
                               (determined at eclass modification time)
    @type LINUX_INFO_KV_HACK:  C{bool}

    @ivar _imported:  imported eclass files, src => first dst
    @type _imported:  C{dict} :: C{str} => C{str}
    """

    def __init__(self, **kwargs):
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
