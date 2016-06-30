# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import string

from ...util.misc import identity, iter_dedup


__all__ = ["ConfigurationSourceStrFormatter"]


def unqualify_field_name(name):
    return name.partition(".")[0]


class ConfigurationSourceStrFormatter(string.Formatter):
    """
    Various configuration source types support str-formatting
    of arguments and file paths.

    The format variables depend on

      (a) the configuration source environment (e.g. arch, srctree)

      (b) the config source type and/or instance

      (c) the config source arg config (e.g. tmpdir, outfile)

    This is the base class that adresses (a).
    It also provides a fmt_vars dict that can be modified freely
    by derived classes and consumers.

    The fmt-var lookup is handled in get_value(key, args, kwargs),
    where args/kwargs are the args/kwargs passed to [v]format(_, args, kwargs).

    If the key is an int, the fmt-var is looked up in args.

    Otherwise, if it is looked up in the following order:

      * key in kwargs?

      * key in format vars?

      * call get_value_dynamic_lookup(key, normalize_field_name(key))

        (derived classes may override or extend this method)

        - normalize_field_name(key) in config source environment format vars?

        - raise KeyError

    Note: kwargs overshadow format vars,
          format vars overshadow conf env vars

    Note: when subclassing, don't forget to merge FIELD_RENAME_MAP
          from the base class with the new remap dict
          This can be done base_cls.merge_field_rename_map({...}).

    @cvar FIELD_RENAME_MAP:  dict for renaming/unaliasing field names,
                             keys should be lowercase strings
    @type FIELD_RENAME_MAP:  C{dict} :: C{str} => C{str}

    @ivar fmt_vars:  additional format vars
    @type fmt_vars:  C{dict} :: C{str} => C{object}

    @ivar senv:      configuration source environment
    @type senv:      L{ConfigurationSourcesEnv}
    """

    FIELD_RENAME_MAP = {
        "s": "srctree"
    }

    @classmethod
    def merge_field_rename_map(cls, rename_map):
        dret = cls.FIELD_RENAME_MAP.copy()
        if rename_map:
            dret.update(rename_map)
        return dret

    def __init__(self, conf_source_env):
        super().__init__()
        self.fmt_vars = {}
        self.senv = conf_source_env

    def normalize_field_name(self, key):
        lowkey = key.lower()
        return self.FIELD_RENAME_MAP.get(lowkey, lowkey)

    def get_value_dynamic_lookup(self, key, norm_key):
        return self.senv.get_format_vars()[norm_key]

    def get_value(self, key, args, kwargs):
        if isinstance(key, int):
            return args[key]

        elif key in kwargs:
            return kwargs[key]

        elif key in self.fmt_vars:
            return self.fmt_vars[key]

        else:
            norm_key = self.normalize_field_name(key)
            return self.get_value_dynamic_lookup(key, norm_key)
    # --- end of get_value (...) ---

    def format_list(self, str_list, *args, **kwargs):
        return [self.vformat(s, args, kwargs) for s in str_list]
    # --- end of format_list (...) ---

    def iter_referenced_vars_v(self, format_str_list, *, fqn=False):
        """
        Generator that yields the name of referenced format variables.
        Duplicates are likely and do not get filtered out.

        @param   format_str_list:  list of format strings
        @type    format_str_list:  C{list} of C{str}  (or iterable)

        @keyword fqn:              whether to emit full names
                                   ("fmtvar.attr"; True)
                                   or just the name of the format var (False).
                                   Defaults to False.
        @type    fqn:              C{bool}

        @return:  format var name(s)
        @rtype:   C{str}
        """
        get_field_name = identity if fqn else unqualify_field_name

        for format_str in format_str_list:
            for item in self.parse(format_str):
                if item[1]:
                    yield get_field_name(item[1])
    # --- end of iter_referenced_vars_v (...) ---

    def iter_referenced_vars(self, *format_str_list, fqn=False):
        """var-args variant of iter_referenced_vars_v()."""
        return self.iter_referenced_vars_v(format_str_list, fqn=fqn)

    def iter_unknown_vars_v(self, format_str_list):
        """
        @return:  2-tuples (name, full name)
        @rtype:   C{str}, C{str}
        """
        _unqualify = unqualify_field_name

        def get_value(key, *, vget=self.get_value, args=(), kwargs={}):
            return vget(key, args, kwargs)

        # save some time on repeated value lookups and remember past keys
        hits = set()   # keys that are known to exist
        miss = set()   # keys that are known not to exist

        for full_name in (
            self.iter_referenced_vars_v(format_str_list, fqn=True)
        ):
            key = _unqualify(full_name)

            if key in hits:
                # key exists
                pass

            elif key in miss:
                # key does not exist
                yield (key, full_name)

            else:
                try:
                    get_value(key)
                except (IndexError, KeyError):
                    # key does not exist
                    #
                    #  catching IndexError here might be a bit odd,
                    #  but there may be legitimate use cases
                    #
                    miss.add(key)
                    yield (key, full_name)
                else:
                    # key exists
                    hits.add(key)
                # -- end try get value

            # -- end if check key exists w/ cache lookup
    # --- end of iter_unknown_vars_v (...) ---

    def iter_unknown_var_names_v(self, format_str_list):
        return iter_dedup((
            name
            for name, full_name in self.iter_unknown_vars_v(format_str_list)
        ))
    # --- end of iter_unknown_var_names_v (...) ---

    def iter_unknown_var_names(self, *format_str_list):
        return self.iter_unknown_var_names_v(format_str_list)

# --- end of ConfigurationSourceStrFormatter ---
