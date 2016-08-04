# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import subprocess

from ...abc import informed
from ...util import makeargs
from ...util import osmisc
from ...util import subproc
from ...util import usedict

from . import _globals
from . import util


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

            # adjust FEATURES a bit
            features = (
                usedict.BoolFlagDict.new_from_str(
                    os.environ.get("FEATURES")
                )
            )

            # disable downloading of files listed SRC_URI
            #    vcs-fetching (git/subversion/... eclass) takes place in
            #    src_unpack(), and config-check re-eval won't get that far
            #
            null_fetch_cmd_str = "{} ${{FILE}}".format(self.sysnop_prog)
            env["FETCHCOMMAND"] = null_fetch_cmd_str
            env["RESUMECOMMAND"] = null_fetch_cmd_str

            # DISTDIR
            # PORTAGE_RO_DISTDIR
            # -- remain unchanged

            # DISTDIR should be considered readonly here,
            # FETCHCOMMAND, RESUMECOMMAND are set to /bin/true.
            #
            # Disables distlocks and the readonly-check.
            features.disable("distlocks")
            features.enable("skiprocheck")

            # do not clean up PORTAGE_TMPDIR after a build failure,
            # it might still contain a usable CONFIG_CHECK tmpfile.
            features.disable("fail-clean")

            # FIXME: remove, has probably no effect anyway
            features.enable("notitles")

            # other FEATURES that might be interesting here
            # -cgroup, -ebuild-locks

            # noauto -cgroup -distlocks -skiprocheck -ebuild-locks notitles
            env["FEATURES"] = features.get_str()

            # EPAUSE_IGNORE: not set here, only relevant for EAPI 0,1,2

            # FIXME/TODO: for circumventing fatal check-reqs,
            #             set I_KNOW_WHAT_I_AM_DOING=y.
            #             However, this could do more harm than good.
            # env["I_KNOW_WHAT_I_AM_DOING"] = "Y"

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
                "--ignore-default-opts", "--color", "n",
                package_info.tmp_ebuild_file
            ],
            extra_env=self.env,
            cwd=pkg_dir,
            tmpdir=self.portage_tmpdir,
            logger=self.logger,
            universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
    # --- end of get_ebuild_subproc (...) ---

# --- end of EbuildEnv ---


class ConfigCheckEbuildEnv(EbuildEnv):

    _did_warn_about_ebuild_phase_errors = False

    def log_ebuild_phase_error(self, phase, package_info, proc):
        dolog_fail = self.logger.warning

        dolog_fail(
            "%s: did not complete the %r phase successfully",
            package_info.cpv, phase
        )

        if self.__class__._did_warn_about_ebuild_phase_errors:
            self.logger.debug("(not repeating the complete warning message)")

        else:
            dolog_fail(
                "This could be caused by kernelconfig's modifications"
                " to linux-info.eclass,"
            )
            dolog_fail(
                "but more likely the ebuild is doing things that should be"
                " handled in pkg_postinst(), like creating users or groups."
            )
            dolog_fail(
                "See Gentoo Bug #217042 for enewgroup/enewuser related errors,"
                "do not report them as kernelconfig bugs!"
            )
            self.__class__._did_warn_about_ebuild_phase_errors = True
        # --

        dolog_fail(
            "Below is the ebuild's output:\n"
            + proc.stdout.rstrip()  # proc's stderr redirected to stdout
            + "\n--- snip ---"
        )
    # --- end of log_ebuild_phase_error (...) ---

    def run_ebuild_phase(self, package_info, proc, phase):
        proc.zap()
        proc.cmdv.append(phase)

        try:
            with proc:
                proc_status = proc.join()
        except subprocess.TimeoutExpired:
            self.logger.error(
                "%s: the ebuild call timed out", package_info.cpv
            )
            return False

        if not proc_status:
            self.log_ebuild_phase_error(phase, package_info, proc)
            return False
        else:
            return True
    # --- end of run_ebuild_phase (...) ---

    def run_ebuild_get_config_check_outfile(self, package_info):
        # this is highly specific / relying in portage internals, FIXME
        pkg_tmpdir = self.portage_tmpdir.get_filepath(
            "tmp/portage/tmp/portage/{cpv!s}/temp".format(cpv=package_info.cpv)
        )
        outfile = _globals.get_vars().get_config_check_tmpfile_path(pkg_tmpdir)

        proc = self.get_ebuild_subproc(package_info)

#        # if "noauto" in FEATURES:
#
#        # run pkg_pretend() first and see if that is sufficient
#        #  packages that call check_extra_config() in both pkg_pretend()
#        #  and pkg_setup() get ignored this way,
#        #  but calling pkg_pretend() only is safer

        status = self.run_ebuild_phase(package_info, proc, "setup")
        if os.path.isfile(outfile):
            if not status:
                # FIXME/TODO: UNSAFE!
                #   check_extra_config() should create/delete a state
                #   file indicating whether outfile is safe to use
                self.logger.warning(
                    (
                        "%s did check for config options prior to failing, "
                        "using the information gathered so far"
                    ),
                    package_info.cpv
                )
            # --
            return outfile

        else:
            return None
    # --- end of run_ebuild_get_config_check_outfile (...) ---

    def _read_config_check_outfile(self, filepath):
        with open(filepath, "rt") as fh:
            config_check_str = fh.read()

        return util.parse_config_check(config_check_str, logger=self.logger)
    # --- end of _read_config_check_outfile (...) ---

    def iter_eval_config_check(self, package_info_iterable):
        """
        @return:  2-tuple(s) (cpv, config check dict)
        """
        package_info_list = list(package_info_iterable)
        num_pkgs = len(package_info_list)

        for idx, package_info in enumerate(package_info_list):
            cpv = package_info.cpv
            self.logger.info(
                "Getting config recommendations for %s (%d/%d)",
                cpv, (idx + 1), num_pkgs
            )
            outfile = self.run_ebuild_get_config_check_outfile(package_info)
            if outfile:
                self.logger.debug("%s: has config recommendations", cpv)
                yield (cpv, self._read_config_check_outfile(outfile))

            else:
                self.logger.debug("%s: no config recommendations", cpv)
                yield (cpv, None)
        # --
    # --- end of iter_eval_config_check (...) ---

# --- end of ConfigCheckEbuildEnv ---
