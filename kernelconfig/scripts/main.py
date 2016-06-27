# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import argparse
import logging
import os.path

__all__ = ["KernelConfigMainScript"]

import kernelconfig.scripts._base
import kernelconfig.scripts._argutil
import kernelconfig.installinfo
import kernelconfig.kernel.info
import kernelconfig.kconfig.config.gen
import kernelconfig.util.fs
import kernelconfig.util.multidir
import kernelconfig.util.settings

import kernelconfig.sources._sources

# _version is a setup.py-generated file
try:
    import kernelconfig._version
except ImportError:
    PRJ_VERSION = "???"
else:
    PRJ_VERSION = kernelconfig._version.version


class KernelConfigMainScript(kernelconfig.scripts._base.MainScriptBase):

    def __init__(self, prog):
        super().__init__(prog)
        self.arg_parser = None
        self.arg_types = None
        self.install_info = kernelconfig.installinfo.get_install_info().copy()
        self.settings = kernelconfig.util.settings.SettingsFileReader()

        self.source_info = None
    # --- end of __init__ (...) ---

    def _setup_arg_parser_args(self, parser, arg_types):
        with_default = lambda h, d=None: (
            "%s (default: %s)" % (h, ("%(default)s" if d is None else d))
        )

        kernelconfig.scripts._argutil.UsageAction.attach_to(parser)

        parser.add_argument(
            '-V', '--print-version', action='version', version=PRJ_VERSION
        )

        # the following args are mostly consistent with those
        # of the original project:
        parser.add_argument(
            "-a", "--arch", metavar="<arch>",
            default=argparse.SUPPRESS,
            help=with_default(
                "configuration target architecture", "\"uname -m\""
            )
        )

        parser.add_argument(
            "-k", "--kernel", dest="srctree", metavar="<srctree>",
            default=argparse.SUPPRESS,
            type=arg_types.arg_existing_dir,
            help=with_default(
                "path to the unpacked kernel sources directory", "\".\""
            )
        )

        parser.add_argument(
            "-s", "--settings", dest="settings_file", metavar="<file>",
            default=argparse.SUPPRESS,
            type=arg_types.arg_existing_file_special_relpath,
            help=with_default(
                "settings file", "\"default\""
                # explain relpath lookup
            )
        )

        # --

        # "--config" is an option and not a positional arg
        #
        # In future, with "curated sources" and a settings file,
        # it will be unlikely to specify the input config via --config.
        #
        parser.add_argument(
            "--config", dest="inconfig", metavar="<file>",
            type=arg_types.arg_existing_file,
            default=argparse.SUPPRESS,
            help=with_default(
                "input kernel configuration file", "\"<srctree>/.config\""
            )
        )

        parser.add_argument(
            "-I", dest="featureset_files", metavar="<file>",
            type=arg_types.arg_existing_file,
            default=[], action="append",
            help=with_default(
                "config-modifying \"macros\" files", "none"
            )
        )

        parser.add_argument(
            "-O", "--outconfig", metavar="<file>",
            type=arg_types.arg_output_file,
            default=argparse.SUPPRESS,
            help=with_default(
                "output kernel configuration file", "\"<srctree>/.config\""
            )
        )

        parser.add_argument(
            "-q", "--quiet", default=0, action="count",
            help="be less verbose (can be specified more than once)"
        )
        parser.add_argument(
            "-v", "--verbose", default=0, action="count",
            help="be more verbose (can specified more than once)"
        )
    # --- end of _setup_arg_parser_args (...) ---

    def init_arg_parser(self):
        arg_types = self.arg_types
        if arg_types is None:
            arg_types = kernelconfig.scripts._argutil.ArgTypes()
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
        self.settings.read_file(settings_file)
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
            input_config_file = arg_config["inconfig"]

        else:
            conf_sources = self.create_loggable(
                kernelconfig.sources._sources.ConfigurationSources,
                install_info=self.install_info,
                source_info=self.source_info
            )

            input_config_file = (
                conf_sources.get_configuration_basis_from_settings(
                    self.settings
                )
            )
        # --

        if not input_config_file:
            self.arg_parser.error("No input config!")
        elif not os.path.isfile(input_config_file):
            self.arg_parser.error(
                "input .config does not exist: {!r}".format(input_config_file)
            )
        # --
        config.read_config_file(input_config_file)
    # ---

    def do_main(self, arg_config):
        self.do_main_setup_logging(arg_config)
        self.do_main_load_settings(arg_config)
        self.do_main_setup_source_info(arg_config)

        # default output config
        if not arg_config.get("outconfig"):
            arg_config["outconfig"] = self.source_info.get_filepath(".config")
        # --

        # config creation
        # * init
        config_gen = self.create_loggable(
            kernelconfig.kconfig.config.gen.ConfigGenerator,
            self.install_info, self.source_info
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

        # * load input config
        self.do_main_load_input_config(arg_config, config)

        # * modify
        if arg_config["featureset_files"]:
            interpreter = config_gen.get_config_choices_interpreter()
            if not interpreter.process_files(arg_config["featureset_files"]):
                self.print_err("Error occurred while loading \"macros\" files")
                return False
        # --

        settings_conf_mod_requests = self.settings.get_section("options")
        if settings_conf_mod_requests:
            interpreter = config_gen.get_config_choices_interpreter()
            if not interpreter.process_str(
                "\n".join(settings_conf_mod_requests)
            ):
                return False
        # --

        # * "resolve"
        config_gen.commit()

        # * write output config
        config.write_config_file(arg_config["outconfig"])

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
