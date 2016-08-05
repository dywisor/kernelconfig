# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import argparse
import collections
import logging
import os.path
import sys


__all__ = ["KernelConfigMainScript"]

import kernelconfig.scripts._base
import kernelconfig.util.argutil
import kernelconfig.installinfo
import kernelconfig.kernel.info
import kernelconfig.kernel.hwdetection.modalias.cachedir
import kernelconfig.kernel.hwdetection.modalias.modulesdir
import kernelconfig.kconfig.config.gen
import kernelconfig.pm.portagevdb
import kernelconfig.util.fs
import kernelconfig.util.misc
import kernelconfig.util.multidir
import kernelconfig.util.settings
import kernelconfig.util.osmisc


import kernelconfig.sources._sources

# _version is a setup.py-generated file
try:
    import kernelconfig._version
except ImportError:
    PRJ_VERSION = "???"
else:
    PRJ_VERSION = kernelconfig._version.version


ModulesDirArgConfig = collections.namedtuple(
    "ModulesDirArgConfig", "path is_optional"
)


class KernelConfigArgTypes(kernelconfig.util.argutil.ArgTypes):

    NONE_WORDS = frozenset({"none", "_"})

    def arg_modules_dir(self, arg):
        if not arg:
            return False
        else:
            argslow = arg.strip().lower()

            if argslow in self.NONE_WORDS:
                return ModulesDirArgConfig(None, True)

            elif argslow in {"auto", }:
                return ModulesDirArgConfig(True, False)

            elif argslow in {"optional", }:
                return ModulesDirArgConfig(True, True)

            else:
                fpath = self.arg_fspath(arg)

                if os.path.isdir(fpath):
                    return ModulesDirArgConfig(fpath, False)

                elif os.path.isfile(fpath):
                    return ModulesDirArgConfig(fpath, False)

                else:
                    raise self.exc_type(
                        "modules dir is neither a dir nor a file"
                    )
    # ---
# ---


class KernelConfigMainScript(kernelconfig.scripts._base.MainScriptBase):

    def __init__(self, prog):
        super().__init__(prog)
        self.arg_parser = None
        self.arg_types = None
        self.install_info = kernelconfig.installinfo.get_install_info().copy()
        self.settings = None

        self.source_info = None
        self.conf_sources = None
    # --- end of __init__ (...) ---

    def get_conf_sources(self):
        conf_sources = self.conf_sources
        if conf_sources is None:
            conf_sources = self.create_loggable(
                kernelconfig.sources._sources.ConfigurationSources,
                install_info=self.install_info,
                source_info=self.source_info
            )
            self.conf_sources = conf_sources
        return conf_sources
    # ---

    def get_settings(self):
        settings = self.settings
        if settings is None:
            settings = kernelconfig.util.settings.SettingsFileReader()
            self.settings = settings
        return settings
    # ---

    def _setup_arg_parser_args(self, parser, arg_types):
        with_default = lambda h, d=None: (
            "%s (default: %s)" % (h, ("%(default)s" if d is None else d))
        )

        def add_script_mode_args():
            script_modes = [
                (
                    "generate-config", None,
                    "generate a .config file (default mode)"
                ),
                (
                    "generate-modalias", None,
                    (
                        "create files for modalias-based hardware-detection\n"
                        "WARNING: this takes a lot of time!"
                    )
                ),
                (
                    "eval-config-check", None,
                    (
                        "TESTING ONLY: re-evaluate CONFIG_CHECK,\n"
                        "comparing it against <srctree>"
                    )
                ),
                (
                    "list-source-names", None,
                    "list available curated sources"
                ),
                (
                    "list-sources", None,
                    "list available curated sources and their paths"
                ),
                (
                    "help-sources", None,
                    "list available curated sources and their usage"
                ),
            ]

            script_mode_group = parser.add_argument_group(title="script mode")
            script_mode_mut_group = (
                script_mode_group.add_mutually_exclusive_group()
            )

            script_mode_mut_group.add_argument(
                "--script-mode",
                dest="script_mode", default=None,
                choices=[xv[0] for xv in script_modes],
                help="set script mode"
            )

            for mode_name, mode_opts, mode_help in script_modes:
                mode_args = mode_opts or ["--{}".format(mode_name)]
                mode_kwargs = {
                    "dest": "script_mode",
                    "default": argparse.SUPPRESS,
                    "action": "store_const",
                    "const": (mode_name, None),
                    "help": mode_help
                }
                script_mode_mut_group.add_argument(*mode_args, **mode_kwargs)
            # --

            script_mode_mut_group.add_argument(
                "--help-source", metavar="<name>",
                dest="script_mode", default=argparse.SUPPRESS,
                type=lambda w: ("help-source", arg_types.arg_nonempty(w)),
                help="print help of the given curated source"
            )
        # ---

        kernelconfig.util.argutil.UsageAction.attach_to(parser)

        parser.add_argument(
            '-V', '--print-version', action='version', version=PRJ_VERSION
        )

        parser.add_argument(
            "-q", "--quiet", default=0, action="count",
            help="be less verbose (can be specified more than once)"
        )
        parser.add_argument(
            "-v", "--verbose", default=0, action="count",
            help="be more verbose (can specified more than once)"
        )
        # -- end basic args

        common_arg_group = parser.add_argument_group(
            title="common optional arguments"
        )

        # the following args are mostly consistent with those
        # of the original project:
        common_arg_group.add_argument(
            "-a", "--arch", metavar="<arch>",
            default=argparse.SUPPRESS,
            help=with_default(
                "configuration target architecture", "\"uname -m\""
            )
        )

        common_arg_group.add_argument(
            "-k", "--kernel", dest="srctree", metavar="<srctree>",
            default=argparse.SUPPRESS,
            type=arg_types.arg_existing_dir,
            help=with_default(
                "path to the unpacked kernel sources directory", "\".\""
            )
        )
        # -- end common_arg_group

        genconfig_arg_group = parser.add_argument_group(
            title="optional arguments for generate-config"
        )

        genconfig_arg_group.add_argument(
            "-s", "--settings", dest="settings_file", metavar="<file>",
            default=argparse.SUPPRESS,
            type=arg_types.arg_existing_file_special_relpath,
            help=with_default(
                "settings file", "\"default\""
                # explain relpath lookup
            )
        )

        # "--config" is an option and not a positional arg
        #
        # In future, with "curated sources" and a settings file,
        # it will be unlikely to specify the input config via --config.
        #
        genconfig_arg_group.add_argument(
            "--config", dest="inconfig", metavar="<file>",
            type=arg_types.arg_existing_file,
            default=argparse.SUPPRESS,
            help=with_default(
                "input kernel configuration file", "\"<srctree>/.config\""
            )
        )

        genconfig_arg_group.add_argument(
            "-I", dest="featureset_files", metavar="<file>",
            type=arg_types.arg_existing_file,
            default=[], action="append",
            help=with_default(
                "config-modifying \"macros\" files", "none"
            )
        )

        genconfig_arg_group.add_argument(
            "-O", "--outconfig", metavar="<file>",
            type=arg_types.arg_output_file,
            default=argparse.SUPPRESS,
            help=with_default(
                "output kernel configuration file", "\"<srctree>/.config\""
            )
        )

        genconfig_arg_group.add_argument(
            "-H", "--hwdetect", metavar="<file>", dest="hwdetect_file",
            type=arg_types.arg_existing_file,
            default=argparse.SUPPRESS,
            help="enable hardware detection from hwcollect file"
        )

        genconfig_arg_group.add_argument(
            "-m", "--modules-dir", metavar="<mod_dir>",
            default=argparse.SUPPRESS,
            type=arg_types.arg_modules_dir,
            help=with_default(
                (
                    'path to the modules directory,\n'
                    'used for looking up module aliases,\n'
                    'can also point to a tarball\n'
                    'or be one of\n'
                    '* "none": disable\n'
                    '* "auto": autodetect and required\n'
                    '* "optional": autodetect and optional\n'
                ),
                'optional'
            )
        )

        genconfig_arg_group.add_argument(
            "--unsafe-modalias", dest="unsafe_modalias",
            default=False, action="store_true",
            help=with_default(
                (
                    'allow to autodetect modules directories\n'
                    'that are not strictly compatible with <srctree>\n'
                    '(--modules-dir "auto", "optional" only)\n'
                ),
                "--safe"
            )
        )

        genconfig_arg_group.add_argument(
            "--safe-modalias", dest="unsafe_modalias",
            default=argparse.SUPPRESS, action="store_false",
            help=(
                (
                    'restrict --modules-dir autodetection\n'
                    'to strictly compatible directories'
                )
            )
        )
        # -- end genconfig_arg_group

        genmodalias_arg_group = parser.add_argument_group(
            title="optional arguments for generate-modalias"
        )

        genmodalias_arg_group.add_argument(
            "-j", "--jobs", metavar="<numjobs>", dest="numjobs", type=int,
            default=max(1, kernelconfig.util.osmisc.get_cpu_count()),
            help=with_default(
                "allow <numjobs> at once when building modules", None
            )
        )

        genmodalias_arg_group.add_argument(
            "--modalias-build-dir", metavar="<dir>",
            type=arg_types.arg_couldbe_dir,
            default=argparse.SUPPRESS,
            help=with_default(
                (
                    "root directory for build files\n"
                    "where a temporary build directory will be created.\n"
                    "Approximately 2G of space is required.\n"
                ),
                "$TMPDIR or /var/tmp"
            )
        )
        # -- end genmodalias_arg_group

        add_script_mode_args()
    # --- end of _setup_arg_parser_args (...) ---

    def init_arg_parser(self):
        arg_types = self.arg_types
        if arg_types is None:
            arg_types = KernelConfigArgTypes()
            self.arg_types = arg_types
        # --

        parser = argparse.ArgumentParser(
            prog=self.get_prog_name(),
            description="Generate Linux kernel configuration files",
            formatter_class=argparse.RawTextHelpFormatter
        )

        self._setup_arg_parser_args(parser, arg_types)
        self.arg_parser = parser
    # --- end of init_arg_parser (...) ---

    def do_main_setup_logging(self, arg_config):
        # logging
        log_levels = [
            logging.DEBUG, logging.INFO, logging.WARNING,
            logging.ERROR, logging.CRITICAL
        ]

        k = 2 - arg_config["verbose"] + arg_config["quiet"]

        if k < 0:
            log_level = log_levels[0]
        elif k >= len(log_levels):
            log_level = log_levels[-1]
        else:
            log_level = log_levels[k]
        # ---

        self.zap_log_handlers()
        self.setup_console_logging(log_level)
    # ---

    def do_main_load_settings(self, arg_config):
        settings_arg = arg_config.get("settings_file")
        if settings_arg is None:
            settings_arg = (True, "default")
        elif not settings_arg:
            return

        need_lookup, filename = settings_arg

        if need_lookup:
            settings_file = self.install_info.get_settings_file(filename)
        else:
            settings_file = filename

        if not settings_file:
            if self.arg_parser is None:
                raise FileNotFoundError(filename)
            else:
                self.arg_parser.error("settings file %r not found" % filename)
        # --

        self.logger.info("Reading settings from %s", settings_file)
        self.get_settings().read_file(settings_file)
    # --- end of do_main_load_settings (...) ---

    def do_main_setup_source_info(self, arg_config):
        source_info = self.create_loggable(
            kernelconfig.kernel.info.KernelInfo,
            (arg_config.get("srctree") or self.initial_working_dir),
            arch=arg_config.get("arch")
        )

        if not source_info.check_srctree():
            self.arg_parser.error(
                "%r does not appear to be a kernel sources directory."
                % source_info.srctree
            )

        source_info.prepare()
        self.source_info = source_info
    # --- end of do_main_setup_source_info (...) ---

    def do_main_load_input_config(self, arg_config, config):
        if arg_config.get("inconfig"):
            input_config_files = [arg_config["inconfig"]]

        elif self.settings is None:
            raise AssertionError(
                "settings must be initialized before config file loaded"
            )

        else:
            conf_sources = self.get_conf_sources()

            input_config_files = (
                conf_sources.get_configuration_basis_from_settings(
                    self.settings
                )
            )
            assert isinstance(input_config_files, list)
        # --

        if not input_config_files:
            self.arg_parser.error("No input config!")

        else:
            if __debug__:
                missing = [
                    f for f in input_config_files if not os.path.isfile(f)
                ]
                if missing:
                    self.arg_parser.error(
                        "input .config does not exist: {!r}".format(missing)
                    )
            # --

            config.read_config_files(*input_config_files)
    # ---

    def do_main_get_modules_dir(self, arg_config):
        modulesdir_pym = kernelconfig.kernel.hwdetection.modalias.modulesdir
        cachedir_pym = kernelconfig.kernel.hwdetection.modalias.cachedir

        mod_dir_config = arg_config.get("modules_dir", None)

        if mod_dir_config is None:
            # the default behavior is: autodetect, but ignore if unavailable
            mod_dir_config = ModulesDirArgConfig(True, True)
        # --

        if not mod_dir_config.path:
            modules_dir = self.create_loggable(modulesdir_pym.NullModulesDir)

        elif mod_dir_config.path is True:
            # lookup
            modalias_cache = self.create_loggable(
                cachedir_pym.ModaliasCache,
                install_info=self.install_info,
                source_info=self.source_info
            )

            modules_dir = modalias_cache.get_modules_dir(
                unsafe=arg_config["unsafe_modalias"]
            )
            modules_dir.set_logger(parent_logger=self.logger)

        else:
            modules_dir = self.create_loggable(
                modulesdir_pym.ModulesDir, mod_dir_config.path
            )
        # --

        if not mod_dir_config.is_optional:
            if not modules_dir.prepare():
                self.logger.error("Failed to get modalias info source")
                return None
        # --

        return modules_dir
    # --- end of do_main_get_modules_dir (...) ---

    def do_main_script_genconfig(self, arg_config):
        def get_interpreter():
            nonlocal arg_config
            nonlocal config_gen

            interpreter = config_gen.get_config_choices_interpreter()

            # start with a clean opcode mask
            interpreter.clear_opcode_mask()

            # if "hardware detection from file" is enabled,
            # disable "hwdetect" instructions
            if arg_config.get("hwdetect_file"):
                self.logger.debug(
                    'Disabling hwdetect interpreter instructions:'
                    ' hwdetect-from-file has been requested'
                )
                interpreter.disable_op("hwdetect")
            # --

            return interpreter
        # ---

        self.do_main_setup_logging(arg_config)
        self.do_main_load_settings(arg_config)
        if self.settings is None:
            raise AssertionError("settings not loaded!")
        self.do_main_setup_source_info(arg_config)

        # default output config
        if not arg_config.get("outconfig"):
            arg_config["outconfig"] = self.source_info.get_filepath(".config")
        # --

        # config creation
        # * init
        #
        #   ** modalias lookup info source
        modules_dir = self.do_main_get_modules_dir(arg_config)
        if modules_dir is None:
            # already logged
            return False

        config_gen = self.create_loggable(
            kernelconfig.kconfig.config.gen.KernelConfigGenerator,
            install_info=self.install_info,
            source_info=self.source_info,
            modules_dir=modules_dir
        )

        config = config_gen.get_config()

        #  the output config file must be backed up
        #  before loading the input config
        #
        #  Otherwise, the wrong file could get copied,
        #  e.g. when running in-source "make defconfig"
        #  with outfile <srctree>/.config
        #
        kernelconfig.util.fs.prepare_output_file(arg_config["outconfig"])

        # load hwdetect-from-file data early on
        #  downloading a conf basis and then erroring out due to a wrong
        #  hwdetect file format would be a waste of user time
        hwdetect_suggestions = None
        if arg_config.get("hwdetect_file"):
            hwdetector = config_gen.get_hwdetector()
            assert hwdetector is not None
            hwdetect_errors, hwdetect_suggestions = (
                hwdetector.get_suggestions(
                    hwdetect_file=arg_config["hwdetect_file"]
                )
            )

            if hwdetect_errors:
                # already logged
                return False

            assert hwdetect_suggestions is not None
        # --

        # * load input config
        self.do_main_load_input_config(arg_config, config)

        # * modify
        #   1. featureset files
        if arg_config["featureset_files"]:
            interpreter = get_interpreter()
            if not interpreter.process_files(arg_config["featureset_files"]):
                self.print_err("Error occurred while loading \"macros\" files")
                return False
        # --

        #   2. hwdetect from file
        if hwdetect_suggestions is not None:
            # TODO/FIXME: better logging, maybe add this to config choices
            #             (and dedup/reuse related interpreter code)
            #             in particular,
            #             error handling differs from ipret - currently
            self.logger.debug("Adding hwdetect-from-file config options")
            conf_choices = config_gen.get_config_choices()

            for option, value in hwdetect_suggestions.items():
                if not conf_choices.option_set_to(option, value):
                    return False
        # --

        #   3. settings->[options]
        settings_conf_mod_requests = self.settings.get_section("options")
        if settings_conf_mod_requests:
            interpreter = get_interpreter()
            if not interpreter.process_str(
                "\n".join(settings_conf_mod_requests)
            ):
                return False
        # --

        # * "resolve"
        config_gen.commit()

        # * write output config
        config.write_config_file(arg_config["outconfig"])

    # --- end of do_main_script_genconfig (...) ---

    def do_main_script_eval_config_check(self, arg_config):
        self.do_main_setup_logging(arg_config)
        self.do_main_setup_source_info(arg_config)

        pm_info = self.create_loggable(
            kernelconfig.pm.portagevdb.PMIntegration,
            install_info=self.install_info,
            source_info=self.source_info
        )

        if not pm_info.enqueue_installed_packages():
            self.logger.info("No packages inheriting linux-info found!")
            return False
        # --

        # FIXME: mixing logger and print
        config_check_map = pm_info.eval_config_check()
        if not config_check_map:
            self.logger.info("CONFIG_CHECK is empty or None")
        else:
            print(config_check_map)
    # --- end of do_main_script_eval_config_check (...) ---

    def do_main_script_list_sources(self, arg_config, names_only):
        def any_of(sfiles):
            for item in filter(None, sfiles):
                return item
            return None
        # ---

        self.do_main_setup_logging(arg_config)
        # FIXME: drop this requirement:
        self.do_main_setup_source_info(arg_config)

        conf_sources = self.get_conf_sources()
        sources_info = conf_sources.get_available_sources_info()

        if not sources_info:
            return False

        outstream_write = sys.stdout.write

        source_names = sorted(sources_info)
        if names_only:
            for name in source_names:
                outstream_write("{}\n".format(name))

        else:
            for name in source_names:
                sfile = any_of(sources_info[name])
                outstream_write("{}\n  ({})\n".format(name, sfile or "???"))
        # --

    # --- end of do_main_script_list_sources (...) ---

    def do_main_script_help_sources(self, arg_config):
        self.do_main_setup_logging(arg_config)
        self.do_main_setup_source_info(arg_config)

        conf_sources = self.get_conf_sources()
        conf_sources.load_available_sources()   # retval ignored

        if not conf_sources:
            # no sources
            return False

        outstream_write = sys.stdout.write

        for k, conf_source in enumerate(conf_sources.iter_sources()):
            if k:
                outstream_write("\n\n")

            outstream_write("{}:\n".format(conf_source.name))

            arg_help_str = conf_source.format_help()
            if not arg_help_str:
                outstream_write("  No help available.\n")

            else:
                # reindent
                help_msg = "\n".join((
                    (("  " + l) if l else l)
                    for l in arg_help_str.splitlines()
                ))

                outstream_write(help_msg)
                outstream_write("\n")
            # --
        # -- end for
    # --- end of do_main_script_help_sources (...) ---

    def do_main_script_help_source(self, arg_config, source_name):
        self.do_main_setup_logging(arg_config)
        self.do_main_setup_source_info(arg_config)

        outstream_write = sys.stdout.write

        conf_sources = self.get_conf_sources()
        conf_source, conf_source_exc = conf_sources.load_source(source_name)

        if conf_source_exc:
            outstream_write(
                "{name}: failed to load: {what!s} ({why!s})\n".format(
                    name=source_name,
                    what=getattr(
                        conf_source_exc[0], "__name__", conf_source_exc[0]
                    ),
                    why=conf_source_exc[1]
                )
            )
            return False

        elif conf_source is None:
            outstream_write("{}: not found\n".format(source_name))
            return False

        else:
            arg_help_str = conf_source.format_help()

            if not arg_help_str:
                outstream_write("{}: no help available.\n".format(source_name))

            else:
                outstream_write(arg_help_str)
                outstream_write("\n")
        # --
    # --- end of do_main_script_help_source (...) ---

    def do_main_script_genmodalias(self, arg_config):
        self.do_main_setup_logging(arg_config)
        self.do_main_setup_source_info(arg_config)

        modalias_cache_builder = self.create_loggable(
            (
                kernelconfig.kernel.hwdetection.modalias.cachedir.
                ModaliasCacheBuilder
            ),
            install_info=self.install_info,
            source_info=self.source_info,
            build_root_dir=arg_config.get("modalias_build_dir"),
            numjobs=arg_config["numjobs"]
        )

        return modalias_cache_builder.run_create()
    # --- end of do_main_script_genmodalias (...) ---

    def do_main(self, arg_config):
        script_mode = arg_config["script_mode"]

        if not script_mode or script_mode[0] == "generate-config":
            return self.do_main_script_genconfig(arg_config)

        elif script_mode[0] == "list-source-names":
            return self.do_main_script_list_sources(arg_config, True)

        elif script_mode[0] == "list-sources":
            return self.do_main_script_list_sources(arg_config, False)

        elif script_mode[0] == "help-sources":
            return self.do_main_script_help_sources(arg_config)

        elif script_mode[0] == "help-source":
            return self.do_main_script_help_source(arg_config, script_mode[1])

        elif script_mode[0] == "generate-modalias":
            return self.do_main_script_genmodalias(arg_config)

        elif script_mode[0] == "eval-config-check":
            return self.do_main_script_eval_config_check(arg_config)

        else:
            raise NotImplementedError("script mode", script_mode)
    # --- end of do_main (...) ---

    def run(self, argv):
        if self.arg_parser is None:
            self.init_arg_parser()

        parsed_args = self.arg_parser.parse_args(argv)
        return self.do_main(vars(parsed_args))
    # --- end of run (...) ---

# --- end of KernelConfigMainScript ---


if __name__ == "__main__":
    KernelConfigMainScript.run_main(prog="kernelconfig")
# --
