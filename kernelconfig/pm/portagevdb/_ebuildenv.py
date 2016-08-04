# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os.path

from ...abc import informed
from ...util import fspath
from ...util import osmisc
from ...util import subproc


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
        self.ebuild_prog = None
        self.sysnop_prog = None
        self.env = None

    def _find_prog(self, name):
        prog = osmisc.which(name)
        if not prog:
            raise EbuildEnvSetupMissingProgramError(name)
        return prog
    # ---

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

            self.env = env
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
        outfile = fspath.join_relpath(pkg_tmpdir, "kernelconfig_config_check")

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
