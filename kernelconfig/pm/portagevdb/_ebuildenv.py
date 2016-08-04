# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os.path

from ...abc import informed
from ...util import makeargs
from ...util import osmisc
from ...util import subproc

from . import _globals


__all__ = ["ConfigCheckEbuildEnv"]


class EbuildEnvError(RuntimeError):
    pass


class EbuildEnvSetupError(EbuildEnvError):
    pass


class EbuildEnvSetupMissingProgramError(EbuildEnvSetupError):
    pass


class EbuildEnvRunError(EbuildEnvError):
    pass


class EbuildEnv(informed.AbstractInformed):

    def __init__(self, tmpdir, **kwargs):
        super().__init__(**kwargs)
        self._tmpdir = tmpdir
        self.portage_tmpdir = None
        self.kbuild_output = None
        self.ebuild_prog = None
        self.sysnop_prog = None
        self.env = None

    def _find_prog(self, name):
        prog = osmisc.which(name)
        if not prog:
            raise EbuildEnvSetupMissingProgramError(name)
        return prog
    # ---

    def _get_kbuild_output_dir(self):
        if not self.source_info.check_supports_out_of_tree_build():
            self.logger.warning(
                'Sources being processed do not support out-of-tree building'
                ', this most likely means that they are not kernel sources'
                ', but pm-integration does not support anything else'
            )
            raise AssertionError(
                "not a kernel srctree", self.source_info.get_path()
            )
        # --

        kbuild_output = self._tmpdir.dodir("kbuild")

        # build up the make command for creating kbuild_output
        #  (which creates the wrapper Makefile and other files)
        #
        #  If the configuration is already available, it could be used as
        #  .config in this directory, but for now, use "defconfig" as target.
        #
        mk_cmdv = makeargs.MakeArgs(
            ["make", "-C", self.source_info.get_path()]
        )

        #  source-info related vars (ARCH=...)
        mk_cmdv.addv(self.source_info.iter_make_vars())

        #  source-info out-of-tree build related vars (O=...)
        mk_cmdv.addv(
            self.source_info.iter_out_of_tree_build_make_vars(kbuild_output)
        )

        # the make target
        #   "kernelversion" or similar would probably also work when using
        #   using the configuration basis as .config
        #
        mk_cmdv.append("defconfig")

        self.logger.debug("Creating KBUILD_OUTPUT: %s", kbuild_output)
        with subproc.SubProc(mk_cmdv, quiet=True, logger=self.logger) as proc:
            if not proc.join():
                self.logger.warning("Failed to create KBUILD_OUTPUT")
                return None
        # --

        self.logger.debug("Created KBUILD_OUTPUT")
        return kbuild_output
    # --- end of _get_kbuild_output_dir (...) ---

    def setup(self, port_iface):
        if self.ebuild_prog is None:
            self.ebuild_prog = self._find_prog("ebuild")

        if self.sysnop_prog is None:
            self.sysnop_prog = self._find_prog("true")

        if self.portage_tmpdir is None:
            self.portage_tmpdir = self._tmpdir.get_new_subdir()

        env = self.env
        if env is None:
            env = {}

            # noauto -cgroup -distlocks -skiprocheck -ebuild-locks notitles
            env["FEATURES"] = "-distlocks -skiprocheck notitles"

            # DISTDIR
            # PORTAGE_RO_DISTDIR

            env["EPAUSE_IGNORE"] = "Y"

            null_fetch_cmd_str = "{} ${{FILE}}".format(self.sysnop_prog)
            env["FETCHCOMMAND"] = null_fetch_cmd_str
            env["RESUMECOMMAND"] = null_fetch_cmd_str

            # explicitly documented as "Overwritable environment Var"
            # in linux-info.eclass: KERNEL_DIR
            env["KERNEL_DIR"] = self.source_info.get_path()
            assert env["KERNEL_DIR"]

            # do not leak KV_FULL from os.environ,
            # it is used to determine whether various KV_* vars are set.
            env["KV_FULL"] = None

            self.env = env
        # --

        if self.kbuild_output is None:
            kbuild_output = self._get_kbuild_output_dir()
            if not kbuild_output:
                raise EbuildEnvSetupError("KBUILD_OUTPUT")

            self.kbuild_output = kbuild_output
            env["KBUILD_OUTPUT"] = kbuild_output
        # --

        env["PORTAGE_TMPDIR"] = self.portage_tmpdir.get_path()
    # --- end of setup (...) ---

    def get_ebuild_subproc(self, package_info):
        """
        @return:  subprocess (not started)
        @rtype:   L{subproc.SubProc}
        """
        pkg_dir = os.path.dirname(package_info.tmp_ebuild_file)
        return subproc.SubProc(
            [
                self.ebuild_prog, "--skip-manifest",
                package_info.tmp_ebuild_file
            ],
            extra_env=self.env,
            cwd=pkg_dir,
            tmpdir=self.portage_tmpdir,
            logger=self.logger
        )
    # --- end of get_ebuild_subproc (...) ---

# --- end of EbuildEnv ---


class ConfigCheckEbuildEnv(EbuildEnv):

    def run_ebuild_get_config_check_outfile(self, package_info):
        # this is highly specific / relying in portage internals, FIXME
        pkg_tmpdir = self.portage_tmpdir.get_filepath(
            "tmp/portage/tmp/portage/{cpv!s}/temp".format(cpv=package_info.cpv)
        )
        outfile = _globals.get_vars().get_config_check_tmpfile_path(pkg_tmpdir)

        proc = self.get_ebuild_subproc(package_info)

#        # if "noauto" in FEATURES
#
#        # run pkg_pretend() first and see if that is sufficient
#        #  packages that call check_extra_config() in both pkg_pretend()
#        #  and pkg_setup() get ignored this way,
#        #  but calling pkg_pretend() only is safer
#        proc.cmdv.append("pretend")
#        with proc:
#            proc_status = proc.join()
#
#        if not proc_status:
#            # ebuild failed in pkg_pretend()
#            if os.path.isfile(outfile):
#                # recover
#                pass
#
#            raise EbuildEnvRunError()  # TODO
#
#        elif os.path.isfile(outfile):
#            # TODO log
#            return outfile

        # run pkg_setup()
#        proc.zap()
#        proc.cmdv.pop()
        proc.cmdv.append("setup")

        with proc:
            proc_status = proc.join()

        if not proc_status:
            # log about it
            # -- bug #217042 maybe?
            #  log
            if os.path.isfile(outfile):
                # recover
                pass

            raise EbuildEnvRunError()  # TODO
        # --

        return (outfile if os.path.isfile(outfile) else None)
    # --- end of run_ebuild_get_config_check_outfile (...) ---

    def _read_config_check_outfile(self, filepath):
        with open(filepath, "rt") as fh:
            config_check_str = fh.read()

        return config_check_str.split()
    # --- end of _read_config_check_outfile (...) ---

    def eval_config_check(self, package_info):
        outfile = self.run_ebuild_get_config_check_outfile(package_info)
        if outfile:
            return self._read_config_check_outfile(outfile)
        else:
            return None

        raise NotImplementedError("read outfile", outfile)
    # --- end of eval_config_check (...) ---

# --- end of ConfigCheckEbuildEnv ---
