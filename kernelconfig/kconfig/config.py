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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.option_expr_str = r'[A-Z_a-z0-9]+'
        self.value_expr_str = r'(?:\S+(?:\s+\S+)*)'
    # ---

    def unpack_value(self, inval):
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

    def read_file(self, infile, filename=None):
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
            infile, filename=filename, strip=None
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
    """The kernel configuration.

    @cvar CFG_DICT_CLS:  dict type or constructor, for storing config options
    @type CFG_DICT_CLS:  C{type}

    @cvar CFG_OPTNAME_PREFIX:  config option name prefix
                               that gets stripped off/added to option names
                               when reading/writing config files.
                               Derived classes may set this to a non-empty
                               value, which should contain all prefix chars
                               (e.g. including a terminating "_").
    @type CFG_OPTNAME_PREFIX:  C{str} or C{None} (or anything False)

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
    # FIXME: let subclasses implement methods for unprefixing/prefixing,
    #        and ditch this var
    #        unprefix_lenient - remove prefix if exists
    #        unprefix_strict  - remove prefix, must exist
    #        prefix           - add prefix
    CFG_OPTNAME_PREFIX = None

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
        pfx = self.CFG_OPTNAME_PREFIX
        upkey = key.upper()  # FIXME bad assumption
        return upkey[len(pfx):] if (pfx and upkey.startswith(pfx)) else upkey
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

    def __getitem__(self, key):
        return self._config[self.normalize_key(key)]

    def __len__(self):
        return len(self._config)

    def __iter__(self):
        return iter(self._config)

    def _read_config_files(self, cfg_dict, infiles):
        optname_prefix = self.CFG_OPTNAME_PREFIX or ""
        optname_pfxlen = len(optname_prefix)

        reader = self._get_config_file_reader()

        for infile_item in infiles:
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
                symbol_name = None
                if option.startswith(optname_prefix):
                    symbol_name = option[optname_pfxlen:]
                    if not symbol_name:
                        raise ValueError(
                            "empty option name after removing prefix"
                        )
                    # --
                else:
                    raise NotImplementedError(
                        "option name does not start with prefix: %s" % option
                    )
                # --

                cfg_dict[symbol_name] = value
            # --
        # --
    # ---

    def read_config_file(self, infile, filename=None, update=False):
        cfg_dict = self.get_new_config_dict(update=update)
        self._read_config_files(cfg_dict, [(infile, filename)])
        self._config = cfg_dict
    # --- end of read_config_file (...) ---

    def read_config_files(self, *infiles, update=False):
        cfg_dict = self.get_new_config_dict(update=update)
        self._read_config_files(cfg_dict, infiles)
        self._config = cfg_dict
    # --- end of read_config_files (...) ---

# ---


class KernelConfig(Config):
    CFG_OPTNAME_PREFIX = "CONFIG_"
