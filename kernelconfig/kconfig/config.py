# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import collections
import collections.abc
import re

from ..abc import loggable
from ..util import fileio
from . import symbol

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
        self.value_expr_str = r'(?:\S+(?:\s+\S+)*)'
    # ---

    def unpack_value(self, inval):
        """Converts a str value from dubious sources to a value suitable
        for storing in a kconfig symbol X value dict.
        Also detects the type of the value.

        @raises: ValueError if inval is faulty

        @param inval:  input value
        @type  inval:  necessarily C{str}

        @return: 2-tuple (value type, value),
                 the value type can also be used for creating kconfig symbols
        @rtype:  2-tuple (
                   L{symbol.KconfigSymbolValueType},
                   C{str}|C{int}|L{symbol.TristateKconfigSymbolValue})
        """
        # FIXME: this method could be moved to somewhere else,
        #        e.g. kconfig.symbol - there's nothing specific to this class
        _vtype = symbol.KconfigSymbolValueType

        if not inval:
            raise ValueError()

        elif inval == "n":
            # tristate or boolean value
            # or inval in {"n", "m", "y"}: getattr(_, inval)
            return (_vtype.v_tristate, symbol.TristateKconfigSymbolValue.n)
        elif inval == "m":
            return (_vtype.v_tristate, symbol.TristateKconfigSymbolValue.m)
        elif inval == "y":
            return (_vtype.v_tristate, symbol.TristateKconfigSymbolValue.y)

        elif inval[0] in "\"'" and inval[0] == inval[-1] and len(inval) > 1:
            # string value (always quoted)
            #  FIXME: unescape value
            return (_vtype.v_string, inval[1:-1])

        else:
            # could be int w/ base 10
            try:
                intval = int(inval, 10)
            except ValueError:
                pass
            else:
                return (_vtype.v_int, intval)

            # otherwise, could be int w/ base 16
            try:
                intval = int(inval, 0x10)
            except ValueError:
                pass
            else:
                return (_vtype.v_hex, intval)

            # unknown value
            raise ValueError(inval)
    # --- end of unpack_value (...) ---

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
        _unpack_value = self.unpack_value

        option_value_regexp = re.compile(
            r'^(?P<option>{oexpr})[=](?P<value>{vexpr})$'.format(
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


class Config(loggable.AbstractLoggable, collections.abc.Mapping):
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

    def iter_config(self):
        return self._config.items()
    # --- end of iter_config (...) ---

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
                symbol_name = get_symbol_name(option, lenient=False)

                try:
                    sym = kconfig_syms[symbol_name]
                except KeyError:
                    # symbol does not exist yet
                    # * if the option is not set, ignore it
                    # * if the option is set, create a new symbol
                    #   and log about it
                    self.logger.warning("Read unknown symbol %s", symbol_name)
                    if value is None:
                        self.logger.info(
                            "Cannot infer type of %s (not set), ignoring",
                            symbol_name
                        )
                    else:
                        self.logger.info(
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
                        try:
                            normval = sym.normalize_and_validate(value[1])
                        except ValueError:
                            self.logger.error(
                                "invalid %s value %r for %s symbol %s",
                                value[0], value[1], sym.type_name, sym.name
                            )
                            raise  # or recover // FIXME
                        else:
                            cfg_dict[sym] = normval
                        # --
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
        self._config = cfg_dict
    # --- end of read_config_file (...) ---

    def read_config_files(self, *infiles, update=False):
        """
        Similar to L{read_config_file()}, but accepts a series of input files.
        """
        cfg_dict = self.get_new_config_dict(update=update)
        self._read_config_files(cfg_dict, infiles)
        self._config = cfg_dict
    # --- end of read_config_files (...) ---

    def generate_config_lines(self):
        """Generator that creates text lines representing the current
        configuration, suitable for writing to a ".config" file.

        @return: "option=value", "# option is not set"
        @rtype:  C{str}
        """
        for sym, val in self.iter_config():
            yield sym.format_value(val)
    # --- end of generate_config_lines (...) ---

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
        fileio.write_text_file_lines(
            outfile,
            self.generate_config_lines(),
            append_newline=True,
            **kwargs
        )
    # --- end of write_config_file (...) ---

# --- Config ---


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
