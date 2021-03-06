# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import collections.abc
import re
import shutil

from ...abc import loggable
from ...util import fileio
from ...util import tmpdir
from .. import symbol
from .. import lkconfig

__all__ = ["Config", "KernelConfig"]


class ConfigFileReader(loggable.AbstractLoggable):
    """
    @ivar option_expr_str:  regexp str for matching config option names
    @type option_expr_str:  C{str}
    @ivar value_expr_str:   regexp str for matching any value
    @type value_expr_str:   C{str}
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.option_expr_str = r'[A-Z_a-z0-9]+'
        self.value_expr_str = (
            r'(?:'
            r'(?:[\"](?:[^\"]|\\[\"])*[\"])'
            r'|(?:[\'](?:[^\']|\\[\'])*[\'])'
            r'|(?:\S+)'
            r')'
        )
        # # r'(?:\S+(?:\s+\S+)*)'
    # ---

    def read_file(self, infile, filename=None, **kwargs):
        """Generator that reads and processes entries from a .config file.

        @param   infile:    file object or path
        @type    infile:    fileobj or C{str}
        @keyword filename:  file name, defaults to None
        @type    filename:  C{str} or C{None}
        @param   kwargs:    additional keyword parameters
                            for L{fileio.read_text_file_lines()}
        @type    kwargs:    C{dict} :: C{str} => _

        @return 3-tuple (
                  line number, option name, None or 2-tuple(value type, value))
        @rtype: 3-tuple (
                 C{int},
                 C{str},
                 C{None} | 2-tuple (
                   L{symbol.KconfigSymbolValueType},
                   C{str}|C{int}|L{symbol.TristateKconfigSymbolValue}
                  )
                )
        """
        _unpack_value = symbol.unpack_value_str

        option_value_regexp = re.compile(
            r'^(?P<option>{oexpr})[=](?P<value>{vexpr})(?:\s+[#].*)?$'.format(
                oexpr=self.option_expr_str, vexpr=self.value_expr_str
            )
        )

        option_unset_regexp = re.compile(
            r'^[#]\s*(?P<option>{oexpr})\s+is\s+not\s+set$'.format(
                oexpr=self.option_expr_str
            )
        )

        for lino, line in fileio.read_text_file_lines(
            infile, filename=filename, rstrip=None, **kwargs
        ):
            if line:
                opt_val_match = option_value_regexp.match(line)
                if opt_val_match is not None:
                    yield (
                        lino,
                        opt_val_match.group("option"),
                        _unpack_value(opt_val_match.group("value"))
                    )

                else:
                    opt_unset_match = option_unset_regexp.match(line)
                    if opt_unset_match is not None:
                        yield (
                            lino,
                            opt_unset_match.group("option"),
                            None
                        )

                    elif line[0] == '#':
                        # just a comment
                        pass

                    else:
                        raise NotImplementedError(line)
                    # -- end if opt unset?, comment?
                # -- end if opt=val?
            # -- end if line
    # --- end of read_file (...) ---
# --- end of ConfigFileReader ---


class _Config(loggable.AbstractLoggable, collections.abc.Mapping):
    """A kconfig-based configuration.

    @cvar CFG_DICT_CLS:  dict type or constructor, for storing config options
    @type CFG_DICT_CLS:  C{type}

    @ivar _kconfig_symbols:  kconfig symbol descriptors
    @type _kconfig_symbols:  L{KconfigSymbols}
                             (kind of
                               C{dict} :: C{str}|L{AbstractKconfigSymbol}
                                       => L{AbstractKconfigSymbol})

    @ivar _config:           configuration dict that maps kconfig symbols
                             to their current value.
                             Do not ref this dict!
                             It will be replaced by a new instance
                             whenever reading config files.
    @type _config:           L{CFG_DICT_CLS} :: L{AbstractKconfigSymbol} => _
    """

    CFG_DICT_CLS = collections.OrderedDict

    def _get_config_file_reader(self):
        return self.create_loggable(ConfigFileReader, logger_name="Reader")

    def get_new_config_dict(self, update=False):
        """Returns a new dict for storing config options.

        Populates this dict with the current configuration if the update
        keyword parameters evaluates to True.

        @keyword update: whether to copy the current config to the new dict
                         Defaults to False.
        @type    update: C{bool}-like

        @return:  new config dict
        @rtype:   L{CFG_DICT_CLS}
        """
        return self.CFG_DICT_CLS(self._config if update else ())
    # --- end of get_new_config_dict (...) ---

    def __init__(self, kconfig_symbols, **kwargs):
        super().__init__(**kwargs)
        self._kconfig_symbols = kconfig_symbols
        self._config = self.CFG_DICT_CLS()
    # ---

    def prepare(self):
        pass

    def convert_option_to_symbol_name(self, option_name, lenient=True):
        """Converts an option name to a symbol name.

        This is mostly a no-op. Derived classes may override this method.

        Note: the option name cannot be assumed to be correct,
              and must be checked by this method (but not whether a
              kconfig symbol exists for it).
              In lenient mode, minor issues should be fixed silently,
              whereas in strict mode, a ValueError should always be raised.

        @raises: ValueError if no symbol name can be determined

        @param   option_name:  option name
        @type    option_name:  C{str}
        @keyword lenient:      be less strict. Defaults to False.
        @type    lenient:      C{bool}
        @return:               symbol name
        @rtype:                C{str}
        """
        if not option_name:
            raise ValueError(option_name)

        return option_name
    # --- end of convert_option_to_symbol_name (...) ---

    def convert_symbol_name_to_option(self, symbol_name):
        """Converts a symbol name to an option name.

        This is a no-op. Derived classes may override this method.

        Note: the symbol name is assumed to be correct,
              and is not checked by this method.

        @raises: ValueError if no option name can be determined

        @param symbol_name:  symbol name
        @type  symbol_name:  C{str}
        @return:             option name
        @rtype:              C{str}
        """
        return symbol_name
    # --- end of convert_symbol_name_to_option (...) ---

    def normalize_key_str(self, key):
        """Normalizes a str key so that it can be used
        for accessing kconfig symbols.

        In constrast to normalize_key(),
        this method simply removes the common config option name prefix,
        if it exists, and returns a str key that can be used for
        accessing _kconfig_symbols.

        @param key:  key
        @type  key:  C{str}
        @return:     normalized key
        @rtype:      C{str}
        """
        return self.convert_option_to_symbol_name(key, lenient=True)
    # --- end of normalize_key_str (...) ---

    def normalize_key(self, key):
        """Normalizes a kconfig symbol key.

        @param key:  key
        @type  key:  C{str} or subclass of L{AbstractKconfigSymbol}
        @return:     normalized key, a kconfig symbol object
        @rtype:      subclass of L{AbstractKconfigSymbol}
        """
        sym_key = self.normalize_key_str(key) if isinstance(key, str) else key
        return self._kconfig_symbols[sym_key]
    # ---

    def _replace_config_dict(self, cfg_dict):
        self._config = cfg_dict

    def _incorporate_changes(self, cfg_dict, decision_syms):
        """Assign a new config dict to this object.

        Unsafe operation, no checks will be performed!

        @param cfg_dict:  config dict
        @type  cfg_dict:  dict :: L{AbstractKconfigSymbol} => _

        @return: None (implicit)
        """
        self._replace_config_dict(cfg_dict)
    # ---

    def iter_config(self):
        return self._config.items()
    # --- end of iter_config (...) ---

    def get_symbol_value(self, kconfig_symbol):
        return self._config[kconfig_symbol]

    def __getitem__(self, key):
        return self._config[self.normalize_key(key)]

    def __len__(self):
        return len(self._config)

    def __iter__(self):
        return iter(self._config)

    def _read_config_files(self, cfg_dict, infiles):
        """Reads a zero or (preferably) more config files and stores
        a mapping :: <kconfig symbol> => <value> in the given config dict.

        @raises ValueError: bad option name
                            (propagated from convert_option_to_symbol_name)
                            or bad option value
                            (propagated from ConfigFileReader.unpack_value)

        @param cfg_dict:  dict for storing config options (symbol => value)
        @type  cfg_dict:  C{dict}:: L{AbstractKconfigSymbol} => _
        @param infiles:   a list containg input files
                          or 2-tuples input file X input file name
        @type  infiles:   C{list} of C{str}|2-tuple(C{str}, C{str}|C{None})
        @return:          cfg_dict
        """

        def normalize_sym_value(sym, vtype, inval):
            try:
                normval = sym.normalize_and_validate(inval)
            except ValueError:
                try:
                    normval = sym.normalize_and_validate(inval, lenient=True)
                except ValueError:
                    self.logger.warning(
                        "invalid %s value %r for %s symbol %s",
                        vtype, inval, sym.type_name, sym.name
                    )
                    raise
                else:
                    self.logger.warning(
                        (
                            'improper %s value %r for %s symbol %s, '
                            'normalized to %r'
                        ),
                        vtype, inval, sym.type_name, sym.name, normval
                    )
                # -- end try again
            # -- end try

            return normval
        # --- end of normalize_sym_value (...) ---

        get_symbol_name = self.convert_option_to_symbol_name

        reader = self._get_config_file_reader()
        # FIXME: modifying kconfig_syms, but not cfg_dict?
        #         should revert changes to kconfig_syms on error
        kconfig_syms = self._kconfig_symbols

        for infile_item in infiles:
            # unpack infile_item, it's either a str or a 2-tuple(str,str|None)
            if isinstance(infile_item, tuple):
                infile_path, infile_name = infile_item
            else:
                infile_path, infile_name = infile_item, None

            self.logger.debug(
                "Reading config file %r", infile_name or infile_path
            )
            for lino, option, value in reader.read_file(
                infile_path, filename=infile_name
            ):
                try:
                    symbol_name = get_symbol_name(option, lenient=False)
                except ValueError:
                    self.logger.warning(
                        "Failed to get symbol name for %s, ignoring.",
                        symbol_name
                    )
                    continue

                try:
                    sym = kconfig_syms[symbol_name]
                except KeyError:
                    # symbol does not exist yet
                    # * if the option is not set, ignore it
                    # * if the option is set, create a new symbol
                    #   and log about it
                    self.logger.debug("Read unknown symbol %s", symbol_name)
                    if value is None:
                        self.logger.debug(
                            "Cannot infer type of %s (not set), ignoring",
                            symbol_name
                        )
                    else:
                        self.logger.debug(
                            "Adding unknown symbol %s as new %s symbol",
                            symbol_name, value[0]
                        )

                        sym = kconfig_syms.add_unknown_symbol(
                            value[0].value, symbol_name
                        )
                        cfg_dict[sym] = value[-1]

                else:
                    if value is None:
                        # do not remove sym from the config, just disable it
                        cfg_dict[sym] = None

                    else:
                        normval = normalize_sym_value(sym, value[0], value[1])
                        cfg_dict[sym] = normval
                    # -- end if value
                # -- end try to use existing symbol
            # --
        # --

        return cfg_dict
    # ---

    def read_config_file(self, infile, filename=None, update=False):
        """Reads options from a single ".config" file and stores them
        in the config dict.

        If the update parameter is true, then entries are added to the
        existing configuration, and otherwise a new config dict is created.

        Note: This operation replaces the existing _config dict,
              but only when successful (i.e. no exceptions occurred).
              However, it modifies the kconfig symbols inplace!

        @raises ValueError: bad option name
                            (propagated from convert_option_to_symbol_name)
                            or bad option value
                            (propagated from ConfigFileReader.unpack_value)

        @param   infile:    .config file object or path
        @type    infile:    fileobj or C{str}
        @param   filename:  name of the config file or None. Defaults to None.
        @type    filename:  C{str} or C{None}
        @keyword update:    whether to update the current configuration dict
                            with the entries from infile (True)
                            or create a config dict (False).
                            Defaults to False.
        @type    update:    C{bool}

        @return: None (implicit)
        """
        cfg_dict = self.get_new_config_dict(update=update)
        self._read_config_files(cfg_dict, [(infile, filename)])
        self._replace_config_dict(cfg_dict)
    # --- end of read_config_file (...) ---

    def read_config_files(self, *infiles, update=False):
        """
        Similar to L{read_config_file()}, but accepts a series of input files.
        """
        cfg_dict = self.get_new_config_dict(update=update)
        self._read_config_files(cfg_dict, infiles)
        self._replace_config_dict(cfg_dict)
    # --- end of read_config_files (...) ---

    def generate_config_lines(self):
        """Generator that creates text lines representing the current
        configuration, suitable for writing to a ".config" file.

        @return: "option=value", "# option is not set"
        @rtype:  C{str}
        """
        for sym, val in self.iter_config():
            yield sym.format_value(val, self.convert_symbol_name_to_option)
    # --- end of generate_config_lines (...) ---

    def _write_config_file(self, outfile, filename=None, **kwargs):
        self.logger.debug("Writing config file %r", filename or outfile)

        fileio.write_text_file_lines(
            outfile,
            self.generate_config_lines(),
            filename=filename, append_newline=True, **kwargs
        )
    # ---

    def write_config_file(self, outfile, filename=None, **kwargs):
        """Writes the current configuration to a file.

        @param   outfile:   output file object or path
        @type    outfile:   fileobj or C{str}
        @keyword filename:  name of the output file or None (the default)
        @type    filename:  C{str} or C{None}
        @param   kwargs:    additional keyword arguments for
                            L{fileio.write_text_file_lines()}
        @type    kwargs:    C{dict} :: C{str} => _

        @return: None (implicit)
        """
        self._write_config_file(outfile, filename=filename, **kwargs)
    # --- end of write_config_file (...) ---

# --- _Config ---


class Config(_Config):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._decision_symbols = None
        self._tmpdir = None
        self._tmpconfig = None
        self._tmpconfig_load_required = False
    # --- end of __init__ (...) ---

    def get_tmpdir(self):
        tdir = self._tmpdir
        if tdir is None:
            self.logger.debug("Creating temporary directory for config files")
            tdir = tmpdir.Tmpdir(suffix=".kernelconfig")
            self._tmpdir = tdir
            self.logger.debug("Temporary directory is %r", tdir.get_filepath())
        # --
        return tdir
    # --- end of get_tmpdir (...) ---

    def _load_tmpconfig_if_needed(self):
        if self._tmpconfig_load_required:
            self.logger.debug("Loading temporary oldconfig")
            cfg_dict = self.get_new_config_dict(update=False)
            self._read_config_files(cfg_dict, [(self._tmpconfig, None)])
            self._replace_config_dict(cfg_dict, tmpconfig_invalidate=False)
            # decision symbols do not accumulate when configuring
            # multiple times
            self._decision_symbols = None
            self._tmpconfig_load_required = False
        # --
    # ---

    def prepare(self):
        self._load_tmpconfig_if_needed()
    # ---

    def _replace_config_dict(self, cfg_dict, tmpconfig_invalidate=True):
        if tmpconfig_invalidate:
            self._tmpconfig = None
            self._tmpconfig_load_required = False
        # --

        super()._replace_config_dict(cfg_dict)
    # ---

    def _incorporate_changes(self, cfg_dict, decision_syms):
        super()._incorporate_changes(cfg_dict, decision_syms)
        self._decision_symbols = decision_syms
        self._write_oldconfig()
    # ---

    def _write_oldconfig(self):
        if self._decision_symbols:
            decisions = {
                sym.name: sym.get_lkconfig_value_repr(self._config[sym])
                for sym in self._decision_symbols
            }
        else:
            decisions = {}
        # --

        tdir = self.get_tmpdir()
        tmp_inconfig = tdir.get_filepath("inconfig")
        tmp_outconfig = tdir.get_filepath("outconfig")

        self._write_config_file(tmp_inconfig)

        self.logger.debug("Running oldconfig, writing to %r", tmp_outconfig)
        lkconfig.oldconfig(
            tmp_inconfig, tmp_outconfig, decisions,
            logger=self.get_child_logger("lkconfig.oldconfig")
        )

        self.logger.debug("Temporary oldconfig file is ready.")
        self._tmpconfig = tmp_outconfig
        self._tmpconfig_load_required = True
    # --- end of _write_oldconfig (...) ---

    def _write_oldconfig_if_needed(self):
        if self._decision_symbols and not self._tmpconfig:
            self._write_oldconfig()
            assert self._tmpconfig
    # --- end of _write_oldconfig_if_needed (...) ---

    def write_config_file(self, outfile, filename=None, **kwargs):
        self._write_oldconfig_if_needed()

        if self._tmpconfig:
            self.logger.debug(
                "Copying temporary oldconfig file to %r",
                filename or outfile
            )
            shutil.copyfile(self._tmpconfig, outfile)
        else:
            self._write_config_file(outfile, filename=filename, **kwargs)
    # ---

# --- end of Config ---


class KernelConfig(Config):
    """A kernel configuration."""

    CFG_OPTNAME_PREFIX = "CONFIG_"

    def convert_option_to_symbol_name(self, option_name, lenient=False):
        opt = option_name.upper() if lenient else option_name

        if opt.startswith(self.CFG_OPTNAME_PREFIX):
            symbol_name = opt[len(self.CFG_OPTNAME_PREFIX):]
        elif lenient:
            symbol_name = opt
        else:
            raise ValueError(option_name)

        if not symbol_name:
            raise ValueError(option_name)

        return symbol_name
    # ---

    def convert_symbol_name_to_option(self, symbol_name):
        return self.CFG_OPTNAME_PREFIX + symbol_name
    # --- end of convert_symbol_name_to_option (...) ---

# --- end of KernelConfig ---
