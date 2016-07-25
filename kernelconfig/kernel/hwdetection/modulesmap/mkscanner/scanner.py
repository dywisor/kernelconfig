# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import os
import re
import shlex

from .....abc import loggable
from .....util import fileio
from .....util import fs
from .....util import accudict

from ... import util
from . import preference


__all__ = ["ModuleConfigOptionsScanner"]


class ModuleConfigOptionsScanner(loggable.AbstractLoggable):

    normalize_module_name = staticmethod(util.normalize_module_name)

    def get_module_options_map(self):
        # create a dict that maps object names to config options
        #   some of the object names are kernel modules,
        #   others are just object files.
        #   For example, filesystem that optionally support xattr,
        #   usually have a xattr.o object, which is not a kenrel module.
        #
        #   This cannot be decided without
        #   (a) replicating a considerable amount of kernel Makefile logic,
        #   (b) or writing a custom Makefile that makes use of the kernel
        #       sources' lib-Makefiles and tells where to look for which
        #       module
        #
        #   We work around that with some sort of preference pinning.
        #   Leftover modules that are ambiguous get dropped (and logged).
        #
        #   For that, more detailed information about the object name's
        #   origin is beneficial, and therefore _scan_module_config_options()
        #   also returns the directory where the option<>object relation
        #   was found (as relative path).
        #
        accu_dict = self.get_module_options_origin_map()
        return self.scanpol.pick_config_options(accu_dict)
    # --- end of get_module_options_map (...) ---

    def get_module_options_origin_map(self):
        return accudict.DictAccumulatorDict(
            (module_name, (option, dirpath_rel))
            for dirpath_rel, option, module_name
            in self._scan_module_config_options()
        )
    # --- end of get_module_options_origin_map (...) ---

    def __init__(self, source_info, **kwargs):
        super().__init__(**kwargs)
        self.source_info = source_info
        self.scanpol = (
            preference.ModuleConfigOptionsScannerStrategy.new_default()
        )

        # The regular expression used for matching Makefile var assignments
        # that reference config options
        #
        # Samples:
        #
        #   obj-$(CONFIG_A)                 += a.o
        #
        #     is interpreted here as "'a.o' depends on CONFIG_A"
        #
        #     ("a.o" => ("obj-$(CONFIG_A)" => {obj-y, obj-m, obj-n}),
        #
        #     where obj-y is the list of builtin modules,
        #     obj-m is the list of modules,
        #     and obj-n (or obj-) is list of disabled modules
        #
        #   obj-$(CONFIG_A)                 += a.o b.o
        #   obj-${CONFIG_A}                 += a.o
        #   obj-x-$(CONFIG_A)               := a.o
        #   obj-z-$(subst m,y,$(CONFIG_A))  += a.o
        #
        # But also:
        #   obj-$(CONFIG_A)                 += -DDEF
        #   obj-$(CONFIG_A)                 += a/
        #   obj-$(CONFIG_A:m=y)             += a/
        #   processor-$(CONFIG_ACPI_PROCESSOR_IDLE) += processor_idle.o
        #
        # So, in a first pass the entire var := value line is matched
        #   ^ <sth>
        #   + "$(CONFIG_"
        #   + <name>
        #   + (":" <sth>)?
        #   + ")"
        #   + <sth>
        #   + (":="|"+="|"=")
        #   + <value>
        #   + ("#" <sth>)? $
        #
        #   As alternative to "$(CONFIG_" + <name>" ")",
        #   "${...}", "$(...}", "${...)" are also allowed.
        #
        #   Note that this will also match  obj := $(CONFIG_X:m=y) := x
        #   (but there are no such cases in the kernel source tree)
        #
        # And in a second pass, module names are extracted from <value>.
        # This is done with shlex.split(<value>),
        # and every item ending with ".o" is considered to be a module.
        #
        self.mkvar_regexp = re.compile(
            r'^obj-(?:\S.*?)?'
            r'\$[\(\{]CONFIG_'
            r'(?P<option>[A-Z_a-z0-9]+)'
            r'(?:[:].*?)?'
            r'[\}\)]'
            r'.*?'
            r'[:+]?[=]'
            r'\s*(?P<value>.*?)'
            r'(?:[#].*)?$'
        )
    # --- end of __init__ (...) ---

    def _iter_dir_candidates(self):
        def dirnames_remove_name(dirnames, name):
            try:
                dirnames.remove(name)
            except ValueError:
                pass
        # ---

        def compile_ored_relpath_regexp(dir_parts):
            return re.compile(
                r'^(?:{})(?:$|/)'.format(
                    r'|'.join(("(?:{})".format(w) for w in dir_parts))
                )
            )

        # relpath_whitelist: dirpaths matching this expr get searched for
        #                    Kbuild/Makefile
        #                    This regexp has the highest precedence.
        relpath_whitelist = compile_ored_relpath_regexp(
            (
                'arch/{karch}'.format(karch=self.source_info.karch),
                'drivers',
                'fs',
                'sound'
            )
        )

        # relpath_greylist:  dirpaths matching this expr are not searched
        #                    for Kbuild/Makefile,
        #                    but its subdirectories get scanned.
        #                    This regexp has lower precedence than
        #                    the whitelist.
        relpath_greylist = re.compile(
            r'^(?:arch)$'
        )

        if __debug__:
            # relpath_blacklist: dirpaths matching this expr get exempted from
            #                    further scanning (of subdirectories)
            #                    This regexp has the lowest precedence.
            relpath_blacklist = compile_ored_relpath_regexp(
                (
                    '(?:[^/]/)*[.][^/]+',    # esp. .git
                    'arch',
                    'block',
                    'certs',
                    'crypto',
                    'debian',
                    'firmware',
                    'include',
                    'init',
                    'ipc',
                    'kernel',
                    'lib',
                    'mm',
                    'net',
                    'patches',
                    'quilt',
                    'samples',
                    'security',
                    'scripts',
                    'tools',
                    'usr',
                    'virt',
                )
            )

            match_relpath_blacklist = relpath_blacklist.match

        else:
            match_relpath_blacklist = lambda w: True
        # --

        for dirpath, dirpath_rel, dirnames, filenames in fs.walk_relpath(
            self.source_info.srctree
        ):
            # do not descend into Documentation dirs
            dirnames_remove_name(dirnames, "Documentation")

            if not dirpath_rel:
                pass

            elif relpath_whitelist.match(dirpath_rel):
                yield (dirpath, dirpath_rel, dirnames, filenames)

            elif relpath_greylist.match(dirpath_rel):
                pass

            elif match_relpath_blacklist(dirpath_rel):
                dirnames[:] = []

            else:
                self.logger.warning(
                    "ignoring unknown subdirectory %s", dirpath_rel
                )
                dirnames[:] = []
        # --
    # --- end of _iter_dir_candidates (...) ---

    def _iter_mk_input_files(self):
        _osp_join = os.path.join

        for dirpath, dirpath_rel, dirnames, filenames in (
            self._iter_dir_candidates()
        ):
            for fname in filenames:
                if fname in {"Kbuild", "Makefile"}:
                    yield (dirpath_rel, _osp_join(dirpath, fname))
    # --- end of _iter_mk_input_files (...) ---

    def _pre_scan_makefile(self, makefile):
        """
        Scans a Makefile for variable assignments
        that reference a CONFIG_ option,
        and returns 2-tuple (varname, value string).
        """
        # the regexp for matching makefile var assignments,
        # it is covered in detail above
        match_mkvar_regexp = self.mkvar_regexp.match

        with open(makefile, "rt") as fh:
            # rstrip lines
            # and accumulate input lines (join lines ending with "\")
            #
            matchgen = (
                (line, match_mkvar_regexp(line))
                for line in fileio.accumulate_line_cont(
                    (l.rstrip() for l in fh)
                )
            )

            if __debug__:
                obj_ymn_regexp = re.compile(r'^obj-[ymn]?($|\s)')
                line_refs_config_regexp = re.compile(
                    r'^obj-(?:\S+.*?)?\$[\(\{]?CONFIG_.*='
                )

                for line, match in matchgen:
                    if match is not None:
                        yield (match.group("option"), match.group("value"))

                    elif obj_ymn_regexp.match(line):
                        pass

                    elif line_refs_config_regexp.match(line):
                        self.logger.warning("unmatched: %s", line)
            else:
                for line, match in matchgen:
                    if match is not None:
                        yield (match.group("option"), match.group("value"))
        # -- end with
    # --- end of _pre_scan_makefile (...) ---

    def _scan_makefile(self, makefile):
        for option, value in self._pre_scan_makefile(makefile):
            for vpart in shlex.split(value):
                if vpart[-2:] == ".o":
                    yield (option, vpart[:-2])
                elif vpart[-1] == "/":
                    yield (option, vpart[:-1])
    # --- end of _scan_makefile (...) ---

    def _scan_module_config_options(self):
        normalize_module_name = self.normalize_module_name

        for dirpath_rel, makefile in self._iter_mk_input_files():
            for option, module in self._scan_makefile(makefile):
                yield (dirpath_rel, option, normalize_module_name(module))
    # --- end of _scan_module_config_options (...) ---

# --- end of ModuleConfigOptionsScanner ---


if __name__ == "__main__":
    def main():
        import argparse
        import collections

        def print_module_options_map(module_options_map):
            max_name_len = max(map(len, module_options_map)) + 1
            for module_name in sorted(
                module_options_map, key=lambda w: w.lower()
            ):
                print(
                    "{module:<{nlen}}: {options}".format(
                        module=module_name,
                        nlen=max_name_len,
                        options=", ".join(module_options_map[module_name])
                    )
                )
            # --
        # ---

        def get_arg_parser():
            arg_parser = argparse.ArgumentParser()
            arg_parser.add_argument("srctree", nargs="?", default=os.getcwd())
            arg_parser.add_argument("-a", "--arch", default="x86")

            cmd_meta_grp = arg_parser.add_argument_group(title="command")
            cmd_grp = cmd_meta_grp.add_mutually_exclusive_group()
            word = "print-mapping"
            cmd_grp.add_argument(
                ("--%s" % word), dest="command", default=word,
                action="store_const", const=word
            )
            for word in {"print-conflicts"}:
                cmd_grp.add_argument(
                    ("--%s" % word), dest="command", default=argparse.SUPPRESS,
                    action="store_const", const=word
                )
            # --

            return arg_parser
        # ---

        MiniSourceInfo = collections.namedtuple(
            "MiniSourceInfo", "srctree karch"
        )

        arg_parser = get_arg_parser()
        arg_config = arg_parser.parse_args()

        source_info = MiniSourceInfo(arg_config.srctree, arg_config.arch)
        scanner = ModuleConfigOptionsScanner(source_info)

        if arg_config.command == "print-mapping":
            module_options_map = scanner.get_module_options_map()
            print_module_options_map(module_options_map)

        elif arg_config.command == "print-conflicts":
            accu_dict = scanner.get_module_options_origin_map()
            conflicts = {
                module: [
                    "{option}({origin})".format(
                        option=option,
                        origin=", ".join(origin)
                    ) for option, origin in accu_dict[module].items()
                ]
                for module, options
                in scanner.scanpol.iter_pick_config_options(accu_dict)
                if options is None
            }

            print_module_options_map(conflicts)
            print("\n{:d} conflicts detected.".format(len(conflicts)))

        else:
            raise NotImplementedError(arg_config.command)
    # ---

    try:
        main()
    except BrokenPipeError:
        pass
